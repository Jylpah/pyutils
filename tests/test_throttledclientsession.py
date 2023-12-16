import sys
import pytest  # type: ignore
from pathlib import Path
from datetime import datetime
from itertools import pairwise, accumulate
from functools import cached_property
from math import ceil
from typing import Generator, Any
from multiprocessing import Process
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from socketserver import ThreadingMixIn

# from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from asyncio.queues import QueueEmpty, QueueFull
from asyncio import Task, create_task, sleep, gather, timeout, TimeoutError
from random import random
import logging


sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import (
    ThrottledClientSession,
    epoch_now,
    get_url_JSON,
    post_url,
)


HOST: str = "localhost"
PORT: int = 8889
MODEL_PATH: str = "/JSONParent"
RATE_FAST: float = 100
RATE_SLOW: float = 0.6

N_FAST: int = 500
N_SLOW: int = 5

THREADS: int = 5
# N : int = int(1e10)

logger = logging.getLogger()
message = logger.warning


class _HttpRequestHandler(BaseHTTPRequestHandler):
    """HTTPServer mock request handler"""

    @cached_property
    def url(self):
        return urlparse(self.path)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        """Handle GET requests"""
        self.send_response(200)
        self.send_header("Content-Type", "application/txt")
        self.end_headers()
        self.wfile.write(datetime.utcnow().isoformat().encode())

    # def do_POST(self) -> None:  # pylint: disable=invalid-name
    #     """Handle POST requests
    #     DOES NOT WORK YET"""
    #     message(f"POST @ {datetime.utcnow()}")
    #     self.send_response(200)
    #     self.send_header("Content-Type", "application/txt")
    #     self.end_headers()
    #     if self.url.path == MODEL_PATH:
    #         message(f"POST {self.url.path} @ {datetime.utcnow()}")
    #         if (
    #             _ := JSONParent.model_validate_json(self.rfile.read().decode())
    #         ) is not None:
    #             # assert False, "POST read content OK"
    #             message(f"POST OK @ {datetime.utcnow()}")
    #             self.wfile.write("OK".encode())
    #             # assert False, "POST did write"
    #         else:
    #             # assert False, "POST read content ERROR"
    #             message(f"POST ERROR @ {datetime.utcnow()}")
    #             self.wfile.write("ERROR".encode())
    #     # assert False, "do_POST()"

    def log_request(self, code=None, size=None):
        """Don't log anything"""
        pass


class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass


class _HttpServer(Process):
    def __init__(self, host: str = HOST, port: int = PORT):
        super().__init__()
        self._host: str = host
        self._port: int = port

    def run(self):
        server = ThreadingSimpleServer((self._host, self._port), _HttpRequestHandler)
        server.serve_forever()


def max_rate(timings: list[float], rate: float) -> float:
    """Read list[datetime] and return number of timings,
    average rate and maximum rate"""
    assert rate > 0, f"rate must be positive: {rate}"
    diffs: list[float] = [x1 - x0 for (x0, x1) in pairwise(timings)]
    cums: list[float] = [0] + list(accumulate(diffs))
    window: int = max(int(rate) - 1, 1)
    min_time: float = min(
        [cums[i + window] - cums[i] for i in range(len(cums) - window)]
    )
    return (window) / min_time


def avg_rate(timings: list[float]) -> float:
    n: int = len(timings) - 1  # the last request is not measured in total
    total: float = timings[-1] - timings[0]
    return n / total


async def _get(url: str, rate: float, N: int) -> list[float]:
    """Test timings of N/sec get"""
    timings: list[float] = list()
    async with ThrottledClientSession(rate_limit=rate) as session:
        for _ in range(N):
            async with session.get(url, ssl=False) as resp:
                assert resp.status == 200, f"request failed, HTTP STATUS={resp.status}"
                timings.append(datetime.fromisoformat(await resp.text()).timestamp())
    return timings


@pytest.fixture(scope="module")
def server_host() -> str:
    return HOST


