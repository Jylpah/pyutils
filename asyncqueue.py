from queue import Full, Empty
import queue
from typing import Generic, TypeVar
import logging 
from asyncio import sleep

T= TypeVar('T')

logger = logging.getLogger(__name__)

debug	= logger.debug
message = logger.warning
verbose = logger.info
error 	= logger.error

class AsyncQueue(Generic[T]):
	"""Async wrapper for queue.Queue"""

	SLEEP: float = 0.01

	def __init__(self, Q: queue.Queue[T]):
		self._Q : queue.Queue[T] = Q

	async def get(self) -> T:
		while True:
			try:
				return self._Q.get_nowait()
			except Empty:
				await sleep(self.SLEEP)
	

	async def put(self, item: T) -> None:		
		while True:
			try:
				self._Q.put_nowait(item)
				return None
			except Full:
				await sleep(self.SLEEP)


	def task_done(self) -> None:
		self._Q.task_done()
		return None


	def qsize(self) -> int:
		return self._Q.qsize()


	def empty(self) -> bool:
		return self._Q.empty()


	def full(self) -> bool:
		return self._Q.full()


