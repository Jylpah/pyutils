import sys
from typing import Annotated, Optional, List
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
    is_alphanum,
    get_type,
    get_subtype,
)

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

