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

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


class CSVExportable(BaseModel):
    """Abstract class to provide CSV export"""

    _csv_custom_field_writers: ClassVar[MutableMapping[str, Callable[[Any], Any]]] = dict()
    _csv_custom_field_readers: ClassVar[MutableMapping[str, Callable[[Any], Any]]] = dict()

    def __init_subclass__(cls, **kwargs) -> None:
        """Use PEP 487 sub class constructor instead a custom one"""
        # make sure each subclass has its own transformation register
        cls._csv_custom_field_writers = dict()
        cls._csv_custom_field_readers = dict()

    def csv_headers(self) -> list[str]:
        """Provide CSV headers as list"""
        return list(self.dict(exclude_unset=False, by_alias=False).keys())

    def csv_row(self) -> dict[str, str | int | float | bool]:
        """Provide CSV row as a dict for csv.DictWriter"""
        return self._clear_None(self._csv_row())

    def _csv_write_custom_fields(self, _class: Type, left: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        res: dict[str, Any] = dict()
        debug("_csv_write_custom_fieldS(): starting: %s", str(_class))
        if _class is CSVExportable:
            debug("_csv_write_custom_fieldS(): stopping recursion")
            return res, left
        debug("_csv_write_custom_fieldS(): writing custom fields: %s", str(_class))
        for field, encoder in _class._csv_custom_field_writers.items():
            debug("class=%s, field=%s, encoder=%s", str(_class), field, str(encoder))
            try:
                if left[field] != "":
                    res[field] = encoder(left[field])
                del left[field]
            except KeyError as err:
                debug("field=%s not found", field)

        for _class in _class.__mro__[1:-1]:  # ugly hack since super() doesn't work
            try:
                # if the _class does not have _csv_read_custom_fields(), this raises AttributeError
                res_parent, left = _class._csv_read_custom_fields(left)  # type: ignore
                res.update(res_parent)
                return res, left
            except AttributeError:
                pass
        return res, left

    def _csv_row(self) -> dict[str, str | int | float | bool | None]:
        """CSVExportable._csv_row() takes care of str,int,float,bool,Enum, date and datetime.
        Class specific implementation needs to take care or serializing other fields."""
        res: dict[str, Any]
        res, left = self._csv_write_custom_fields(self.__class__, self.dict(by_alias=False))

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
        return res

    def _clear_None(self, res: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool]:
        out: dict[str, str | int | float | bool] = dict()
        for key, value in res.items():
            if value is None:
                out[key] = ""
            else:
                out[key] = value
        return out

    @classmethod
    def from_csv(cls, row: dict[str, Any]) -> Self | None:
        """Provide CSV row as a dict for csv.DictWriter"""
        try:
            row = cls._from_csv(row)
            return cls.parse_obj(row)
        except Exception as err:
            error(f"Could not parse row ({row}): {err}")
        return None

    @classmethod
    def _csv_read_custom_fields(cls, row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """read CSV fields with custom encoding.
        Returns read, unread fields as dict[str, Any]"""

        res: dict[str, Any] = dict()
        if cls is CSVExportable:
            return res, row
        for field, decoder in cls._csv_custom_field_readers.items():
            try:
                if row[field] != "":
                    res[field] = decoder(row[field])
                del row[field]
            except KeyError as err:
                debug("field=%s not found", field)

        debug("class=%s, parent=%s", str(cls), super())
        for _class in cls.__mro__[1:-1]:  # ugly hack since super() doesn't work
            try:
                # if the _class does not have _csv_read_custom_fields(), this raises AttributeError
                res_parent, row = _class._csv_read_custom_fields(row)  # type: ignore
                res.update(res_parent)
                return res, row
            except AttributeError:
                pass
        return res, row

    @classmethod
    def _from_csv(cls, row: dict[str, Any]) -> dict[str, Any]:
        ## Does NOT WORK with Alias field names
        assert type(row) is dict, "row has to be type dict()"
        res: dict[str, Any]
        res, row = cls._csv_read_custom_fields(row)

        for field in row.keys():
            if row[field] != "":
                try:
                    field_type = cls.__fields__[field].type_
                    debug("field=%s, field_type=%s, value=%s", field, field_type, row[field])
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
                    debug("%s raised, trying direct assignment: %s", type(err), err)
                    res[field] = str(row[field])

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
