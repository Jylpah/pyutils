import logging
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from typing import (
    Optional,
    Any,
    Sequence,
    TypeVar,
    Iterator,
    AsyncGenerator,
)
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


##############################################
#
## Functions
#
##############################################


# def read_config(
#     config: str | None = None, files: list[str] = list()
# ) -> ConfigParser | None:
#     """Read config file and if found return a ConfigParser"""
#     if config is not None:
#         files = [config] + files
#     for fn in [expanduser(f) for f in files]:
#         try:
#             if isfile(fn):
#                 debug("reading config file: %s", fn)
#                 cfg = ConfigParser()
#                 cfg.read(fn)
#                 return cfg
#         except ConfigParserError as err:
#             error(f"could not parse config file: {fn}: {err}")
#             break
#     return None


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
        return resp_model.parse_raw(content)
    except ValidationError as err:
        debug(
            f"{resp_model.__name__}: {url}: response={content}: Validation error={err}"
        )
    except Exception as err:
        debug(f"Unexpected error: {err}")
    return None


# async def get_url_JSON_models(
#     session: ClientSession, url: str, item_model: type[M], retries: int = MAX_RETRIES
# ) -> Optional[list[M]]:
#     """Get a list of Pydantic models from URL. Validate JSON against resp_model, if given."""
#     assert session is not None, "session cannot be None"
#     assert url is not None, "url cannot be None"
#     content: str | None = None
#     try:
#         if (content := await get_url(session, url, retries)) is not None:
#             elems: list[Any] | None
#             if (elems := json.loads(content)) is not None:
#                 res: list[M] = list()
#                 for elem in elems:
#                     try:
#                         res.append(item_model.parse_obj(elem))
#                     except ValidationError as err:
#                         debug(f"Could not validate {elem}: {err}")
#                 return res
#     except Exception as err:
#         debug(f"Unexpected error: {err}")
#     return None


# async def get_urls(
#     session: ClientSession,
#     queue: UrlQueue,
#     stats: EventCounter = EventCounter(),
#     retries: int = MAX_RETRIES,
# ) -> AsyncGenerator[tuple[str, str], None]:
#     """Async Generator to retrieve URLs read from an async Queue"""

#     assert session is not None, "Session must be initialized first"
#     assert queue is not None, "Queue must be initialized first"

#     while True:
#         try:
#             url_item: UrlQueueItemType = await queue.get()
#             url: str = url_item[0]
#             retry: int = url_item[1]
#             if retry > retries:
#                 debug(f"URL has been tried more than {retries} times: {url}")
#                 continue
#             if retry > 0:
#                 debug(f"Retrying URL ({retry}/{retries}): {url}")
#             else:
#                 debug(f"Retrieving URL: {url}")

#             async with session.get(url) as resp:
#                 if resp.status == 200:
#                     debug(f"HTTP request OK/{resp.status}: {url}")
#                     stats.log("OK")
#                     yield await resp.text(), url
#                 else:
#                     error(f"HTTP error {resp.status}: {url}")
#                     if retry < retries:
#                         retry += 1
#                         stats.log("retries")
#                         await queue.put(url, retry)
#                     else:
#                         error(f"Could not retrieve URL: {url}")
#                         stats.log("failed")

#         except asyncio.CancelledError as err:
#             debug(f"Async operation has been cancelled. Ending loop.")
#             break


# async def get_urls_JSON(
#     session: ClientSession,
#     queue: UrlQueue,
#     stats: EventCounter = EventCounter(),
#     retries: int = MAX_RETRIES,
# ) -> AsyncGenerator[tuple[Any, str], None]:
#     """Async Generator to retrieve JSON from URLs read from an async Queue"""

#     assert session is not None, "Session must be initialized first"
#     assert queue is not None, "Queue must be initialized first"

#     async for content, url in get_urls(
#         session, queue=queue, stats=stats, retries=retries
#     ):
#         try:
#             yield await json.loads(content), url
#         except ClientResponseError as err:
#             debug(f"Client response error: {url}: {err}")
#         except Exception as err:
#             debug(f"Unexpected error: {err}")


# async def get_urls_JSON_models(
#     session: ClientSession,
#     queue: UrlQueue,
#     resp_model: type[M],
#     stats: EventCounter = EventCounter(),
#     retries: int = MAX_RETRIES,
# ) -> AsyncGenerator[tuple[M, str], None]:
#     """Async Generator to retrieve JSON from URLs read from an async Queue"""

#     assert session is not None, "Session must be initialized first"
#     assert queue is not None, "Queue must be initialized first"

#     async for content, url in get_urls(
#         session, queue=queue, stats=stats, retries=retries
#     ):
#         try:
#             yield resp_model.parse_raw(content), url
#         except ValidationError as err:
#             debug(f"{resp_model.__name__}(): Validation error: {url}: {err}")
#         except Exception as err:
#             debug(f"Unexpected error: {err}")


# # def mk_id(account_id: int, last_battle_time: int, tank_id: int = 0) -> ObjectId:
# # 	return ObjectId(hex(account_id)[2:].zfill(10) + hex(tank_id)[2:].zfill(6) + hex(last_battle_time)[2:].zfill(8))


def set_config(
    config: ConfigParser,
    section: str,
    option: str,
    value: Any = None,
    fallback: str | int | float | bool | None = None,
) -> None:
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
    elif not (fallback is None or config.has_option(section=section, option=option)):
        config[section][option] = str(fallback)
