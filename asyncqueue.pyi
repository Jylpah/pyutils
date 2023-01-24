import queue
import asyncio
from typing import Any, AsyncIterable, Generic, TypeVar, Optional
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

	SLEEP: float

	def __init__(self, maxsize: int =0): ...

	@classmethod
	def from_queue(cls, Q : queue.Queue[T]) -> 'AsyncQueue[T]': ...

	@property
	def maxsize(self) -> int: ...
		
	async def get(self) -> T: ...

	def get_nowait(self) -> T: ...
	
	async def put(self, item: T) -> None: ...

	def put_nowait(self, item: T) -> None: ...

	async def join(self) -> None: ...
	
	def task_done(self) -> None: ...
	
	def qsize(self) -> int: ...
	
	def empty(self) -> bool: ...
		
	def full(self) -> bool: ...
		

