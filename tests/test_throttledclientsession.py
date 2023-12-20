import sys
import pytest  # type: ignore
from pathlib import Path
from datetime import datetime
from itertools import pairwise, accumulate
from functools import cached_property
from math import ceil
from typing import Generator, Any, List, Dict
from multiprocessing import Process
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from socketserver import ThreadingMixIn

# from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from asyncio.queues import QueueEmpty, QueueFull
from asyncio import Task, create_task, sleep, gather, timeout, TimeoutError
from random import random
import logging
import json


sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import (
    ThrottledClientSession,
    epoch_now,
    get_url_JSON,
    post_url,
)


HOST: str = "localhost"
PORT: int = 8889
JSON_PATH: str = "/json"
RATE_FAST: float = 100
RATE_SLOW: float = 0.6

N_FAST: int = 500
N_SLOW: int = 5

THREADS: int = 5
# N : int = int(1e10)

logger = logging.getLogger()
message = logger.warning


def json_data() -> List[Dict[str, str | int | float | None]]:
    """Generate JSON test data"""

    txt: str = """[{
            "id": "024092b5fd17f4896062dac7b4dbd42d",
            "map_id": 35,
            "battle_duration": 335.84668,
            "title": "VK 72.01 (K) @ Naval Frontier",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 486,
            "enemies_spotted": 3,
            "enemies_destroyed": 0,
            "damage_assisted": 0,
            "damage_made": 618,
            "details_url": "https://replays.wotinspector.com/en/view/024092b5fd17f4896062dac7b4dbd42d",
            "download_url": "https://replays.wotinspector.com/download/024092b5fd17f4896062dac7b4dbd42d",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318447090649727840"
        }, {
            "id": "e9c332bec8d527753c1f2209a1e8cf03",
            "map_id": 38,
            "battle_duration": 261.1665,
            "title": "VK 72.01 (K) @ Horrorstadt",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 272,
            "enemies_spotted": 3,
            "enemies_destroyed": 1,
            "damage_assisted": 0,
            "damage_made": 228,
            "details_url": "https://replays.wotinspector.com/en/view/e9c332bec8d527753c1f2209a1e8cf03",
            "download_url": "https://replays.wotinspector.com/download/e9c332bec8d527753c1f2209a1e8cf03",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318447481491751496"
        }, {
            "id": "a66b6ec64a72c60691cf60f502eba0d7",
            "map_id": 19,
            "battle_duration": 289.8519,
            "title": "VK 72.01 (K) @ Winter Malinovka",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 505,
            "enemies_spotted": 0,
            "enemies_destroyed": 0,
            "damage_assisted": 0,
            "damage_made": 2140,
            "details_url": "https://replays.wotinspector.com/en/view/a66b6ec64a72c60691cf60f502eba0d7",
            "download_url": "https://replays.wotinspector.com/download/a66b6ec64a72c60691cf60f502eba0d7",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318441056220676378"
        }, {
            "id": "31f20c9a1438fe4bbd95fc86d9eee2b7",
            "map_id": 11,
            "battle_duration": 230.93056,
            "title": "VK 72.01 (K) @ Oasis Palms",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 245,
            "enemies_spotted": 2,
            "enemies_destroyed": 0,
            "damage_assisted": 0,
            "damage_made": 624,
            "details_url": "https://replays.wotinspector.com/en/view/31f20c9a1438fe4bbd95fc86d9eee2b7",
            "download_url": "https://replays.wotinspector.com/download/31f20c9a1438fe4bbd95fc86d9eee2b7",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318447146484301852"
        }, {
            "id": "c7cb7fab94e7eced8dee9aea1ed11500",
            "map_id": 10,
            "battle_duration": 287.48947,
            "title": "VK 72.01 (K) @ Black Goldville",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 502,
            "enemies_spotted": 0,
            "enemies_destroyed": 0,
            "damage_assisted": 0,
            "damage_made": 3649,
            "details_url": "https://replays.wotinspector.com/en/view/c7cb7fab94e7eced8dee9aea1ed11500",
            "download_url": "https://replays.wotinspector.com/download/c7cb7fab94e7eced8dee9aea1ed11500",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318447575981031129"
        }, {
            "id": "dcc06a7e8872e3f06bf9472c40e5fc89",
            "map_id": 14,
            "battle_duration": 238.07674,
            "title": "VK 72.01 (K) @ Molendijk",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 247,
            "enemies_spotted": 0,
            "enemies_destroyed": 0,
            "damage_assisted": 0,
            "damage_made": 1411,
            "details_url": "https://replays.wotinspector.com/en/view/dcc06a7e8872e3f06bf9472c40e5fc89",
            "download_url": "https://replays.wotinspector.com/download/dcc06a7e8872e3f06bf9472c40e5fc89",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318439978183884222"
        }, {
            "id": "4e82956ce42fd8090a70d02a886a18be",
            "map_id": 5,
            "battle_duration": 245.33473,
            "title": "VK 72.01 (K) @ Falls Creek",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": 0,
            "exp_base": 592,
            "enemies_spotted": 0,
            "enemies_destroyed": 0,
            "damage_assisted": 999,
            "damage_made": 2650,
            "details_url": "https://replays.wotinspector.com/en/view/4e82956ce42fd8090a70d02a886a18be",
            "download_url": "https://replays.wotinspector.com/download/4e82956ce42fd8090a70d02a886a18be",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "16117927324875930"
        }, {
            "id": "22a56c4be013915002b82403fa8cf375",
            "map_id": 42,
            "battle_duration": 140.49388,
            "title": "VK 72.01 (K) @ Normandy",
            "player_name": "jylpah",
            "protagonist": 521458531,
            "vehicle_descr": 58641,
            "mastery_badge": null,
            "exp_base": null,
            "enemies_spotted": null,
            "enemies_destroyed": 0,
            "damage_assisted": null,
            "damage_made": 1575,
            "details_url": "https://replays.wotinspector.com/en/view/22a56c4be013915002b82403fa8cf375",
            "download_url": "https://replays.wotinspector.com/download/22a56c4be013915002b82403fa8cf375",
            "game_version": {
                "name": "10.1.0_apple",
                "package": "blitz10.1"
            },
            "arena_unique_id": "2318440424860482440"
        }]"""
    return json.loads(txt)


