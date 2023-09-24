import sys
import pytest  # type: ignore
from typing import Literal, Self
from pydantic import Field
from pathlib import Path
from time import time
from datetime import date, datetime
from asyncio.queues import Queue
from enum import StrEnum, IntEnum
import json
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import JSONExportable, export_json, export, Idx
from pyutils import CSVExportable, export_csv
from pyutils import TXTExportable, TXTImportable, Importable
from pyutils import awrap, EventCounter
from pyutils.utils import get_type, get_subtype


########################################################
#
# Test Plan
#
########################################################

# 1) Create instances, export as JSON, import back and compare
# 2) Create instances, export as CSV, import back and compare
# 3) Create instances, export as TXT, import back and compare

logger = logging.getLogger()
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

    _exclude_unset = False

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

    _csv_custom_readers = {"birthday": str2datetime}
    _csv_custom_writers = {"birthday": datetime2str}

    def txt_row(self, format: str = "") -> str:
        """export data as single row of text"""
        return f"{self.name}:{self.age}:{self.height}:{self.birthday.date().isoformat()}:{self.woman}:{self.hair.name}:{self.eyes.name}"

    @classmethod
    def from_txt(cls, text: str, **kwargs) -> Self:
        """Provide parse object from a line of text"""
        debug(f"line: {text}")
        n, a, h, bd, w, ha, e = text.split(":")
        debug(
            "name=%s, age=%s height=%s, birthday=%s, woman=%s, hair=%s, eyes=%s",
            n,
            a,
            h,
            bd,
            w,
            ha,
            e,
        )
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

    def __hash__(self) -> int:
        """Make object hashable, but using index fields only"""
        return hash((self.name, self.birthday.date()))


def rm_parenthesis(name: str) -> str:
    return name.removesuffix("()")


def add_parenthesis(name: str) -> str:
    return f"{name}()"


class CSVPerson(TXTPerson):
    favorite_func: str

    _csv_custom_readers = {"favorite_func": add_parenthesis}
    _csv_custom_writers = {"favorite_func": rm_parenthesis}


class CSVChild(CSVPerson):
    favorite_func: str

    _csv_custom_readers = {"toy": str.lower}
    _csv_custom_writers = {"toy": str.upper}


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
def csv_data() -> list[CSVPerson]:
    res: list[CSVPerson] = list()
    res.append(
        CSVPerson(
            name="Marie",
            age=0,
            height=1.85,
            woman=True,
            eyes=Eyes.brown,
            hair=Hair.red,
            favorite_func="VLOOKUP()",
        )
    )
    res.append(
        CSVPerson(
            name="Jack Who",
            age=45,
            height=1.43,
            birthday=datetime.fromisoformat("1977-07-23"),
            eyes=Eyes.grey,
            favorite_func="INDEX()",
        )
    )
    res.append(
        CSVPerson(
            name="James 3.5",
            age=18,
            height=1.76,
            birthday=datetime.fromisoformat("2005-02-14"),
            hair=Hair.blonde,
            favorite_func="SUMPRODUCT()",
        )
    )
    return res


@pytest.fixture
def txt_data() -> list[TXTPerson]:
    res: list[TXTPerson] = list()
    res.append(
        TXTPerson(
            name="Marie", age=0, height=1.85, woman=True, eyes=Eyes.brown, hair=Hair.red
        )
    )
    res.append(
        TXTPerson(
            name="Jack Who",
            age=45,
            height=1.43,
            birthday=datetime.fromisoformat("1977-07-23"),
            eyes=Eyes.grey,
        )
    )
    res.append(
        TXTPerson(
            name="James 3.5",
            age=18,
            height=1.76,
            birthday=datetime.fromisoformat("2005-02-14"),
            hair=Hair.blonde,
        )
    )
    return res


@pytest.fixture
def test_model_ok() -> str:
    return "JSONParent"


@pytest.fixture
def test_model_not_found() -> str:
    return "JSONParent_NOT_FOUND"


@pytest.fixture
def test_model_nok() -> str:
    return "JSONParent::NOT_OK"


