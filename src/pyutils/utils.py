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

import json
from time import time
from pathlib import Path
from aiohttp import ClientSession, ClientError, ClientResponseError
from pydantic import BaseModel, ValidationError
from asyncio import sleep, CancelledError
import string
from tempfile import gettempdir
from random import choices

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


def get_type(name: str) -> type[object] | None:
    type_class: type[object]
    try:
        if is_alphanum(name):
            type_class = globals()[name]
        else:
            raise ValueError(f"model {name}() contains illegal characters")
        return type_class
    except Exception as err:
        error(f"Could not find class {name}(): {err}")
    return None


def get_sub_type(name: str, parent: type[T]) -> Optional[type[T]]:
    if (model := get_type(name)) is not None:
        if issubclass(model, parent):
            return model
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
                await sleep(wait)
                current = 0
                for m in monitor:
                    current += m.count
                if current != prev:
                    bar((current - prev) * batch)
                prev = current
                if current == total:
                    break
        except CancelledError:
            pass

    return None


async def get_url(
    session: ClientSession, url: str, max_retries: int = MAX_RETRIES
) -> str | None:
    """Retrieve (GET) an URL and return JSON object"""
    assert session is not None, "Session must be initialized first"
    assert url is not None, "url cannot be None"

    if not is_url(url):
        raise ValueError(f"URL is malformed: {url}")

    for retry in range(1, max_retries + 1):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    debug(f"HTTP request OK: {url}")
                    return await resp.text()
                else:
                    debug(f"HTTP error {resp.status}: {url}")
                if retry == max_retries:
                    break
                debug(f"Retrying URL [ {retry}/{max_retries} ]: {url}")
            await sleep(SLEEP)

        except ClientError as err:
            debug(f"Could not retrieve URL: {url} : {err}")
        except CancelledError as err:
            debug(f"Cancelled while still working: {err}")
            break
        except Exception as err:
            debug(f"Unexpected error {err}")
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
            return await json.loads(content)
    except ClientResponseError as err:
        debug(f"Client response error: {url}: {err}")
    except Exception as err:
        debug(f"Unexpected error: {err}")
    return None


M = TypeVar("M", bound=BaseModel)


async def get_url_JSON_model(
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


async def get_url_JSON_models(
    session: ClientSession, url: str, item_model: type[M], retries: int = MAX_RETRIES
) -> Optional[list[M]]:
    """Get a list of Pydantic models from URL. Validate JSON against resp_model, if given."""
    assert session is not None, "session cannot be None"
    assert url is not None, "url cannot be None"
    content: str | None = None
    try:
        if (content := await get_url(session, url, retries)) is not None:
            elems: list[Any] | None
            if (elems := json.loads(content)) is not None:
                res: list[M] = list()
                for elem in elems:
                    try:
                        res.append(item_model.parse_obj(elem))
                    except ValidationError as err:
                        debug(f"Could not validate {elem}: {err}")
                return res
    except Exception as err:
        debug(f"Unexpected error: {err}")
    return None


async def get_urls(
    session: ClientSession,
    queue: UrlQueue,
    stats: EventCounter = EventCounter(),
    max_retries: int = MAX_RETRIES,
) -> AsyncGenerator[tuple[str, str], None]:
    """Async Generator to retrieve URLs read from an async Queue"""

    assert session is not None, "Session must be initialized first"
    assert queue is not None, "Queue must be initialized first"

    while True:
        try:
            url_item: UrlQueueItemType = await queue.get()
            url: str = url_item[0]
            retry: int = url_item[1]
            if retry > max_retries:
                debug(f"URL has been tried more than {max_retries} times: {url}")
                continue
            if retry > 0:
                debug(f"Retrying URL ({retry}/{max_retries}): {url}")
            else:
                debug(f"Retrieving URL: {url}")

            async with session.get(url) as resp:
                if resp.status == 200:
                    debug(f"HTTP request OK/{resp.status}: {url}")
                    stats.log("OK")
                    yield await resp.text(), url
                else:
                    error(f"HTTP error {resp.status}: {url}")
                    if retry < max_retries:
                        retry += 1
                        stats.log("retries")
                        await queue.put(url, retry)
                    else:
                        error(f"Could not retrieve URL: {url}")
                        stats.log("failed")

        except CancelledError as err:
            debug(f"Async operation has been cancelled. Ending loop.")
            break


async def get_urls_JSON(
    session: ClientSession,
    queue: UrlQueue,
    stats: EventCounter = EventCounter(),
    max_retries: int = MAX_RETRIES,
) -> AsyncGenerator[tuple[Any, str], None]:
    """Async Generator to retrieve JSON from URLs read from an async Queue"""

    assert session is not None, "Session must be initialized first"
    assert queue is not None, "Queue must be initialized first"

    async for content, url in get_urls(
        session, queue=queue, stats=stats, max_retries=max_retries
    ):
        try:
            yield await json.loads(content), url
        except ClientResponseError as err:
            debug(f"Client response error: {url}: {err}")
        except Exception as err:
            debug(f"Unexpected error: {err}")


async def get_urls_JSON_models(
    session: ClientSession,
    queue: UrlQueue,
    resp_model: type[M],
    stats: EventCounter = EventCounter(),
    max_retries: int = MAX_RETRIES,
) -> AsyncGenerator[tuple[M, str], None]:
    """Async Generator to retrieve JSON from URLs read from an async Queue"""

    assert session is not None, "Session must be initialized first"
    assert queue is not None, "Queue must be initialized first"

    async for content, url in get_urls(
        session, queue=queue, stats=stats, max_retries=max_retries
    ):
        try:
            yield resp_model.parse_raw(content), url
        except ValidationError as err:
            debug(f"{resp_model.__name__}(): Validation error: {url}: {err}")
        except Exception as err:
            debug(f"Unexpected error: {err}")


# def mk_id(account_id: int, last_battle_time: int, tank_id: int = 0) -> ObjectId:
# 	return ObjectId(hex(account_id)[2:].zfill(10) + hex(tank_id)[2:].zfill(6) + hex(last_battle_time)[2:].zfill(8))
