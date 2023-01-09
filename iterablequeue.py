from asyncio import Queue
from typing import Any, AsyncIterable, Generic, TypeVar, Optional
from .utils import Countable


T= TypeVar('T')

class QueueDone(Exception):
	pass


class IterableQueue(Queue[T], AsyncIterable, Countable):
	"""Async.Queue subclass to support async iteration and QueueDone"""

	def __init__(self, producers: int = 1, total: int = 0, 
					count_items: bool = True, **kwargs):
		super(Queue[Optional[T]], self).__init__(**kwargs)
		self._producers 	: int 	= producers
		self._done 			: bool 	= False
		self._total 		: int 	= total
		self._count 		: int 	= 0
		self._count_items 	: bool 	= count_items
		self._registered_producers : bool = producers > 1


	def register_producer(self, N : int = 1) -> int:
		assert N > 0, 'N has to be positive'
		if self.is_done:
			raise ValueError('Cannot register a producer to a queue that is done')
		if self._registered_producers:
			self._producers += N
		else:
			self._registered_producers = True
		return self._producers


	async def done(self) -> bool:
		self._producers -= 1
		if self._producers <= 0:
			self._producers = 0
			self._done = True
			await super().put(None)
		return self._done


	async def shutdown(self) -> None:
		self._producers = 0
		await self.done()


	@property
	def is_done(self) -> bool:
		return self._done


	async def put(self, item: T) -> None:
		if self.is_done:
			raise QueueDone
		else:
			if item is None:
				raise ValueError('Cannot add None to IterableQueue')
			await super().put(item=item)

	
	# async def last(self) -> None:
	# 	"""Put marker to the queue signaling the last item has 
	# 		been put to the queue"""
	# 	await super().put(None)


	async def get(self) -> T:
		item = await super().get()
		if item is None:
			super().task_done()
			await super().put(None)			
			raise QueueDone
		else:
			if self._count_items:
				self._count += 1
			return item

	@property
	def count(self) -> int:
		# return min(self._count, self._total)
		return self._count


	async def __aiter__(self):
		return self

	
	async def __anext__(self) -> T:
		try:
			item = await self.get()
			return item
		except QueueDone:
			raise StopAsyncIteration