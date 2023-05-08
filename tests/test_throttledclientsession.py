import sys
import pytest # type: ignore
from pathlib import Path
from datetime import datetime, timedelta
from itertools import pairwise, accumulate
from math import ceil
from typing import Generator
from multiprocessing import Process
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
# from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from asyncio.queues import QueueEmpty, QueueFull
from asyncio import Task, create_task, sleep, gather, timeout, TimeoutError
from random import random
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / 'src'))

from pyutils import ThrottledClientSession

HOST : str = 'localhost'
PORT : int = 8889
RATE_FAST : float = 100
RATE_SLOW : float = 0.6

N_FAST : int = 500
N_SLOW : int = 5  

THREADS : int = 5
# N : int = int(1e10)

logger	= logging.getLogger()
message	= logger.warning

class _HttpRequestHandler(BaseHTTPRequestHandler):
	"""HTTPServer mock request handler"""
	
	def do_GET(self):  # pylint: disable=invalid-name
		"""Handle GET requests"""
		# message(f'GET @ {datetime.utcnow()}')
		self.send_response(200)
		self.send_header("Content-Type", "application/txt")
		self.end_headers()
		self.wfile.write(datetime.utcnow().isoformat().encode())


	def log_request(self, code=None, size=None):
		"""Don't log anything"""
		pass


class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
	pass


class _HttpServer(Process):
	def __init__(self, host: str = HOST, port: int = PORT):
		super().__init__()
		self._host : str = host
		self._port : int = port

	def run(self):
		server = ThreadingSimpleServer((self._host, self._port), 
										_HttpRequestHandler)
		server.serve_forever()


def max_rate(timings: list[float], rate: float) -> float:
	"""Read list[datetime] and return number of timings, 
		average rate and maximum rate"""
	assert rate > 0, f"rate must be positive: {rate}"
	diffs : list[float] = [x1-x0 for (x0, x1) in pairwise(timings)]
	cums : list[float] = [0] + list(accumulate(diffs))
	window : int = max(int(rate) -1, 1)
	min_time : float = min([ cums[i+window] - cums[i] for i in range(len(cums)-window) ])
	return (window) / min_time


def avg_rate(timings: list[float]) -> float:
	n : int = len(timings) -1 # the last request is not measured in total
	total : float = timings[-1] - timings[0]
	return n / total


async def _get(url: str, rate: float, N: int) -> list[float]:
	"""Test timings of N/sec get"""
	timings : list[float] = list()
	async with ThrottledClientSession(rate_limit=rate) as session:
		for _ in range(N):
			async with session.get(url, ssl=False) as resp:
				assert resp.status == 200, f"request failed, HTTP STATUS={resp.status}"
				timings.append(datetime.fromisoformat(await resp.text()).timestamp())
	return timings


@pytest.fixture(scope='module')
def server_host() -> str:
	return HOST


@pytest.fixture(scope='module')
def server_port() -> int:
	return PORT


@pytest.fixture(scope='module')
def server_url(server_host: str, server_port: int) -> Generator[str, None, None]:
	# start HTTP server
	host: str = server_host
	port: int = server_port
	server : _HttpServer = _HttpServer(host = host, port = server_port)
	server.start()
	yield f"http://{host}:{port}/"
	# clean up
	server.terminate()



@pytest.mark.timeout(20)
@pytest.mark.asyncio
async def test_1_fast_get(server_url: str) -> None:
	"""Test timings of N/sec get"""	
	rate_limit : float = RATE_FAST
	N : int = N_FAST
	timings : list[float] = await _get(server_url, rate=rate_limit, N=N)
	rate_max : float = max_rate(timings, rate_limit)
	rate_avg : float = avg_rate(timings)
	message(f'rate limit: {rate_limit:.2f}, avg rate: {rate_avg:.2f}, max rate: {rate_max:.2f}')
	assert rate_avg <= rate_limit*1.05, f"Avg. rate is above rate_limit: {rate_avg:.2f} > {rate_limit:.2f}"
	assert rate_max <= rate_limit*1.1, f""""max_rate is above rate_limit: {rate_max:.2f} > {rate_limit:.2f}\n
										{', '.join([str(t) for t in timings])}"""
	

@pytest.mark.timeout(40)
@pytest.mark.asyncio
async def test_2_slow_get(server_url: str) -> None:
	"""Test timings of N/sec get"""	
	rate_limit : float = RATE_SLOW
	N : int = N_SLOW
	timings : list[float] = await _get(server_url, rate=rate_limit, N=N)
	rate_max : float = max_rate(timings, rate_limit)
	rate_avg : float = avg_rate(timings)
	message(f'rate limit: {rate_limit:.2f}, avg rate: {rate_avg:.2f}, max rate: {rate_max:.2f}')
	assert rate_avg <= rate_limit*1.05, f"Avg. rate is above rate_limit: {rate_avg:.2f} > {rate_limit:.2f}"
	assert rate_max <= rate_limit*1.1, f""""max_rate is above rate_limit: {rate_max:.2f} > {rate_limit:.2f}\n
										{', '.join([str(t) for t in timings])}"""
	


