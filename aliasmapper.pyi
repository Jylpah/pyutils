from pydantic import BaseModel
from typing import Any, Iterable


class AliasMapper():
	"""Simple class to map Pydantic BaseModel fields to their aliases"""
	def __init__(self, model: type[BaseModel]): ...
	
	def alias(self, field: str): ...

	@classmethod
	def map(cls, model: type[BaseModel], fields: Iterable[tuple[str, Any]]) -> dict[str, Any]: ...