## -----------------------------------------------------------
#### Class ThrottledClientSession(aiohttp.ClientSession)
#
#  Rate-limited async http client session
#
#  Inherits aiohttp.ClientSession 
## -----------------------------------------------------------

from typing import Optional, Union
import aiohttp
from asyncio import Queue, Task, CancelledError, TimeoutError, sleep, create_task, wait_for
import time
import logging
import re
from math import ceil, log

logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

class ThrottledClientSession(aiohttp.ClientSession):
	"""Rate-throttled client session class inherited from aiohttp.ClientSession)""" 

	def __init__(self, rate_limit: float = 0, filters: list[str] = list() , 
				limit_filtered: bool = False, re_filter: bool = False, *args,**kwargs) -> None: 
		assert isinstance(rate_limit, (int, float)),   "rate_limit has to be float"
		assert isinstance(filters, list),       "filters has to be list"
		assert isinstance(limit_filtered, bool),"limit_filtered has to be bool"
		assert isinstance(re_filter, bool),     "re_filter has to be bool"

		super().__init__(*args,**kwargs)
		
		self.rate_limit     : float = 0
		self._fillerTask    : Optional[Task]    = None
		self._queue         : Optional[Queue]   = None
		self._start_time    : float = time.time()
		self._count         : int = 0
		self._limit_filtered: bool = limit_filtered
		self._re_filter     : bool = re_filter
		self._filters       : list[Union[str, re.Pattern]] = list()

		if re_filter:
			for filter in filters:
				self._filters.append(re.compile(filter))
		else:
			for filter in filters:
				self._filters.append(filter)
		self.set_rate_limit(rate_limit)


	def get_rate(self) -> float:
		"""Return rate of requests"""
		return self._count / (time.time() - self._start_time)


	def get_stats(self) -> dict[str, float]:
		"""Get session statistics"""
		res = {'rate' : self.get_rate(), 'rate_limit': self.rate_limit, 'count' : self._count }
		return res
		

	def get_stats_str(self) -> str:
		"""Print session statistics"""
		return self.print_stats(self.get_stats())


	@classmethod
	def print_stats(cls, stats: dict[str, float]) -> str:
		try:
			rate_limit 	: float = stats['rate_limit']
			rate 		: float = stats['rate']
			count		: float = stats['count']
			
			rate_limit_str : str 
			if rate_limit >= 1 or rate_limit == 0:
				rate_limit_str = f'{rate_limit:.1f} requests/sec'
			else:
				rate_limit_str = f'{1/rate_limit:.1f} secs/request'

			return f"rate limit: {rate_limit_str}, rate: {rate:.1f} request/sec, requests: {count:.0f}"
		except KeyError as err:
			return f'Incorrect stats format: {err}'
		except Exception as err:
			return f'Unexpected error: {err}'


	def reset_counters(self) -> dict[str, float]:
		"""Reset rate counters and return current results"""
		res = self.get_stats()
		self._start_time = time.time()
		self._count = 0
		return res


	def set_rate_limit(self, rate_limit: float = 0) -> float:
		assert rate_limit is not None, "rate_limit must not be None" 
		assert isinstance(rate_limit, (int,float)) and rate_limit >= 0, "rate_limit has to be type of 'float' >= 0"
		
		if self._fillerTask is not None: 
			self._fillerTask.cancel()  
			self._fillerTask = None

		self.rate_limit = rate_limit

		if rate_limit > 0:
			self._fillerTask = create_task(self._filler_log())
		
		return self.rate_limit
		

	async def close(self) -> None:
		"""Close rate-limiter's "bucket filler" task"""
		debug(self.get_stats_str())
		try:
			if self._fillerTask is not None:
				self._fillerTask.cancel()
				await wait_for(self._fillerTask, timeout=0.5)
		except TimeoutError as err:
			debug(f'Timeout while cancelling bucket filler: {err}')
		except CancelledError as err:
			debug('Cancelled')
		await super().close()

	
	async def _filler(self) -> None:
		"""Filler task to fill the leaky bucket algo"""
		assert self.rate_limit > 0, "_filler cannot be started without rate limit"
		try:
			self._queue = Queue(1)
			debug(f'SLEEP: {1/self.rate_limit}')
			while True:
				await self._queue.put(None)
				await sleep(1/self.rate_limit)
		except CancelledError:
			debug('Cancelled')
		except Exception as err:
			error(f'{err}')
		finally:
			self._queue = None
		return None


	async def _filler_log(self) -> None:
		"""Filler task to fill the leaky bucket algo.
			Uses longer queue for performance (maybe) :-)"""
		assert self.rate_limit > 0, "_filler cannot be started without rate limit"
		try:
			qlen : int = 1
			if self.rate_limit > 1:
				qlen = ceil(log(self.rate_limit))
			wait : float = qlen / self.rate_limit
			self._queue = Queue(qlen)
			debug(f'SLEEP: {wait}')
			while True:
				for _ in range(qlen):
					await self._queue.put(None)
				await sleep(wait)			
		except CancelledError:
			debug('Cancelled')
		except Exception as err:
			error(f'{err}')
		finally:
			self._queue = None
		return None


	async def _request(self, *args,**kwargs) -> aiohttp.ClientResponse:
		"""Throttled _request()"""
		if self._queue is not None and self.is_limited(*args): 
			debug(f'URL is rate-limited: {args[1]}') 
			await self._queue.get()
			self._queue.task_done()
		else:
			debug(f'URL is not rate-limited: {args[1]}') 
		self._count += 1
		return await super()._request(*args,**kwargs)


	def is_limited(self, *args: str) -> bool:
		"""Check wether the rate limit should be applied"""
		try:
			url: str = args[1]
			for filter in self._filters:
				if isinstance(filter, re.Pattern) and filter.match(url) is not None:
					return self._limit_filtered
				elif isinstance(filter, str) and url.startswith(filter):
					return self._limit_filtered
					
			return not self._limit_filtered
		except Exception as err:
			error(f'{err}')
		return True    

