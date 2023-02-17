import logging
from typing import  cast, Type, Any, TypeVar, \
	 Mapping,Self, AsyncGenerator
from abc import ABCMeta, abstractmethod
from pydantic import BaseModel, ValidationError
from aiocsv.readers import AsyncDictReader
from csv import Dialect, excel, QUOTE_NONNUMERIC
from aiofiles import open

# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug



########################################################
#
# Importable()
#
########################################################


class Importable(metaclass=ABCMeta):
	"""Abstract class to provide import"""

	@classmethod
	async def import_file(cls, file : str, 					  
					  	**kwargs,
					 	 ) ->  AsyncGenerator[Self, None]: ...


########################################################
#
# TXTImportable()
#
########################################################


TXTImportableSelf = TypeVar('TXTImportableSelf', bound='TXTImportable')
class TXTImportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT import"""
	
	@classmethod
	def from_txt(cls, 
	      			text: str, 
					**kwargs
				) -> Self: ...
		
	@classmethod
	async def import_txt(cls, 
						filename : str, 
						**kwargs
						) -> AsyncGenerator[Self, None]: ...
	

########################################################
#
# CSVImportable()
#
########################################################


CSVImportableSelf = TypeVar('CSVImportableSelf', bound='CSVImportable')

class CSVImportable(BaseModel):
	"""Abstract class to provide CSV export"""
	
	@classmethod
	def from_csv(cls, 
	      		row: dict[str, Any]
				) -> Self | None: ...

	@classmethod
	def _set_field_types(cls, row: dict[str, Any]) -> dict[str, Any]: ...
		
	@classmethod
	async def import_csv(cls, 
						filename : str, 
						**kwargs
						) -> AsyncGenerator[Self, None]: ...


########################################################
#
# JSONImportable()
#
########################################################


JSONImportableSelf = TypeVar('JSONImportableSelf', bound='JSONImportable')

class JSONImportable(BaseModel):

	@classmethod
	async def open(cls, 
					filename: str
					) -> Self | None: ...
	
	@classmethod
	def from_str(cls,
	      		content: str
		  		) -> Self | None: ...
	
	@classmethod
	def from_obj(cls, 
	      		content: Any
				) -> Self | None: ...
	
	@classmethod
	async def import_json(cls, 
						filename : str, 
						**kwargs
						) -> AsyncGenerator[Self, None]: ...
