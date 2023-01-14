from asyncio import Queue, Event, Lock
from typing import Any, AsyncIterable, Generic, TypeVar, Optional
from .utils import Countable

T= TypeVar('T')

class QueueDone(Exception):
	pass


class IterableQueue(Queue[T], AsyncIterable[T], Countable):
	"""Async.Queue subclass that to supports:
	* AsyncIterable()
	* Producers must be registered with add_producer()
	* Producers must notify once they have finished adding items with finish()
	* Automatic termination  of consumers when the queue is empty with (QueueDone exception)
	* Countable interface to count number of items task_done() through 'count' property
	* Countable property can be disabled with count_items=False. This is useful when you
	want to sum the count of multiple IterableQueues"""

	def __init__(self, count_items: bool = True, **kwargs):
		self._Q : Queue[Optional[T]] = Queue(**kwargs)
		self._producers 	: int 	= 0
		self._count_items 	: bool 	= count_items
		self._count 		: int 	= 0
		self._wip 			: int 	= 0
		self._modify 		: Lock	= Lock()
		self._empty 		: Event = Event()
		self._done			: Event = Event()


	async def add_producer(self, N : int = 1) -> int:
		"""Add producer(s) to the queue"""
		assert N > 0, 'N has to be positive'
		async with self._modify:
			self._producers += N
		return self._producers


	async def finish(self) -> bool:
		async with self._modify:
			if self._producers == 1:
				self._producers = 0
				await self._Q.put(None)
			elif self._producers > 1:
				self._producers -= 1
		return self.is_finished


	async def shutdown(self) -> None:
		async with self._modify:
			self._producers = 1   # since finish() deducts 1 producer
		await self.finish()


	@property
	def is_finished(self) -> bool:
		return self._producers == 0


	@property
	def maxsize(self) -> int:
		return self._Q.maxsize


	def full(self) -> bool:
		return self._Q.full()


	def empty(self) -> bool:
		if self.is_finished:
			return self._empty.is_set()
		return self._Q.empty()


	async def get(self) -> T:
		# if self._empty.is_set():
		# 	raise QueueDone
		item = await self._Q.get()
		if item is None:
			self._empty.set()
			self._Q.task_done()
			await self._Q.put(None)
			raise QueueDone
		else:
			async with self._modify:
				self._wip += 1
		return item


	def get_nowait(self) -> T:
		if self._empty.is_set():
			raise QueueDone
		item = self._Q.get_nowait()
		if item is None:
			self._Q.task_done()
			self._Q.put_nowait(None)
			self._empty.set()
			raise QueueDone
		else:
			self._wip += 1
		return item


	async def put(self, item: T) -> None:
		if self.is_finished:
			raise QueueDone
		elif item is None:
			raise ValueError('Cannot add None to IterableQueue')
		await self._Q.put(item=item)
		return None


	def put_nowait(self, item: T) -> None:
		if self.is_finished:
			raise QueueDone
		elif item is None:
			raise ValueError('Cannot add None to IterableQueue')
		self._Q.put_nowait(item=item)
		return None


	async def join(self) -> None:
		await self._done.wait()
		# await self._Q.join()
		return None


	def qsize(self) -> int:
		if self.is_finished:
			return self._Q.qsize() - 1
		else:
			return self._Q.qsize()


	def task_done(self) -> None:
		self._Q.task_done()
		if self._count_items:
			self._count += 1
		self._wip -= 1
		if self._wip < 0:
			raise ValueError('task_done() called more than tasks open')
		if self._wip == 0 and self._empty.is_set():
			self._done.set()


	@property
	def count(self) -> int:
		return self._count


	async def __aiter__(self):
		return self


	async def __anext__(self) -> T:
		try:
			item = await self.get()
			return item
		except QueueDone:
			raise StopAsyncIteration