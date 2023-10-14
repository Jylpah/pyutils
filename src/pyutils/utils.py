import logging
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any, Sequence, TypeVar, Iterator, AsyncGenerator, cast
from abc import ABC, abstractmethod
from re import compile
from itertools import islice
from aiofiles import open
from alive_progress import alive_bar  # type: ignore
from inspect import stack, getmembers, currentframe
from types import FrameType
import json
from time import time
from pathlib import Path
from aiohttp import ClientSession, ClientError, ClientResponseError, FormData
from pydantic import BaseModel, ValidationError
import asyncio
import string
from tempfile import gettempdir
from random import choices
from configparser import ConfigParser
from functools import wraps
from click import BaseCommand
from click.testing import CliRunner

from .eventcounter import EventCounter
from .urlqueue import UrlQueue, UrlQueueItemType, is_url


# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug

# Constants
MAX_RETRIES: int = 3
SLEEP: float = 1


T = TypeVar("T")


class Countable(ABC):
    @property
    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError


class ClickApp:
    """Helper class to write Markdown docs for a Click CLI program"""

    def __init__(self, cli: BaseCommand, name: str):
        self.cli: BaseCommand = cli
        self.name: str = name
        self.commands: list[list[str]] = list()
        self.add_command([])

    def add_command(self, command: list[str]):
        """Add a command without '--help'"""
        if len(command) > 0 and command[-1] == "--help":
            command = command[:-1]
        self.commands.append(command)

    def mk_docs(self) -> str:
        """Print help for all the commands"""
        res: list[str] = list()
        for command in self.commands:
            if len(command) > 0:
                res.append(f"### `{self.name} {' '.join(command)}` usage")
            else:
                res.append(f"## `{self.name}` usage")
            res.append("")
            res.append("```")
            result = CliRunner().invoke(
                self.cli, args=command + ["--help"], prog_name=self.name
            )
            res.append(result.stdout)
            res.append("```")
        return "\n".join(res)


##############################################
#
## Functions
#
##############################################


def coro(f):
    """decorator for async coroutines"""

    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


def str2path(filename: str | Path, suffix: str | None = None) -> Path:
    """convert filename (str) to pathlib.Path"""
    if isinstance(filename, str):
        filename = Path(filename)
    if suffix is not None and not filename.name.lower().endswith(suffix):
        filename = filename.with_suffix(suffix)
    return filename


def get_datestr(_datetime: datetime = datetime.now()) -> str:
    return _datetime.strftime("%Y%m%d_%H%M")


def epoch_now() -> int:
    return int(time())


def is_alphanum(string: str) -> bool:
    try:
        return not compile(r"[^a-zA-Z0-9_]").search(string)
    except:
        error(f"Illegal characters in the table name: {string}")
    return False


def chunker(it: Sequence[T], size: int) -> Iterator[list[T]]:
    """Makes fixed sized chunks out of Sequence"""
    assert size > 0, "size has to be positive"
    iterator: Iterator = iter(it)
    while chunk := list(islice(iterator, size)):
        yield chunk


def get_type(name: str, _globals: dict[str, Any] | None = None) -> type[object] | None:
    type_class: type[object]
    try:
        call_scope: FrameType | None
        if _globals is None:
            if (call_scope := currentframe()) is not None and (
                call_scope := call_scope.f_back
            ) is not None:
                # _globals = dict(getmembers(stack()[1][0]))["f_globals"]
                _globals = dict(getmembers(call_scope))["f_globals"]
            else:
                raise ValueError("could not get caller environment")
        if is_alphanum(name):
            assert _globals is not None, "could not read globals()"
            type_class = _globals[name]
        else:
            raise ValueError(f"model {name}() contains illegal characters")
        return type_class
    except ValueError as err:
        error(f"{err}")
    except KeyError as err:
        error(f"Could not find class {name}(): {err}")
    return None


def get_subtype(
    name: str, parent: type[T], _globals: dict[str, Any] | None = None
) -> Optional[type[T]]:
    type_class: type[object] | None
    call_scope: FrameType | None
    if _globals is None:
        if (call_scope := currentframe()) is not None and (
            call_scope := call_scope.f_back
        ) is not None:
            # _globals = dict(getmembers(stack()[1][0]))["f_globals"]
            _globals = dict(getmembers(call_scope))["f_globals"]
        else:
            raise ValueError("could not get caller environment")
    if (type_class := get_type(name, _globals)) is not None:
        if issubclass(type_class, parent):
            return type_class
    return None


def get_temp_filename(prefix: str = "", length: int = 10) -> Path:
    """Return temp filename as Path"""
    s = string.ascii_letters + string.digits
    return Path(gettempdir()) / (prefix + "".join(choices(s, k=length)))


