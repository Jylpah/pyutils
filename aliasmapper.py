from pydantic import BaseModel
from typing import Any
import logging

logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

class AliasMapper():
	"""Simple class to map Pydantic BaseModel fields to their aliases"""
	def __init__(self, model: type[BaseModel]):
		self._model : type[BaseModel] = model
	
	
	def alias(self, field: str):
		return self._model.__fields__[field].alias

	@classmethod
	def map_dict(cls, model: type[BaseModel], fields: dict[str, Any]) -> dict[str, Any]:
		res : dict[str, Any] = dict()
		try:
			a : AliasMapper = AliasMapper(model)
			alias = a.alias
			for f, v in fields.items():
				res[alias(f)] = v
		except KeyError as err:
			error(f'{type(model).__name__}() Field not found: {err}')
		except Exception as err:		
			raise ValueError(f'{type(model).__name__}(): Could not map field aliases: {err}')
		return res