class _HttpRequestHandler(BaseHTTPRequestHandler):
    """HTTPServer mock request handler"""

    _res_json: list[Dict[str, str | int | float | None]] = json_data()

    @cached_property
    def url(self):
        return urlparse(self.path)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        """Handle GET requests"""
        self.send_response(200)
        if self.url.path == JSON_PATH:
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            l: int = len(self._res_json)
            idx: int = epoch_now() % l
            res: Dict[str, str | int | float | None] = self._res_json[idx]
            self.wfile.write(json.dumps(res).encode())

        else:
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
    #     if self.url.path == JSON_PATH:
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
    async with ThrottledClientSession(rate_limit=rate, trust_env=True) as session:
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
def json_path() -> str:
    return JSON_PATH


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


@pytest.mark.timeout(20)
@pytest.mark.asyncio
async def test_3_get_json(server_url: str, json_path: str) -> None:
    """Test get_url_JSON()"""
    rate_limit: float = RATE_SLOW
    N: int = N_SLOW
    url: str = server_url + json_path
    res: Any | None
    async with ThrottledClientSession(rate_limit=rate_limit, trust_env=True) as session:
        for _ in range(N):
            if (_ := await get_url_JSON(session=session, url=url, retries=2)) is None:
                assert False, "get_url_JSON() returned None"


# @pytest.mark.timeout(10)
# @pytest.mark.asyncio
# async def test_5_post_json(server_url: str, json_path: str) -> None:
#     """Test post_url_JSON()"""
#     rate_limit: float = RATE_FAST
#     url: str = server_url + json_path
#     res: Any | None
#     parents: list[JSONParent] = json_data()
#     async with ThrottledClientSession(rate_limit=rate_limit, trust_env=True) as session:
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
