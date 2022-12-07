from collections import namedtuple
from operator import attrgetter
from bisect import bisect, insort
from typing import Any, TypeVar, Generic, Optional
from dataclasses import dataclass
import logging

# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

T = TypeVar("T")

# @dataclass
# class BucketItem(Generic[T]):
# 	item: T
# 	key: int | float

# class BucketMapper(Generic[T]):
	
# 	by_key = attrgetter('key')
	
# 	def __init__(self, attr: str):
# 		self._attr : str = attr
# 		#self.keys : list[float|int] = list()
# 		self.data : list[BucketItem[T]] = list()

# 	def insert(self, item : T) -> None:
# 		key : int | float = getattr(item, self._attr)
# 		insort(self.data, BucketItem(item=item, key=key), key=self.by_key)
# 		return None
		

class BucketMapper(Generic[T]):
	
	def __init__(self, attr: str):
		self.by_key = attrgetter(attr)
		self.data : list[T] = list()

	def insert(self, item : T) -> None:
		insort(self.data, item, key=self.by_key)
		return None
	
	def get(self, key: int | float) -> Optional[T]:
		try:
			return self.data[bisect(self.data, key, key=self.by_key)]
		except Exception as err:
			error(f'{err}')
		return None

	def pop(self, item : T) -> Optional[T]:
		try:
			return self.data.pop(bisect(self.data, self.by_key(item), key=self.by_key))
		except Exception as err:
			error(f'{err}')
		return None