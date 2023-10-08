import sys
import pytest  # type: ignore
from pathlib import Path
from datetime import datetime, timedelta
from itertools import pairwise, accumulate
from functools import cached_property
from math import ceil
from typing import Generator, Any
from multiprocessing import Process
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from socketserver import ThreadingMixIn
import click


from asyncio import Task, create_task, sleep, gather, timeout, TimeoutError
from random import random
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils.utils import ClickApp

logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


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


def test_1_ClickApp() -> None:
    """Test ClickApp() helper"""
    app = ClickApp(cli, "test-app")
    app.add_command(["more"])
    app.add_command(["more", "do", "--help"])
    app.add_command(["more", "dont"])
    app.add_command(["less", "--help"])
    app.add_command(["less", "do", "--help"])
    app.add_command(["less", "dont"])

    docs: str = app.mk_docs()
    assert len(docs) > 100, "making docs failed"
