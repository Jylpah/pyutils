from asyncio import Queue
from typing import TypeVar, Iterable
from .utils import Countable

###########################################
# 
# class CounterQueue  
#
###########################################
T = TypeVar('T')

class CounterQueue(Queue[T], Countable):
	_counter : int

	def __init__(self, 
	      		*args, 
	      		count_items : bool = True, 
				batch: int = 1, 
				**kwargs) -> None: ...

	def task_done(self) -> None: ...
	
	@property
	def count(self) -> int: ...


class QCounter:
	def __init__(self, Q : Queue[int]): ...

	@property
	def count(self) -> int: ...

	async def start(self) -> None: ...