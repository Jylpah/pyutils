from queue import Full, Empty
import queue
from asyncio.queues import QueueEmpty, QueueFull
import asyncio
from typing import Generic, TypeVar
import logging 
from asyncio import sleep

T= TypeVar('T')

logger = logging.getLogger(__name__)

debug	= logger.debug
message = logger.warning
verbose = logger.info
error 	= logger.error

class AsyncQueue(asyncio.Queue, Generic[T]):
	"""Async wrapper for queue.Queue"""

	SLEEP: float = 0.01

	def __init__(self, maxsize: int =0):
		self._Q : queue.Queue[T] = queue.Queue()
		self._done : int = 0

	@classmethod
	def from_queue(cls, Q : queue.Queue[T]) -> 'AsyncQueue[T]':
		aQ : AsyncQueue[T] = AsyncQueue()
		aQ._Q = Q
		return aQ

	@property
	def maxsize(self) -> int:
		"""not supported by queue.Queue"""
		return 0


	async def get(self) -> T:
		while True:
			try:
				return self._Q.get_nowait()
			except Empty:
				await sleep(self.SLEEP)
	
	
	def get_nowait(self) -> T:
		try:
			return self._Q.get_nowait()
		except:
			raise QueueEmpty		


	async def put(self, item: T) -> None:		
		while True:
			try:
				self._Q.put_nowait(item)
				return None
			except Full:
				await sleep(self.SLEEP)


	def put_nowait(self, item: T) -> None:
		try:
			return self._Q.put_nowait(item)
		except:
			raise QueueFull


	async def join(self) -> None:
		while True:
			if self._Q.empty():
				return None
			else:
				await sleep(self.SLEEP)


	def task_done(self) -> None:
		self._Q.task_done()
		self._done += 1
		return None


	def qsize(self) -> int:
		return self._Q.qsize()


	@property
	def done(self) -> int:
		return self._done


	def empty(self) -> bool:
		return self._Q.empty()


	def full(self) -> bool:
		return self._Q.full()


