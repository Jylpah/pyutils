import logging
from typing import cast, Type, Any, TypeVar, Self, AsyncGenerator, Callable, Sequence, Self, ClassVar, Optional
from abc import ABCMeta, abstractmethod
from collections.abc import MutableMapping
from pydantic import BaseModel, ValidationError
from aiocsv.readers import AsyncDictReader
from csv import Dialect, excel, QUOTE_NONNUMERIC
from aiofiles import open

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


########################################################
#
# Importable()
#
########################################################


class Importable(metaclass=ABCMeta):
    """Abstract class to provide import"""

    @classmethod
    async def import_file(
        cls,
        file: str,
        **kwargs,
    ) -> AsyncGenerator[Self, None]:
        debug("starting")
        try:
            if file.lower().endswith(".txt") and issubclass(cls, TXTImportable):
                debug("importing from TXT file: %s", file)
                async for obj in cls.import_txt(file, **kwargs):
                    yield obj
            elif file.lower().endswith(".json") and issubclass(cls, JSONImportable):
                debug("importing from JSON file: %s", file)
                async for obj in cls.import_json(file, **kwargs):
                    yield obj
            elif file.lower().endswith(".csv") and issubclass(cls, CSVImportable):
                debug("importing from CSV file: %s", file)
                async for obj in cls.import_csv(file):
                    yield obj
            else:
                raise ValueError(f"Unsupported file format: {file}")
                yield
        except Exception as err:
            error(f"{err}")

    @classmethod
    async def count_file(cls, file: str, **kwargs) -> int:
        """Count Importables in the file"""
        res: int = 0
        async for _ in cls.import_file(file=file, **kwargs):
            res += 1
        return res


########################################################
#
# TXTImportable()
#
########################################################


TXTImportableSelf = TypeVar("TXTImportableSelf", bound="TXTImportable")


class TXTImportable(BaseModel):
    """Abstract class to provide TXT import"""

    @classmethod
    def from_txt(cls, text: str, **kwargs) -> Self:
        """Provide parse object from a line of text"""
        raise NotImplementedError

    @classmethod
    async def import_txt(cls, filename: str, **kwargs) -> AsyncGenerator[Self, None]:
        """Import from filename, one model per line"""
        try:
            debug(f"starting: {filename}")
            # importable : TXTImportableSelf | None
            async with open(filename, "r") as f:
                async for line in f:
                    try:
                        debug("line: %s", line)
                        if (importable := cls.from_txt(line.rstrip(), **kwargs)) is not None:
                            yield importable
                    except ValidationError as err:
                        error(f"Could not validate mode: {err}")
                    except Exception as err:
                        error(f"{err}")
        except Exception as err:
            error(f"Error importing file {filename}: {err}")


########################################################
#
# CSVImportable()
#
########################################################


CSVImportableSelf = TypeVar("CSVImportableSelf", bound="CSVImportable")


class CSVImportable(BaseModel):
    """Abstract class to provide CSV export"""

    @classmethod
    def from_csv(cls, row: dict[str, Any]) -> Self | None:
        """Provide CSV row as a dict for csv.DictWriter"""
        try:
            row = cls._set_field_types(row)
            return cls.parse_obj(row)
        except Exception as err:
            error(f"Could not parse row ({row}): {err}")
        return None

    @classmethod
    def _set_field_types(cls, row: dict[str, Any]) -> dict[str, Any]:
        ## Does NOT WORK with Alias field names
        assert type(row) is dict, "row has to be type dict()"
        res: dict[str, Any] = dict()
        for field in row.keys():
            if row[field] != "":
                try:
                    field_type = cls.__fields__[field].type_
                    debug("field=%s, field_type=%s, value=%s", field, field_type, row[field])
                    res[field] = (field_type)(eval(row[field]))
                except KeyError:  # field not in cls
                    continue
                except AttributeError as err:
                    error(f"Class {cls.__name__}() does not have attribute: {field}")
                except Exception as err:
                    debug("%s raised, trying direct assignment: %s", type(err), err)
                    res[field] = row[field]
        return res

    @classmethod
    async def import_csv(cls, filename: str) -> AsyncGenerator[Self, None]:
        """Import from filename, one model per line"""
        try:
            dialect: Type[Dialect] = excel
            async with open(filename, mode="r", newline="") as f:
                async for row in AsyncDictReader(f, dialect=dialect):
                    debug("row: %s", row)
                    try:
                        if (importable := cls.from_csv(row)) is not None:
                            # debug(f'{importable}')
                            yield importable
                    except ValidationError as err:
                        error(f"Could not validate mode: {err}")
                    except Exception as err:
                        error(f"{err}")
        except Exception as err:
            error(f"Error importing file {filename}: {err}")


########################################################
#
# JSONImportable()
#
########################################################


JSONImportableSelf = TypeVar("JSONImportableSelf", bound="JSONImportable")


class JSONImportable(BaseModel):
    """Base class for Pydantic models with fail-safe parsing and transformations.
    Returns None if parsing / iumporting fails
    """

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
    def from_obj(cls, obj: Any, in_type: BaseModel | None = None) -> Optional[Self]:
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
    def from_objs(cls, objs: Sequence[Any], in_type: BaseModel | None = None) -> list[Self]:
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
    def from_str(cls, content: str) -> Self | None:
        """Open replay JSON file and return class instance"""
        try:
            return cls.parse_raw(content)
        except ValidationError as err:
            error(f"Invalid replay format: {err}")
        return None

    @classmethod
    async def import_json(cls, filename: str, **kwargs) -> AsyncGenerator[Self, None]:
        """Import from filename, one model per line"""
        try:
            # importable : JSONImportableSelf | None
            async with open(filename, "r") as f:
                async for line in f:
                    try:
                        if (importable := cls.from_str(line, **kwargs)) is not None:
                            yield importable
                    except ValidationError as err:
                        error(f"Could not validate mode: {err}")
                    except Exception as err:
                        error(f"{err}")
        except Exception as err:
            error(f"Error importing file {filename}: {err}")
