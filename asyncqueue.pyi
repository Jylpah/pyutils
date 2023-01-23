import queue
from typing import Any, AsyncIterable, Generic, TypeVar, Optional
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

	SLEEP: float

	def __init__(self, queue: queue.Queue[T]): ...
		
	async def get(self) -> T: ...
	
	async def put(self, item: T) -> None: ...
	
	def task_done(self) -> None: ...
	
	def qsize(self) -> int: ...
	
	def empty(self) -> bool: ...
		
	def full(self) -> bool: ...
		

