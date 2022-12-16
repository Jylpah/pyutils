from pydantic import BaseModel

class AliasMapper():
	"""Simple class to map Pydantic BaseModel fields to their aliases"""
	def __init__(self, model: type[BaseModel]):
		self._model : type[BaseModel] = model
	
	
	def alias(self, field: str):
		return self._model.__fields__[field].alias