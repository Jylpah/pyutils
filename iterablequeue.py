from asyncio import Queue
from typing import Any, AsyncIterable


class QueueDone(Exception):
	pass


class IterableQueue(Queue, AsyncIterable):
	"""Async.Queue subclass to support async iteration and QueueDone"""
	def __init__(self, producers: int = 1, **kwargs):
		super(Queue,self).__init__(**kwargs)
		self._producers = producers
		self._done : bool = False
		self._registered_producers : bool = producers > 1


	def register_producer(self, N : int = 1) -> int:
		assert N > 0, 'N has to be positive'
		if self._registered_producers:
			self._producers += N
		else:
			self._registered_producers = True
		return self._producers


	async def done(self) -> bool:
		self._producers -= 1
		if self._producers <= 0:
			self._done = True
			await super().put(None)
		return self._done


	@property
	def is_done(self) -> bool:
		return self._done


	async def put(self, item) -> None:
		if self._done:
			raise QueueDone
		else:
			if item is None:
				raise ValueError('Cannot add None to IterableQueue')
			await super().put(item=item)


	async def get(self) -> Any:
		item = await super().get()
		if item is None:
			super().task_done()
			await super().put(None)
			raise QueueDone
		else:
			return item

	
	async def __aiter__(self):
		return self

	
	async def __anext__(self) -> Any:
		try:
			item = await self.get()
			return item
		except QueueDone:
			raise StopAsyncIteration

