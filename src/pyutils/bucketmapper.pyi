from typing import TypeVar, Generic, Optional
from dataclasses import dataclass

T = TypeVar("T")

@dataclass
class BucketItem(Generic[T]): ...


class BucketMapper(Generic[T]):
	"""BucketMapper() is a generic class for mapping object based on a 
		numeric, discrete key and retrieving objects by value that is 
		less that the key. see python bisect module"""
	
	def __init__(self, attr: str): ...

	def insert(self, item : T) -> None: ...

	def get(self, key: int | float, shift: int = 0) -> Optional[T]: ...
		

	def pop(self, item : T|None = None, key : Optional[int|float] = None, shift: int = 0) -> Optional[T]: ...

	def list(self) -> list[T]: ...	