@pytest.mark.asyncio
async def test_1_json_exportable(tmp_path: Path, json_data: list[JSONParent]):
    fn: Path = tmp_path / "export.json"

    await export(awrap(json_data), format="json", filename="-")  # type: ignore
    await export(awrap(json_data), format="json", filename=fn)  # type: ignore
    await export(awrap(json_data), format="json", filename=str(fn.resolve()), force=True)  # type: ignore

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
async def test_2_json_exportable_include_exclude() -> None:
    # test for custom include/exclude
    parent = JSONParent(
        name="P3", amount=-6, correct=False, child=JSONChild(name="test")
    )

    parent_src: dict
    parent_db: dict
    parent_src = json.loads(parent.json_src())
    assert (
        "array" in parent_src
    ), "json_src() failed: _exclude_unset set 'False', 'array' excluded"
    parent_db = json.loads(parent.json_db())
    assert (
        "c" not in parent_db
    ), "json_db() failed: _exclude_defaults set 'True', 'c' included"

    for excl, incl in zip(["child", None], ["name", None]):
        kwargs: dict[str, set[str]] = dict()
        if excl is not None:
            kwargs["exclude"] = {excl}
        if incl is not None:
            kwargs["include"] = {incl}

        parent_src = json.loads(parent.json_src(fields=None, **kwargs))
        parent_db = json.loads(parent.json_db(fields=None, **kwargs))
        if excl is not None:
            assert (
                excl not in parent_db
            ), f"json_src() failed: excluded field {excl} included"
            assert (
                excl not in parent_src
            ), f"json_db() failed: excluded field {excl} included"
        if incl is not None:
            assert (
                incl in parent_src
            ), f"json_src() failed: included field {incl} excluded"
            assert (
                incl in parent_db
            ), f"json_db() failed: included field {incl} excluded"

    parent_src = json.loads(parent.json_src(fields=["name", "array"]))
    assert (
        "amount" not in parent_src
    ), f"json_src() failed: excluded field 'amount' included"
    assert "array" in parent_src, "json_src() failed: included field 'array' excluded"

    parent_db = json.loads(parent.json_db(fields=["name", "array"]))
    assert (
        "amount" not in parent_db
    ), f"json_db() failed: excluded field 'amount' included"
    assert "array" in parent_db, "json_db() failed: included field 'array' excluded"


@pytest.mark.asyncio
async def test_3_txt_exportable_importable(tmp_path: Path, txt_data: list[TXTPerson]):
    fn: Path = tmp_path / "export.txt"

    await export(awrap(txt_data), "txt", filename="-")  # type: ignore
    await export(awrap(txt_data), "txt", filename=fn)  # type: ignore
    await export(awrap(txt_data), format="txt", filename=str(fn.resolve()), force=True)  # type: ignore

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
async def test_4_csv_exportable_importable(tmp_path: Path, csv_data: list[CSVPerson]):
    fn: Path = tmp_path / "export.csv"

    await export(awrap(csv_data), "csv", filename="-")  # type: ignore
    await export(awrap(csv_data), "csv", filename=fn)  # type: ignore
    await export(awrap(csv_data), "csv", filename=str(fn.resolve()), force=True)  # type: ignore

    imported: set[CSVPerson] = set()
    try:
        async for p_in in CSVPerson.import_file(fn):
            debug("imported: %s", str(p_in))
            imported.add(p_in)
    except Exception as err:
        assert False, f"failed to import test data: {err}"

    assert len(imported) == len(
        csv_data
    ), f"could not import all CSV data: {len(imported)} != {len(csv_data)}"
    for data_imported in imported:
        debug("hash(data_imported)=%d", hash(data_imported))
        try:
            if data_imported in csv_data:
                ndx: int = csv_data.index(data_imported)
                data = csv_data[ndx]
                assert (
                    data == data_imported
                ), f"imported data different from original: {data_imported} != {data}"
                csv_data.pop(ndx)
            else:
                assert False, f"imported data not in the original: {data_imported}"
        except ValueError as err:
            assert (
                False
            ), f"export/import conversion error. imported data={data_imported} is not in input data"

    assert (
        len(csv_data) == 0
    ), f"could not import all the data correctly: {len(csv_data)} != 0"


def test_5_types(
    test_model_ok: str, test_model_nok: str, test_model_not_found: str
) -> None:
    """Test utils.get_type() and related functions"""
    assert (
        get_type(test_model_ok) is JSONParent
    ), f"failed to get type for '{test_model_ok}'"
    assert (
        get_type(test_model_nok) is None
    ), f"did not return None for NOT OK type: {test_model_nok}"
    assert (
        get_type(test_model_not_found) is None
    ), f"did not return None for non-existing type: {test_model_not_found}"
    assert (
        get_subtype(name=test_model_ok, parent=JSONExportable) is JSONParent
    ), f"failed to get sub type of 'JSONExportable' type for '{test_model_ok}'"
    assert (
        get_subtype(name=test_model_ok, parent=JSONChild) is None
    ), f"returned model that is not child of 'JSONChild' type for '{test_model_ok}'"
    assert (
        get_subtype(name=test_model_not_found, parent=JSONChild) is None
    ), f"returned model that is not child of 'JSONChild' type for '{test_model_not_found}'"
