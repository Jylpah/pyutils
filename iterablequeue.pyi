from asyncio import Queue
from typing import Any, AsyncIterable, Generic, TypeVar, Optional
from .utils import Countable


T= TypeVar('T')

class QueueDone(Exception):
	pass


class IterableQueue(Queue[T], AsyncIterable[T], Countable):
	"""Async.Queue subclass to support async iteration and QueueDone"""

	def __init__(self, total: int = 0, 
					count_items: bool = True, **kwargs): ...

	async def add_producer(self, N : int = 1) -> int: ...

	async def finish(self) -> bool: ...

	async def shutdown(self) -> None: ...
	
	@property
	def is_filled(self) -> bool: ...
	
	async def put(self, item: T) -> None: ...

	def put_nowait(self, item: T) -> None: ...

	async def get(self) -> T: ...

	def get_nowait(self) -> T: ...

	def task_done(self) -> None: ...

	async def join(self) -> None: ...

	@property
	def maxsize(self) -> int: ...
	
	def full(self) -> bool: ...

	def empty(self) -> bool: ...

	def qsize(self) -> int: ...

	@property
	def wip(self) -> int: ...
	
	@property
	def has_wip(self) -> bool: ...

	@property
	def count(self) -> int: ...
	
	async def __aiter__(self): ...
	
	async def __anext__(self) -> T: ...
