import logging
from typing import (
    Optional,
    cast,
    Type,
    Any,
    Literal,
    TypeVar,
    ClassVar,
    Callable,
    Union,
    AsyncIterable,
    AsyncIterator,
    get_args,
)
from enum import Enum
from datetime import date, datetime
from collections.abc import MutableMapping
from pydantic import BaseModel
from asyncio import CancelledError
from aiofiles import open
from os.path import isfile, exists
from os import linesep
from aiocsv.writers import AsyncDictWriter
from csv import Dialect, excel, QUOTE_NONNUMERIC
from bson.objectid import ObjectId
from abc import abstractmethod

from .eventcounter import EventCounter
from .jsonexportable import JSONExportable
from .csvexportable import CSVExportable

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


DESCENDING: Literal[-1] = -1
ASCENDING: Literal[1] = 1
TEXT: Literal["text"] = "text"

Idx = Union[str, int, ObjectId]
BackendIndexType = Literal[-1, 1, "text"]
BackendIndex = tuple[str, BackendIndexType]
I = TypeVar("I", bound=Idx)


########################################################
#
# TXTExportable()
#
########################################################


class TXTExportable(BaseModel):
    """Abstract class to provide TXT export"""

    @abstractmethod
    def txt_row(self, format: str = "") -> str:
        """export data as single row of text"""
        raise NotImplementedError


########################################################
#
# CSVExportable()
#
########################################################


EXPORT_FORMAT = Literal["txt", "json", "csv"]
EXPORT_FORMATS = ["txt", "json", "csv"]


async def export_csv(
    iterable: AsyncIterable[CSVExportable], filename: str, force: bool = False, append: bool = False
) -> EventCounter:
    """Export data to a CSVfile"""
    debug("starting")
    # assert isinstance(Q, Queue), "Q has to be type of asyncio.Queue[CSVExportable]"
    assert type(filename) is str and len(filename) > 0, "filename has to be str"
    stats: EventCounter = EventCounter("CSV")
    try:
        dialect: Type[Dialect] = excel
        aiterator: AsyncIterator[CSVExportable] = aiter(iterable)
        exportable: CSVExportable | None = await anext(aiterator, None)

        if exportable is None:
            debug("empty iterable given")
            return stats
        fields: list[str] = exportable.csv_headers()

        if filename == "-":  # STDOUT
            try:
                # print header
                print(dialect.delimiter.join(fields))
                while exportable is not None:
                    try:
                        row: dict[str, str | int | float | bool] = exportable.csv_row()
                        print(dialect.delimiter.join([str(row[key]) for key in fields]))
                        stats.log("rows")
                    except KeyError as err:
                        error(f"CSVExportable object does not have field: {err}")
                        stats.log("errors")
                    exportable = await anext(aiterator, None)

                debug("export finished")
            except CancelledError as err:
                debug(f"Cancelled")

        else:  # File
            if not filename.lower().endswith("csv"):
                filename = f"{filename}.csv"
            file_exists: bool = isfile(filename)
            if exists(filename) and (not file_exists or not (force or append)):
                raise FileExistsError(f"Cannot export to {filename }")

            mode: Literal["w", "a"] = "w"
            if append and file_exists:
                mode = "a"
            else:
                append = False
            debug(f"opening {filename} for writing in mode={mode}")
            async with open(filename, mode=mode, newline="") as csvfile:
                try:
                    writer = AsyncDictWriter(csvfile, fieldnames=fields, dialect=dialect)
                    if not append:
                        await writer.writeheader()

                    while exportable is not None:
                        try:
                            # debug(f'Writing row: {exportable.csv_row()}')
                            await writer.writerow(exportable.csv_row())
                            stats.log("rows")
                        except Exception as err:
                            error(f"{err}")
                            stats.log("errors")
                        exportable = await anext(aiterator, None)

                except CancelledError as err:
                    debug(f"Cancelled")
                finally:
                    pass

    except Exception as err:
        error(f"{err}")
    return stats


async def export_json(
    iterable: AsyncIterable[JSONExportable], filename: str, force: bool = False, append: bool = False
) -> EventCounter:
    """Export data to a JSON file"""
    assert type(filename) is str and len(filename) > 0, "filename has to be str"
    stats: EventCounter = EventCounter("JSON")
    try:
        exportable: JSONExportable
        if filename == "-":
            async for exportable in iterable:
                try:
                    print(exportable.json_src())
                    stats.log("rows")
                except Exception as err:
                    error(f"{err}")
                    stats.log("errors")
        else:
            if not filename.lower().endswith("json"):
                filename = f"{filename}.json"
            file_exists: bool = isfile(filename)
            if exists(filename) and (not file_exists or not (force or append)):
                raise FileExistsError(f"Cannot export to {filename }")
            mode: Literal["w", "a"] = "w"
            if append and file_exists:
                mode = "a"
            async with open(filename, mode=mode) as txtfile:
                async for exportable in iterable:
                    try:
                        await txtfile.write(exportable.json_src() + linesep)
                        stats.log("rows")
                    except Exception as err:
                        error(f"{err}")
                        stats.log("errors")

    except CancelledError as err:
        debug(f"Cancelled")
    except Exception as err:
        error(f"{err}")
    return stats


async def export_txt(
    iterable: AsyncIterable[TXTExportable], filename: str, force: bool = False, append: bool = False
) -> EventCounter:
    """Export data to a text file"""
    assert type(filename) is str and len(filename) > 0, "filename has to be str"
    stats: EventCounter = EventCounter("Text")
    try:
        exportable: TXTExportable
        if filename == "-":
            async for exportable in iterable:
                try:
                    print(exportable.txt_row(format="rich"))
                    stats.log("rows")
                except Exception as err:
                    error(f"{err}")
                    stats.log("errors")
        else:
            if not filename.lower().endswith("txt"):
                filename = f"{filename}.txt"
            file_exists: bool = isfile(filename)
            if exists(filename) and (not file_exists or not (force or append)):
                raise FileExistsError(f"Cannot export to {filename }")
            mode: Literal["w", "a"] = "w"
            if append and file_exists:
                mode = "a"
            async with open(filename, mode=mode) as txtfile:
                async for exportable in iterable:
                    try:
                        await txtfile.write(exportable.txt_row() + linesep)
                        stats.log("rows")
                    except Exception as err:
                        error(f"{err}")
                        stats.log("errors")

    except CancelledError as err:
        debug(f"Cancelled")
    except Exception as err:
        error(f"{err}")
    return stats


async def export(
    iterable: AsyncIterable[CSVExportable] | AsyncIterable[TXTExportable] | AsyncIterable[JSONExportable],
    format: EXPORT_FORMAT,
    filename: str,
    force: bool = False,
    append: bool = False,
) -> EventCounter:
    """Export data to file or STDOUT"""
    debug("starting")
    stats: EventCounter = EventCounter("write")

    if filename != "-":
        for export_format in EXPORT_FORMATS:
            if filename.endswith(export_format) and export_format in get_args(EXPORT_FORMAT):
                format = cast(EXPORT_FORMAT, export_format)

    try:
        if format == "txt":
            stats.merge_child(
                await export_txt(iterable, filename=filename, force=force, append=append)  # type: ignore
            )
        elif format == "json":
            stats.merge_child(
                await export_json(iterable, filename=filename, force=force, append=append)  # type: ignore
            )
        elif format == "csv":
            stats.merge_child(
                await export_csv(iterable, filename=filename, force=force, append=append)  # type: ignore
            )
        else:
            raise ValueError(f"Unknown format: {format}")
    except Exception as err:
        stats.log("errors")
        error(f"{err}")
    finally:
        return stats