@pytest.fixture(scope="module")
def server_port() -> int:
    return PORT


@pytest.fixture(scope="module")
def server_url(server_host: str, server_port: int) -> Generator[str, None, None]:
    # start HTTP server
    host: str = server_host
    port: int = server_port
    server: _HttpServer = _HttpServer(host=host, port=server_port)
    server.start()
    yield f"http://{host}:{port}/"
    # clean up
    server.terminate()


@pytest.fixture()
def model_path() -> str:
    return MODEL_PATH


@pytest.mark.timeout(20)
@pytest.mark.asyncio
async def test_1_fast_get(server_url: str) -> None:
    """Test timings of N/sec get"""
    rate_limit: float = RATE_FAST
    N: int = N_FAST
    timings: list[float] = await _get(server_url, rate=rate_limit, N=N)
    rate_max: float = max_rate(timings, rate_limit)
    rate_avg: float = avg_rate(timings)
    message(
        f"rate limit: {rate_limit:.2f}, avg rate: {rate_avg:.2f}, max rate: {rate_max:.2f}"
    )
    assert (
        rate_avg <= rate_limit * 1.05
    ), f"Avg. rate is above rate_limit: {rate_avg:.2f} > {rate_limit:.2f}"
    assert (
        rate_max <= rate_limit * 1.1
    ), f""""max_rate is above rate_limit: {rate_max:.2f} > {rate_limit:.2f}\n
                                        {', '.join([str(t) for t in timings])}"""


@pytest.mark.timeout(40)
@pytest.mark.asyncio
async def test_2_slow_get(server_url: str) -> None:
    """Test timings of N/sec get"""
    rate_limit: float = RATE_SLOW
    N: int = N_SLOW
    timings: list[float] = await _get(server_url, rate=rate_limit, N=N)
    rate_max: float = max_rate(timings, rate_limit)
    rate_avg: float = avg_rate(timings)
    message(
        f"rate limit: {rate_limit:.2f}, avg rate: {rate_avg:.2f}, max rate: {rate_max:.2f}"
    )
    assert (
        rate_avg <= rate_limit * 1.05
    ), f"Avg. rate is above rate_limit: {rate_avg:.2f} > {rate_limit:.2f}"
    assert (
        rate_max <= rate_limit * 1.1
    ), f""""max_rate is above rate_limit: {rate_max:.2f} > {rate_limit:.2f}\n
                                        {', '.join([str(t) for t in timings])}"""


# @pytest.mark.timeout(20)
# @pytest.mark.asyncio
# async def test_3_get_json(server_url: str, model_path: str) -> None:
#     """Test get_url_JSON()"""
#     rate_limit: float = RATE_SLOW
#     N: int = N_SLOW
#     url: str = server_url + model_path
#     res: Any | None
#     async with ThrottledClientSession(rate_limit=rate_limit) as session:
#         for _ in range(N):
#             if (res := await get_url_JSON(session=session, url=url, retries=2)) is None:
#                 assert False, "get_url_JSON() returned None"
#             if (_ := JSONParent.model_validate(res)) is None:
#                 assert False, "could not parse returned model"


# @pytest.mark.timeout(10)
# @pytest.mark.asyncio
# async def test_5_post_json(server_url: str, model_path: str) -> None:
#     """Test post_url_JSON()"""
#     rate_limit: float = RATE_FAST
#     url: str = server_url + model_path
#     res: Any | None
#     parents: list[JSONParent] = json_data()
#     async with ThrottledClientSession(rate_limit=rate_limit) as session:
#         for parent in parents:
#             if (
#                 res := await post_url(
#                     session=session,
#                     url=url,
#                     headers={"Content-Type": "application/json"},
#                     json=parent.obj_src(),
#                     retries=2,
#                 )
#             ) is None:
#                 assert False, "post_url() returned None"
#             assert res == "OK", "got wrong response"
#         assert False, "ALL IS GOOD"
