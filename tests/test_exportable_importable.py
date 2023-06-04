import sys
import pytest  # type: ignore
from typing import Literal, Self
from pydantic import BaseModel, Field
from pathlib import Path
from time import time
from datetime import date
from asyncio.queues import Queue
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import JSONExportable, export_json, export, Idx
from pyutils import CSVExportable, CSVImportable, export_csv
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


def today() -> date:
    return date.today()


class TXTPerson(TXTExportable, TXTImportable, CSVExportable, CSVImportable, Importable):
    name: str = Field(default=...)
    height: float = Field(default=...)
    birthday: date = Field(default_factory=today)

    def txt_row(self, format: str = "") -> str:
        """export data as single row of text"""
        return f"{self.name}:{self.height}:{self.birthday.isoformat()}"

    @classmethod
    def from_txt(cls, text: str, **kwargs) -> Self:
        """Provide parse object from a line of text"""
        debug(f"line: {text}")
        n, h, bd = text.split(":")
        debug(f"name={n}, height={h}, birthday={bd}")
        return cls(name=n, height=float(h), birthday=date.fromisoformat(bd), **kwargs)

    def __hash__(self) -> int:
        """Make object hashable, but using index fields only"""
        return hash((self.name, self.birthday))

    def csv_headers(self) -> list[str]:
        """Provide CSV headers as list"""
        return ["name", "height", "birthday"]

    def _csv_row(self) -> dict[str, str | int | float | bool | None]:
        """Class specific implementation of CSV export as a single row"""
        return {
            "name": self.name,
            "height": self.height,
            "birthday": self.birthday.isoformat(),
        }


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
    res.append(TXTPerson(name="one", height=1.85))
    res.append(TXTPerson(name="two more", height=1.43, birthday="1977-07-23"))
    res.append(TXTPerson(name="Third 3.5", height=1.76, birthday=date.fromisoformat("2005-02-14")))
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
            imported.add(p_in)
    except Exception as err:
        assert False, f"failed to import test data: {err}"

    for data in txt_data:
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

    for data in txt_data:
        try:
            imported.remove(data)
        except Exception as err:
            assert False, f"could not export or import item: {data}: {err}: {imported}"

    assert len(imported) == 0, "Export or import failed"
