import sys
import pytest  # type: ignore
from typing import Literal, Self
from pydantic import BaseModel, Field
from pathlib import Path
from time import time
from datetime import date, datetime
from asyncio.queues import Queue
from enum import Enum, StrEnum, IntEnum
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import JSONExportable, export_json, export, Idx
from pyutils import CSVExportable, export_csv
from pyutils import TXTExportable, TXTImportable, Importable
from pyutils import awrap

########################################################
#
# Test Plan
#
########################################################

# 1) Create instances, export as JSON, import back and compare
# 2) Create instances, export as CSV, import back and compare
# 3) Create instances, export as TXT, import back and compare

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


def epoch() -> int:
    return int(time())


class Eyes(StrEnum):
    blue = "Blue"
    grey = "Grey"
    brown = "Brown"


class Hair(IntEnum):
    black = 0
    brown = 1
    red = 2
    blonde = 3


class JSONChild(JSONExportable):
    name: str
    created: int = Field(default_factory=epoch)

    @property
    def index(self) -> Idx:
        """return backend index"""
        return self.name

    @property
    def indexes(self) -> dict[str, Idx]:
        """return backend indexes"""
        return {"name": self.index}


class JSONParent(JSONExportable, Importable):
    name: str
    amount: int = 0
    correct: bool = Field(default=False, alias="c")
    array: list[str] = list()
    child: JSONChild | None = None

    @property
    def index(self) -> Idx:
        """return backend index"""
        return self.name

    @property
    def indexes(self) -> dict[str, Idx]:
        """return backend indexes"""
        return {"name": self.index}


def today() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


def str2datetime(dt: str) -> datetime:
    debug("str2datetime(): %s", dt)
    return datetime.combine(date.fromisoformat(dt), datetime.min.time())


def datetime2str(dt: datetime) -> str:
    debug("datetime2str(): %s", dt)
    return dt.date().isoformat()


class TXTPerson(TXTExportable, TXTImportable, CSVExportable, Importable):
    name: str = Field(default=...)
    age: int = Field(default=...)
    height: float = Field(default=...)
    birthday: datetime = Field(default_factory=today)
    woman: bool = Field(default=False)
    hair: Hair = Field(default=Hair.brown)
    eyes: Eyes = Field(default=Eyes.blue)

    _csv_custom_field_readers = {"birthday": str2datetime}
    _csv_custom_field_writers = {"birthday": datetime2str}

    def txt_row(self, format: str = "") -> str:
        """export data as single row of text"""
        return f"{self.name}:{self.age}:{self.height}:{self.birthday.date().isoformat()}:{self.woman}:{self.hair.name}:{self.eyes.name}"

    @classmethod
    def from_txt(cls, text: str, **kwargs) -> Self:
        """Provide parse object from a line of text"""
        debug(f"line: {text}")
        n, a, h, bd, w, ha, e = text.split(":")
        debug("name=%s, age=%s height=%s, birthday=%s, woman=%s, hair=%s, eyes=%s", n, a, h, bd, w, ha, e)
        return cls(
            name=n,
            age=int(a),
            height=float(h),
            birthday=datetime.fromisoformat(bd),
            woman=(w == "True"),
            hair=Hair[ha],
            eyes=Eyes[e],
            **kwargs,
        )

    # def _csv_row(self) -> dict[str, str | int | float | bool | None]:
    #     row: dict[str, str | int | float | bool | None] = super()._csv_row()
    #     row["birthday"] = self.birthday.date().isoformat()
    #     debug("row: %s", str(row))
    #     return row

    def __hash__(self) -> int:
        """Make object hashable, but using index fields only"""
        return hash((self.name, self.birthday.date()))

    def csv_headers(self) -> list[str]:
        """Provide CSV headers as list"""
        return list(self.__fields__.keys())

    # def _csv_row(self) -> dict[str, str | int | float | bool | None]:
    #     """Class specific implementation of CSV export as a single row"""
    #     return {
    #         "name": self.name,
    #         "height": self.height,
    #         "birthday": self.birthday.isoformat(),
    #     }