async def alive_bar_monitor(
    monitor: list[Countable],
    title: str,
    total: int | None = None,
    wait: float = 0.5,
    batch: int = 1,
    *args,
    **kwargs,
) -> None:
    """Create a alive_progress bar for List[Countable]"""

    assert len(monitor) > 0, "'monitor' cannot be empty"

    prev: int = 0
    current: int = 0

    with alive_bar(total, *args, title=title, **kwargs) as bar:
        try:
            while total is None or current <= total:
                await asyncio.sleep(wait)
                current = 0
                for m in monitor:
                    current += m.count
                if current != prev:
                    bar((current - prev) * batch)
                prev = current
                if current == total:
                    break
        except asyncio.CancelledError:
            pass

    return None


async def post_url(
    session: ClientSession,
    url: str,
    headers: dict | None = None,
    data: FormData | dict[str, Any] | None = None,
    retries: int = MAX_RETRIES,
    **kwargs,
) -> str | None:
    """Do HTTP POST and return content as text"""
    assert session is not None, "Session must be initialized first"
    assert url is not None, "url cannot be None"
    for retry in range(1, retries + 1):
        debug(f"POST {url}: try {retry} / {retries}")
        try:
            async with session.post(
                url, headers=headers, data=data, **kwargs  # chunked=512 * 1024,
            ) as resp:
                debug(f"POST {url} HTTP response status {resp.status}/{resp.reason}")
                if resp.ok:
                    return await resp.text()
        except ClientError as err:
            debug(f"POST {url} Unexpected exception {err}")
        except asyncio.CancelledError as err:
            debug(f"Cancelled while still working: {err}")
            raise
        await asyncio.sleep(SLEEP)
    verbose(f"POST {url} FAILED")
    return None


async def get_url(
    session: ClientSession, url: str, retries: int = MAX_RETRIES
) -> str | None:
    """Retrieve (GET) an URL and return content as text"""
    assert session is not None, "Session must be initialized first"
    assert url is not None, "url cannot be None"

    # if not is_url(url):
    #     raise ValueError(f"URL is malformed: {url}")

    for retry in range(1, retries + 1):
        debug(f"GET {url} try {retry} / {retries}")
        try:
            async with session.get(url) as resp:
                debug(f"GET {url} HTTP response status {resp.status}/{resp.reason}")
                if resp.ok:
                    return await resp.text()
        except ClientError as err:
            debug(f"Could not retrieve URL: {url} : {err}")
        except asyncio.CancelledError as err:
            debug(f"Cancelled while still working: {err}")
            raise
        # except Exception as err:
        #     debug(f"Unexpected error {err}")
        await asyncio.sleep(SLEEP)
    verbose(f"Could not retrieve URL: {url}")
    return None


async def get_url_JSON(
    session: ClientSession, url: str, retries: int = MAX_RETRIES
) -> Any | None:
    """Get JSON from URL and return object."""

    assert session is not None, "session cannot be None"
    assert url is not None, "url cannot be None"

    try:
        if (content := await get_url(session, url, retries)) is not None:
            return json.loads(content)
    except ClientResponseError as err:
        debug(f"Client response error: {url}: {err}")
    # except Exception as err:
    #     debug(f"Unexpected error: {err}")
    return None


M = TypeVar("M", bound=BaseModel)


async def get_url_model(
    session: ClientSession, url: str, resp_model: type[M], retries: int = MAX_RETRIES
) -> Optional[M]:
    """Get JSON from URL and return object. Validate JSON against resp_model, if given."""
    assert session is not None, "session cannot be None"
    assert url is not None, "url cannot be None"
    content: str | None = None
    try:
        if (content := await get_url(session, url, retries)) is None:
            debug("get_url() returned None")
            return None
        return resp_model.model_validate_json(content)
    except ValueError as err:
        debug(
            f"{resp_model.__name__}: {url}: response={content}: Validation error={err}"
        )
    except Exception as err:
        debug(f"Unexpected error: {err}")
    return None


def set_config(
    config: ConfigParser,
    fallback: T,
    section: str,
    option: str,
    value: str | int | float | bool | None = None,
) -> T:
    """Helper for setting ConfigParser config params"""
    assert isinstance(
        config, ConfigParser
    ), "config argument has to be instance of ConfigParser"
    # opt_type: str | int | float | bool = str
    # if fallback is not None:
    #     opt_type = type(fallback)

    if not config.has_section(section):
        config[section] = {}
    if value is not None:
        config[section][option] = str(value)
    elif config.has_option(section=section, option=option):
        pass
    elif fallback is not None:
        config[section][option] = str(fallback)
    else:
        return None
    return cast(T, config[section][option])
