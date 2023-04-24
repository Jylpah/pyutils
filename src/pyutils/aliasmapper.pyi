from pydantic import BaseModel
from typing import Any, Iterable, TypeVar, Generic

T = TypeVar('T')

class AliasMapper():
	"""Simple class to map Pydantic BaseModel fields to their aliases"""
	def __init__(self, model: type[BaseModel]): ...
	
	def alias(self, field: str): ...

	def map(self, fields: Iterable[tuple[str, T]]) -> dict[str, T]: ...

	@classmethod
	def mapper(cls, model: type[BaseModel], fields: Iterable[tuple[str, T]]) -> dict[str, T]: ...