@pytest.fixture
def json_data() -> list[JSONParent]:
    c1 = JSONChild(name="c1")
    c3 = JSONChild(name="c3")
    res: list[JSONParent] = list()
    res.append(JSONParent(name="P1", amount=1, array=["one", "two"], child=c1))
    res.append(JSONParent(name="P2", amount=-6, array=["three", "four"]))
    res.append(JSONParent(name="P3", amount=-6, child=c3))
    return res


@pytest.fixture
def txt_data() -> list[TXTPerson]:
    res: list[TXTPerson] = list()
    res.append(TXTPerson(name="Marie", age=0, height=1.85, woman=True, eyes=Eyes.brown, hair=Hair.red))
    res.append(
        TXTPerson(name="Jack Who", age=45, height=1.43, birthday=datetime.fromisoformat("1977-07-23"), eyes=Eyes.grey)
    )
    res.append(
        TXTPerson(
            name="James 3.5", age=18, height=1.76, birthday=datetime.fromisoformat("2005-02-14"), hair=Hair.blonde
        )
    )
    return res


@pytest.mark.asyncio
async def test_1_json_exportable(tmp_path: Path, json_data: list[JSONParent]):
    fn: str = f"{tmp_path.resolve()}/export.json"

    try:
        await export(awrap(json_data), "json", filename=fn)  # type: ignore
    except Exception as err:
        assert False, f"failed to export test data: {err}"

    imported: set[JSONParent] = set()
    try:
        async for p_in in JSONParent.import_file(fn):
            imported.add(p_in)
    except Exception as err:
        assert False, f"failed to import test data: {err}"

    for data in json_data:
        try:
            imported.remove(data)
        except Exception as err:
            assert False, f"could not export or import item: {data}: {err}"

    assert len(imported) == 0, "Export or import failed"


@pytest.mark.asyncio
async def test_2_txt_exportable_importable(tmp_path: Path, txt_data: list[TXTPerson]):
    fn: str = f"{tmp_path.resolve()}/export.txt"

    try:
        await export(awrap(txt_data), "txt", filename=fn)  # type: ignore
    except Exception as err:
        assert False, f"failed to export test data: {err}"

    imported: set[TXTPerson] = set()
    try:
        async for p_in in TXTPerson.import_file(fn):
            debug("import_txt(): %s", str(p_in))
            imported.add(p_in)
    except Exception as err:
        assert False, f"failed to import test data: {err}"

    assert len(imported) == len(
        txt_data
    ), f"failed to import all data from TXT file: {len(imported)} != {len(txt_data)}"

    for data in txt_data:
        debug("trying to remove data=%s from imported", str(data))
        try:
            imported.remove(data)
        except Exception as err:
            assert False, f"could not export or import item: {data}: {err}: {imported}"

    assert len(imported) == 0, "Export or import failed"


@pytest.mark.asyncio
async def test_3_csv_exportable_importable(tmp_path: Path, txt_data: list[TXTPerson]):
    fn: str = f"{tmp_path.resolve()}/export.csv"

    try:
        await export(awrap(txt_data), "csv", filename=fn)  # type: ignore
    except Exception as err:
        assert False, f"failed to export test data: {err}"

    imported: set[TXTPerson] = set()
    try:
        async for p_in in TXTPerson.import_file(fn):
            imported.add(p_in)
    except Exception as err:
        assert False, f"failed to import test data: {err}"

    assert len(imported) == len(txt_data), f"could not import all CSV data: {len(imported)} != {len(txt_data)}"
    for data_imported in imported:
        debug("hash(data_imported)=%d", hash(data_imported))
        try:
            if data_imported in txt_data:
                ndx: int = txt_data.index(data_imported)
                data = txt_data[ndx]
                assert data == data_imported, f"imported data different from original: {data_imported} != {data}"
                txt_data.pop(ndx)
            else:
                assert False, f"imported data not in the original: {data_imported}"
        except ValueError as err:
            assert False, f"export/import conversion error. imported data={data_imported} is not in input data"

    assert len(txt_data) == 0, f"could not import all the data correctly: {len(txt_data)} != 0"
