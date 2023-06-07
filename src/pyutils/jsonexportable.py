########################################################
#
# JSONExportable()
#
########################################################

import logging
from typing import (
    Optional,
    Type,
    Any,
    Self,
    Literal,
    TypeVar,
    ClassVar,
    Union,
    Callable,
    Sequence,
    AsyncGenerator,
    get_args,
)
from enum import Enum
from datetime import date, datetime
from collections.abc import MutableMapping
from pydantic import BaseModel, ValidationError
from asyncio import CancelledError
from aiofiles import open
from os.path import isfile, exists
from os import linesep
from bson.objectid import ObjectId
from abc import abstractmethod

from .eventcounter import EventCounter

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug

TypeExcludeDict = MutableMapping[int | str, Any]

# D = TypeVar("D", bound="JSONExportable")
# J = TypeVar("J", bound="JSONExportable")
# O = TypeVar("O", bound="JSONExportable")

DESCENDING: Literal[-1] = -1
ASCENDING: Literal[1] = 1
TEXT: Literal["text"] = "text"

Idx = Union[str, int, ObjectId]
BackendIndexType = Literal[-1, 1, "text"]
BackendIndex = tuple[str, BackendIndexType]
I = TypeVar("I", bound=Idx)


class JSONExportable(BaseModel):
    """Base class for Pydantic models with fail-safe JSON import & export and
    registrable model transformations. Returns None if parsing / importing / transformation fails
    """

    _exclude_export_DB_fields: ClassVar[Optional[TypeExcludeDict]] = None
    _exclude_export_src_fields: ClassVar[Optional[TypeExcludeDict]] = None
    _include_export_DB_fields: ClassVar[Optional[TypeExcludeDict]] = None
    _include_export_src_fields: ClassVar[Optional[TypeExcludeDict]] = None
    _export_DB_by_alias: bool = True
    _exclude_defaults: bool = True
    _exclude_unset: bool = True
    _exclude_none: bool = True

    # This is set in every subclass using __init_subclass__()
    _transformations: ClassVar[MutableMapping[Type, Callable[[Any], Optional[Self]]]] = dict()

    def __init_subclass__(cls, **kwargs) -> None:
        """Use PEP 487 sub class constructor instead a custom one"""
        # make sure each subclass has its own transformation register
        cls._transformations = dict()

    @classmethod
    def register_transformation(
        cls,
        obj_type: Any,
        method: Callable[[Any], Optional[Self]],
    ) -> None:
        """Register transformations"""
        cls._transformations[obj_type] = method
        return None

    @classmethod
    def transform(cls, in_obj: Any) -> Optional[Self]:
        """Transform object to out_type if supported"""
        try:
            if type(in_obj) is cls:
                return in_obj
            else:
                return cls._transformations[type(in_obj)](in_obj)  # type: ignore
        except Exception as err:
            error(f"failed to transform {type(in_obj)} to {cls}: {err}")
        return None

    @classmethod
    def transform_many(cls, in_objs: Sequence[Any]) -> list[Self]:
        """Transform a Sequence of objects into list of Self"""
        return [out for obj in in_objs if (out := cls.transform(obj)) is not None]

    @classmethod
    def from_obj(cls, obj: Any, in_type: type[BaseModel] | None = None) -> Optional[Self]:
        """Parse instance from raw object.
        Returns None if reading from object failed.
        """
        obj_in: BaseModel
        if in_type is None:
            try:
                return cls.parse_obj(obj)
            except ValidationError as err:
                error("could not parse object as %s: %s", cls.__name__, str(err))
        else:
            try:
                if (obj_in := in_type.parse_obj(obj)) is not None:
                    return cls.transform(obj_in)
            except ValidationError as err:
                error("could not parse object as %s: %s", cls.__name__, str(err))
        return None

    @classmethod
    def from_objs(cls, objs: Sequence[Any], in_type: type[BaseModel] | None = None) -> list[Self]:
        """Parse list of instances from raw objects.
        Parsing failures are ignored silently.
        """
        return [out for obj in objs if (out := cls.from_obj(obj, in_type=in_type)) is not None]

    @classmethod
    async def open_json(cls, filename: str) -> Self | None:
        """Open replay JSON file and return class instance"""
        try:
            async with open(filename, "r") as f:
                return cls.parse_raw(await f.read())
        except Exception as err:
            error(f"Error reading replay: {err}")
        return None

    @classmethod
    def parse_str(cls, content: str) -> Self | None:
        """return class instance from a JSON string"""
        try:
            return cls.parse_raw(content)
        except ValidationError as err:
            error(f"Could not parse {type(cls)} from JSON: {err}")
        return None

    @classmethod
    async def import_json(cls, filename: str, **kwargs) -> AsyncGenerator[Self, None]:
        """Import from filename, one model per line"""
        try:
            # importable : JSONImportableSelf | None
            async with open(filename, "r") as f:
                async for line in f:
                    try:
                        if (importable := cls.parse_str(line, **kwargs)) is not None:
                            yield importable
                    except ValidationError as err:
                        error(f"Could not validate mode: {err}")
                    except Exception as err:
                        error(f"{err}")
        except Exception as err:
            error(f"Error importing file {filename}: {err}")

    def _export_helper(self, params: dict[str, Any], fields: list[str] | None = None, **kwargs) -> dict:
        """Helper func to process params for obj/src export funcs"""
        if fields is not None:
            del params["exclude"]
            params["include"] = {f: True for f in fields}
            params["exclude_defaults"] = False
            params["exclude_unset"] = False
            params["exclude_none"] = False
        else:
            for f in ["exclude", "include"]:
                try:
                    params[f].update(kwargs[f])
                    del kwargs[f]
                except:
                    pass
        params.update(kwargs)
        return params

    @property
    def index(self) -> Idx:
        """return backend index"""
        raise NotImplementedError

    @property
    def indexes(self) -> dict[str, Idx]:
        """return backend indexes"""
        raise NotImplementedError

    @classmethod
    def backend_indexes(cls) -> list[list[tuple[str, BackendIndexType]]]:
        """return backend search indexes"""
        raise NotImplementedError

    def __hash__(self) -> int:
        """Make object hashable, but using index fields only"""
        return hash(self.index)

    def obj_db(self, fields: list[str] | None = None, **kwargs) -> dict:
        params: dict[str, Any] = {
            "exclude": self._exclude_export_DB_fields,
            "include": self._include_export_DB_fields,
            "exclude_defaults": self._exclude_defaults,
            "by_alias": self._export_DB_by_alias,
        }
        params = self._export_helper(params=params, fields=fields, **kwargs)
        return self.dict(**params)

    def obj_src(self, fields: list[str] | None = None, **kwargs) -> dict:
        params: dict[str, Any] = {
            "exclude": self._exclude_export_src_fields,
            "include": self._include_export_src_fields,
            "exclude_unset": self._exclude_unset,
            "exclude_none": self._exclude_none,
            "by_alias": not self._export_DB_by_alias,
        }
        params = self._export_helper(params=params, fields=fields, **kwargs)
        return self.dict(**params)

    def json_db(self, fields: list[str] | None = None, **kwargs) -> str:
        params: dict[str, Any] = {
            "exclude": self._exclude_export_DB_fields,
            "include": self._include_export_DB_fields,
            "exclude_defaults": self._exclude_defaults,
            "by_alias": self._export_DB_by_alias,
        }
        params = self._export_helper(params=params, fields=fields, **kwargs)
        return self.json(**params)

    def json_src(self, fields: list[str] | None = None, **kwargs) -> str:
        params: dict[str, Any] = {
            "exclude": self._exclude_export_src_fields,
            "include": self._include_export_src_fields,
            "exclude_unset": self._exclude_unset,
            "exclude_none": self._exclude_none,
            "by_alias": not self._export_DB_by_alias,
        }
        params = self._export_helper(params=params, fields=fields, **kwargs)
        return self.json(**params)

    async def save_json(self, filename: str) -> int:
        """Save object JSON into a file"""
        try:
            async with open(filename, "w") as rf:
                return await rf.write(self.json_src())
        except Exception as err:
            error(f"Error writing replay {filename}: {err}")
        return -1
