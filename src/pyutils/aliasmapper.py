from pydantic import BaseModel
from typing import Any, Iterable, TypeVar, Generic
import logging

logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

T = TypeVar('T')
class AliasMapper():
	"""Simple class to map Pydantic BaseModel fields to their aliases"""
	def __init__(self, model: type[BaseModel]):
		self._model : type[BaseModel] = model
	
	
	def alias(self, field: str) -> str:
		if len(fields := field.split('.')) > 1:
			field = fields[0]
			field_child : str = '.'.join(fields[1:])
			model : type[BaseModel] = self._model.__fields__[field].type_
			mapper : AliasMapper = AliasMapper(model)
			return self.alias(field) + '.' + mapper.alias(field_child)
		else:
			return self._model.__fields__[field].alias


	def map(self, fields: Iterable[tuple[str, T]]) -> dict[str, T]:
		res : dict[str, T] = dict()
		try:			
			for f, v in fields:
				try: 
					res[self.alias(f)] = v
				except KeyError as err:
					error(f'{self._model.__qualname__}(): could not map {f}: {err}')
		except Exception as err:		
			raise ValueError(f'{self._model.__qualname__}(): Could not map field aliases: {err}')
		return res


	@classmethod
	def mapper(cls, model: type[BaseModel], fields: Iterable[tuple[str, T]]) -> dict[str, T]:
		return cls(model).map(fields)
		
