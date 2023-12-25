import sys
import pytest  # type: ignore
from pathlib import Path
from os import makedirs
from fnmatch import fnmatch, fnmatchcase
import logging


logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import FileQueue  # noqa: E402

########################################################
#
# Test Plan
#
########################################################

# 1) Parse test replay
# 2) Export test replays
# 3) Re-import test replays

########################################################
#
# Fixtures
#
########################################################

FIXTURE_DIR = Path(__file__).parent

TEST_BASE = Path("06_FileQueue")


@pytest.fixture
def file_tree() -> list[Path]:
    FILE_TREE: list[Path] = [
        TEST_BASE / "1" / "20200229_2321__jylpah_E-50_fort.wotbreplay.json",
        TEST_BASE / "1" / "20200229_2324__jylpah_E-50_erlenberg.wotbreplay.json",
        TEST_BASE / "1" / "20200229_2328__jylpah_E-50_grossberg.wotbreplay",
        TEST_BASE / "1" / "20200229_2332__jylpah_E-50_lumber.wotbreplay",
        TEST_BASE / "2" / "3" / "20200229_2337__jylpah_E-50_skit.wotbreplay.json",
        TEST_BASE / "2" / "3" / "20200229_2341__jylpah_E-50_erlenberg.wotbreplay.json",
        TEST_BASE / "2" / "3" / "20200229_2344__jylpah_E-50_rock.wotbreplay",
        TEST_BASE / "2" / "4" / "20200229_2341__jylpah_E-50_erlenberg.wotbreplay.json",
        TEST_BASE / "2" / "4" / "20200229_2344__jylpah_E-50_rock.wotbreplay",
        TEST_BASE / "20200229_2349__jylpah_E-50_himmelsdorf.wotbreplay.json",
        TEST_BASE / "20200229_2353__jylpah_E-50_fort.wotbreplay.json",
        TEST_BASE / "20200301_0022__jylpah_E-50_rudniki.wotbreplay",
        TEST_BASE / "20200301_0026__jylpah_E-50_himmelsdorf.wotbreplay.JSON",
        TEST_BASE / "20200301_0030__jylpah_E-50_rift.wotbreplay",
        TEST_BASE / "20200301_0035__jylpah_E-50_rock.wotbreplay.JSON",
        TEST_BASE / "20200301_0039__jylpah_E-50_desert_train.wotbreplay.json",
    ]
    return FILE_TREE


def mk_files(base: Path, files: list[Path]) -> None:
    for file in files:
        new: Path = base / file
        makedirs(new.parent, mode=0o700, exist_ok=True)
        open(new, "a").close()


def count_matches(
    files: list[Path], filter="*", exclude: bool = False, case_sensitive: bool = True
) -> int:
    count: int = 0
    for file in files:
        if case_sensitive:
            if fnmatch(file.name, filter) != exclude:
                count += 1
        else:
            if fnmatchcase(file.name, filter) != exclude:
                count += 1
    return count


########################################################
#
# Tests
#
########################################################


@pytest.mark.asyncio
async def test_1_filter(tmp_path: Path, file_tree: list[Path]) -> None:
    mk_files(tmp_path, files=file_tree)

    for filter, exclude, case_sensitive in zip(
        ["*.json", "*.wotbreplay"], [True, False], [True, False]
    ):
        fq = FileQueue(
            base=tmp_path, filter=filter, exclude=exclude, case_sensitive=case_sensitive
        )
        await fq.mk_queue([str(tmp_path)])
        matches: int = count_matches(
            file_tree, filter=filter, exclude=exclude, case_sensitive=case_sensitive
        )
        assert (
            fq.qsize() == matches
        ), f"incorrect file count: found={fq.qsize()} created={matches}"
