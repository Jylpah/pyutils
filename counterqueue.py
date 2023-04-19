from asyncio import Queue
from typing import TypeVar
from .utils import Countable
import logging

logger 	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

###########################################
# 
# class CounterQueue  
#
###########################################
T = TypeVar('T')

class CounterQueue(Queue[T], Countable):
	_counter 	 : int
	_count_items : bool
	_batch 		 : int

	def __init__(self, *args, 
	      		count_items : bool = True, 
				batch: int = 1, 
				**kwargs) -> None:
		super().__init__(*args, **kwargs)
		self._counter = 0
		self._count_items = count_items
		self._batch = batch

	def task_done(self) -> None:
		super().task_done()
		if self._count_items:
			self._counter += 1
		return None


	@property
	def count(self) -> int:
		"""Return number of completed tasks"""
		return self._counter * self._batch


	@property
	def count_items(self) -> bool:
		"""Whether or not count items"""
		return self._count_items

class QCounter:
	def __init__(self, Q : Queue[int]):
		self._count = 0
		self._Q : Queue[int]= Q


	@property
	def count(self) -> int:
		return self._count	


	async def start(self) -> None:
		"""Read and count items from Q"""
		while True:
			self._count += await self._Q.get()
			self._Q.task_done()
			