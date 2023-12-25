from enum import Enum
from math import ceil
import sys
from typing import Annotated, Optional, List, Sequence
import pytest  # type: ignore
from pathlib import Path
import click
from typer import Typer, Context, Option

import logging

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils.utils import (
    ClickHelpGen,
    Countable,
    TyperHelpGen,
    chunker,
    is_valid_obj,
    get_type,
    get_subtype,
)
from pyutils import awrap

logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug

########################################################
#
# Click test app
#
########################################################


@click.group(help="CLI tool test")
@click.option(
    "--normal",
    "LOG_LEVEL",
    flag_value=logging.WARNING,
    default=True,
    help="default verbosity",
)
@click.option("--verbose", "LOG_LEVEL", flag_value=logging.INFO, help="verbose logging")
@click.option("--debug", "LOG_LEVEL", flag_value=logging.DEBUG, help="debug logging")
@click.option(
    "--log", type=click.Path(path_type=Path), default=None, help="log to FILE"
)
@click.pass_context
def cli(
    ctx: click.Context,
    LOG_LEVEL: int = logging.WARNING,
    log: Path | None = None,
) -> None:
    """CLI app to extract WoT Blitz tankopedia and maps for other tools"""
    global logger, error, debug, verbose, message
    click.echo(f"LOG_LEVEL={LOG_LEVEL}, log={log}")


@cli.group(help="Test more")
@click.option(
    "-f",
    "--force",
    flag_value=True,
    default=False,
    help="Force testing",
)
@click.pass_context
def more(ctx: click.Context, force: bool = False) -> None:
    click.echo(f"more: force={force}")


@more.command(help="do test")
def do():
    click.echo("do")


@more.command(help="don't test")
def dont():
    click.echo("dont")


@cli.group(help="Test less")
@click.option(
    "-f",
    "--force",
    flag_value=True,
    default=False,
    help="Force testing",
)
@click.pass_context
def less(ctx: click.Context, force: bool = False) -> None:
    click.echo(f"less: force={force}")


@less.command(name="do", help="do test")
def do_less():
    click.echo("do")


@less.command(name="dont", help="don't test")
def dont_less():
    click.echo("dont")


def test_1_ClickHelpGen() -> None:
    """Test ClickHelpGen() helper"""
    app = ClickHelpGen(cli, "test-app")
    app.add_command(["more"])
    app.add_command(["more", "do", "--help"])
    app.add_command(["more", "dont"])
    app.add_command(["less", "--help"])
    app.add_command(["less", "do", "--help"])
    app.add_command(["less", "dont"])

    docs: str = app.mk_docs()
    assert len(docs) > 100, "making docs failed"


########################################################
#
# Typer test app
#
########################################################

app: Typer = Typer()


@app.callback()
def main(
    ctx: Context,
    print_verbose: Annotated[
        bool,
        Option(
            "--verbose",
            "-v",
            show_default=False,
            metavar="",
            help="verbose logging",
        ),
    ] = False,
    print_debug: Annotated[
        bool,
        Option(
            "--debug",
            show_default=False,
            metavar="",
            help="debug logging",
        ),
    ] = False,
    log: Annotated[Optional[Path], Option(metavar="FILE", help="log to FILE")] = None,
) -> None:
    """CLI app to extract WoT Blitz tankopedia and maps for other tools"""
    global logger, error, debug, verbose, message
    typer.echo(f"verbose={print_verbose}, debug={print_debug}, log={log}")


more_app = Typer()
app.add_typer(more_app, name="more")


@more_app.callback()
def typer_more(ctx: Context, force: bool = False) -> None:
    """Test more"""
    typer.echo(f"more: force={force}")


@more_app.command("do", help="do test")
def more_do():
    typer.echo("do")


@more_app.command("dont", help="don't test")
def more_dont():
    typer.echo("dont")


less_app = Typer()
app.add_typer(less_app, name="less")


@less_app.callback()
def typer_less(ctx: Context, force: bool = False) -> None:
    """Test less"""
    typer.echo(f"less: force={force}")


