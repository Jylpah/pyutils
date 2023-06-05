import logging
from typing import cast, Type, Any, TypeVar, Self, AsyncGenerator, Callable, Sequence, Self, ClassVar, Optional
from abc import ABCMeta, abstractmethod
from collections.abc import MutableMapping
from pydantic import BaseModel, ValidationError
from aiocsv.readers import AsyncDictReader
from csv import Dialect, excel, QUOTE_NONNUMERIC
from datetime import date, datetime
from aiofiles import open
from enum import Enum
from .jsonexportable import JSONExportable
from .csvexportable import CSVExportable

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
            elif file.lower().endswith(".json") and issubclass(cls, JSONExportable):
                debug("importing from JSON file: %s", file)
                async for obj in cls.import_json(file, **kwargs):
                    yield obj
            elif file.lower().endswith(".csv") and issubclass(cls, CSVExportable):
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
