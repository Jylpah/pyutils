from asyncio import Queue, Event, Lock
from typing import Any, AsyncIterable, Generic, TypeVar, Optional
from .utils import Countable

T= TypeVar('T')

class QueueDone(Exception):
	pass


class IterableQueue(Queue[T], AsyncIterable[T], Countable):
	"""Async.Queue subclass to support async iteration and QueueDone"""

	def __init__(self, count_items: bool = True, **kwargs):
		self._Q : Queue[Optional[T]] = Queue(**kwargs)
		self._producers 	: int 	= 0
		# self._finished 		: bool 	= False
		# self._done 		: bool 	= False	# neeeded? 
		# self._total 		: int 	= total
		self._count 		: int 	= 0
		self._count_items 	: bool 	= count_items
		self._modify 		: Lock	= Lock()
		self._done 			: Event = Event()


	async def add_producer(self, N : int = 1) -> int:
		"""Add producer(s) to the queue"""		
		assert N > 0, 'N has to be positive'

		# if self.is_finished:
		# 	raise ValueError('Cannot add a producer. Queue has finished filling')
		async with self._modify:
			self._producers += N		
		return self._producers


	async def finish(self) -> bool:
		async with self._modify:
			if self._producers == 1:
				await self._Q.put(None)					
			if self._producers > 0:			
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
			return self._done.is_set()
		return self._Q.empty()


	async def get(self) -> T:
		item = await self._Q.get()
		if item is None:
			self._Q.task_done()
			await self._Q.put(None)	
			self._done.set()
			raise QueueDone
		elif self._count_items:
			async with self._modify:
				self._count += 1
		
		return item


	def get_nowait(self) -> T:
		item = self._Q.get_nowait()
		if item is None:
			self._Q.task_done()
			self._Q.put_nowait(None)
			self._done.set()			
			raise QueueDone
		elif self._count_items:
			self._count += 1
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
		elif self._producers > 0:		
			self._Q.put_nowait(item=item)
			return None
		raise ValueError('No producers registered')


	async def join(self) -> None:
		await self._done.wait()
		return None


	def qsize(self) -> int:
		if self.is_finished:
			return self._Q.qsize() - 1
		else:
			return self._Q.qsize()
	

	def task_done(self) -> None:
		self._Q.task_done()
		

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