@less_app.command("do", help="do test")
def less_do():
    typer.echo("do")


@less_app.command("dont", help="don't test")
def less_dont():
    typer.echo("dont")


def test_2_TyperHelpGen() -> None:
    """Test TyperHelpGen() helper"""
    global app
    typer_app = TyperHelpGen(app, "test-app")
    typer_app.add_command(["more"])
    typer_app.add_command(["more", "do", "--help"])
    typer_app.add_command(["more", "dont"])
    typer_app.add_command(["less", "--help"])
    typer_app.add_command(["less", "do", "--help"])
    typer_app.add_command(["less", "dont"])

    docs: str = typer_app.mk_docs()
    assert len(docs) > 100, "making docs failed"


########################################################
#
# test Countable()
#
########################################################


class _TestCountable(Countable):
    def __init__(self, lst: List[int] = list()) -> None:
        super().__init__()
        self.lst: List[int] = lst

    @property
    def count(self) -> int:
        return len(self.lst)


class _TestCountableChild(_TestCountable):
    def items(self) -> List[int]:
        return self.lst


def test_3_Countable() -> None:
    """Test Countable"""

    l = _TestCountable([1, 2, 3, 4, 5])

    assert l.count == 5, "count returned incorrect value"


def test_4_is_valid_obj() -> None:
    """Test is_valid_obj()"""
    test_ok: str = "234asefw43rt_wq343wq4_234_234_"
    assert is_valid_obj(test_ok), f"test failed for {test_ok}"

    test_nok: str = "23.34-"
    assert not is_valid_obj(test_nok), f"false positive for {test_nok}"


def test_5_chunker() -> None:
    i: int = 0
    size: int = 52
    chunk_size: int = 5

    for chunk in chunker(range(size), chunk_size):
        if i < size // chunk_size:
            assert (
                len(chunk) == chunk_size
            ), f"chunk size is wrong: {len(chunk)} != {chunk_size}"
        else:
            assert (
                len(chunk) == size - (size // chunk_size) * chunk_size
            ), "last chunk is wrong size: {len(chunk)}"
        i += 1

    assert i == ceil(size / chunk_size), "incorrect number of chunks"


########################################################
#
# test get_type(), get_sub_type()
#
########################################################


@pytest.fixture
def test_model_ok() -> str:
    return "_TestCountableChild"


@pytest.fixture
def test_model_not_found() -> str:
    return "_TestCountable_NOT_FOUND"


@pytest.fixture
def test_model_nok() -> str:
    return "_TestCountable::NOT_OK"


def test_6_get_type(
    test_model_ok: str, test_model_nok: str, test_model_not_found: str
) -> None:
    """Test utils.get_type() and related functions"""
    assert (
        get_type(test_model_ok) is _TestCountableChild
    ), f"failed to get type for '{test_model_ok}'"
    assert (
        get_type(test_model_nok) is None
    ), f"did not return None for NOT OK type: {test_model_nok}"
    assert (
        get_type(test_model_not_found) is None
    ), f"did not return None for non-existing type: {test_model_not_found}"


def test_7_get_subtype(
    test_model_ok: str, test_model_nok: str, test_model_not_found: str
) -> None:
    """Test utils.get_subtype() and related functions"""

    assert (
        get_subtype(name=test_model_ok, parent=_TestCountable) is _TestCountableChild
    ), f"failed to get sub type of '_TestCountable' type for '{test_model_ok}'"
    assert (
        get_subtype(name=test_model_ok, parent=Enum) is None
    ), f"returned model that is not child of '_TestCountableChild' type for '{test_model_ok}': {get_subtype(name=test_model_ok, parent=_TestCountableChild)}"
    assert (
        get_subtype(name=test_model_not_found, parent=_TestCountable) is None
    ), f"returned model that is not child of '_TestCountableChild' type for '{test_model_not_found}'"


@pytest.mark.asyncio
async def test_8_awrap() -> None:
    t: Sequence[int] = range(10)
    s: int = -1
    async for i in awrap(t):
        assert i == s + 1, f"invalid value returned: {i} != {s+1}"
        s = i
