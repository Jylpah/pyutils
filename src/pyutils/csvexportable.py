########################################################
#
# CSVExportable()
#
########################################################

import logging
from typing import cast, Type, Any, Self, AsyncGenerator, Callable, Self, ClassVar
from collections.abc import MutableMapping
from pydantic import BaseModel, ValidationError
from aiocsv.readers import AsyncDictReader
from csv import Dialect, excel, QUOTE_NONNUMERIC
from datetime import date, datetime
from aiofiles import open
from enum import Enum
from copy import deepcopy

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


class CSVExportable(BaseModel):
    """Abstract class to provide CSV export"""

    # Define subclass' CSV readers/writers into these
    _csv_custom_writers: ClassVar[MutableMapping[str, Callable[[Any], Any]]] = dict()
    _csv_custom_readers: ClassVar[MutableMapping[str, Callable[[Any], Any]]] = dict()
    # Do not store directly into these
    _csv_writers: ClassVar[MutableMapping[str, Callable[[Any], Any]]] = dict()
    _csv_readers: ClassVar[MutableMapping[str, Callable[[Any], Any]]] = dict()

    def __init_subclass__(cls, **kwargs) -> None:
        """Use PEP 487 sub class constructor instead a custom one"""
        # makes sure each subclass has its own CSV field readers/writers.
        # Inherits the parents field functions using copy.deepcopy()
        super().__init_subclass__(**kwargs)
        try:
            cls._csv_writers = deepcopy(cls._csv_writers)  # type: ignore
            cls._csv_readers = deepcopy(cls._csv_readers)  # type: ignore
        except AttributeError:
            cls._csv_writers = dict()
            cls._csv_readers = dict()
        cls._csv_writers.update(cls._csv_custom_writers)
        cls._csv_readers.update(cls._csv_custom_readers)

    def csv_headers(self) -> list[str]:
        """Provide CSV headers as list"""
        return list(self.dict(exclude_unset=False, by_alias=False).keys())

    def _csv_write_fields(self, left: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Write CSV fields with custom encoders

        Returns columns_done, columns_left
        """
        res: dict[str, Any] = dict()
        # debug ("_csv_write_fields(): starting: %s", str(type(self)))

        for field, encoder in self._csv_writers.items():
            # debug ("class=%s, field=%s, encoder=%s", str(type(self)), field, str(encoder))
            try:
                if left[field] != "":
                    res[field] = encoder(left[field])
                del left[field]
            except KeyError as err:
                debug("field=%s not found: %s", field, err)

        return res, left

    def csv_row(self) -> dict[str, str | int | float | bool]:
        """CSVExportable._csv_row() takes care of str,int,float,bool,Enum, date and datetime.
        Class specific implementation needs to take care or serializing other fields."""
        res: dict[str, Any]
        res, left = self._csv_write_fields(self.dict(by_alias=False))

        for key in left.keys():
            value = getattr(self, key)
            if type(value) in {int, str, float, bool}:
                res[key] = value
            elif isinstance(value, Enum):
                res[key] = value.name
            elif isinstance(value, date):
                res[key] = value.isoformat()
            elif isinstance(value, datetime):
                res[key] = value.isoformat()
            else:
                error(f"no field encoder defined for field={key}")
                res[key] = None
        return self._clear_None(res)

    def _clear_None(self, res: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool]:
        out: dict[str, str | int | float | bool] = dict()
        for key, value in res.items():
            if value is None:
                out[key] = ""
            else:
                out[key] = value
        return out

    @classmethod
    def _csv_read_fields(cls, row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """read CSV fields with custom encoding.
        Returns read, unread fields as dict[str, Any]"""

        res: dict[str, Any] = dict()
        # if cls is CSVExportable:
        #     return res, row
        # debug ("%s._csv_read_fields(): %s", cls.__name__, str(row))
        for field, decoder in cls._csv_readers.items():
            # debug (
            #     "%s._csv_read_fields(): field=%s, decoder=%s, value=%s", cls.__name__, field, str(decoder), row[field]
            # )
            try:
                if row[field] != "":
                    res[field] = decoder(row[field])
                del row[field]
            except KeyError as err:
                debug("field=%s not found", field)
        # debug ("class=%s", str(cls))

        return res, row

    @classmethod
    def from_csv(cls, row: dict[str, Any]) -> Self | None:
        ## Does NOT WORK with Alias field names
        assert type(row) is dict, "row has to be type dict()"
        res: dict[str, Any]
        # debug("from_csv(): trying to import from: %s", str(row))
        res, row = cls._csv_read_fields(row)

        for field in row.keys():
            if row[field] != "":
                try:
                    field_type = cls.__fields__[field].type_
                    # debug ("field=%s, field_type=%s, value=%s", field, field_type, row[field])
                    if field_type in {int, float, str}:
                        res[field] = (field_type)(str(row[field]))
                    elif field_type is bool:
                        res[field] = row[field] == "True"
                    elif issubclass(field_type, Enum):
                        res[field] = field_type[str(row[field])]  ## Enums are stored by key, not value
                    elif field_type is date:
                        res[field] = date.fromisoformat(row[field])
                    elif field_type is datetime:
                        res[field] = datetime.fromisoformat(row[field])
                    else:
                        res[field] = (field_type)(str(row[field]))
                except KeyError:  # field not in cls
                    continue
                except AttributeError as err:
                    error(f"Class {cls.__name__}() does not have attribute: {field}")
                except Exception as err:
                    # debug ("%s raised, trying direct assignment: %s", type(err), err)
                    res[field] = str(row[field])
        try:
            # debug ("from_csv(): trying parse: %s", str(res))
            return cls.parse_obj(res)
        except ValidationError as err:
            error(f"Could not parse row ({row}): {err}")
        return None

    @classmethod
    async def import_csv(cls, filename: str) -> AsyncGenerator[Self, None]:
        """Import from filename, one model per line"""
        try:
            dialect: Type[Dialect] = excel
            debug("importing from CSV file: %s", filename)
            async with open(filename, mode="r", newline="") as f:
                async for row in AsyncDictReader(f, dialect=dialect):
                    # debug ("row: %s", row)
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
