from asyncio import Queue, CancelledError, sleep
from typing import TypeVar, Iterable
from alive_progress import alive_bar 		# type: ignore
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

class CounterQueue(Queue[T]):
	_counter 	 : int
	_count_items : bool

	def __init__(self, *args, count_items : bool = True, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self._counter = 0
		self._count_items = count_items

	def task_done(self) -> None:
		super().task_done()
		if self._count_items:
			self._counter += 1
		return None


	@property
	def count(self) -> int:
		"""Return number of completed tasks"""
		return self._counter


	@property
	def count_items(self) -> bool:
		"""Whether or not count items"""
		return self._count_items


async def alive_queue_bar(queues : Iterable[CounterQueue], title : str, 
							total : int | None = None, wait: float = 0.1, 
							*args, **kwargs) -> None:
	try:
		prev : int = 0
		current : int = 0
		with alive_bar(total, *args, title=title, **kwargs) as bar:
			while True:
				try:
					# if total is not None and current >= total:
					#	break
					await sleep(wait)
				except CancelledError:
					debug('cancelled')	
					break
				finally:
					current = 0
					for q in queues:
						current += q.count
					if current - prev > 0:
						bar(current - prev)
					prev = current
	except Exception as err:
		error(f'{err}')
	return None