import logging
from typing import  cast, Type, Any, TypeVar, \
	 Mapping,Self
from abc import ABCMeta, abstractmethod
from pydantic import BaseModel, ValidationError
from aiocsv.readers import AsyncDictReader
from csv import Dialect, excel, QUOTE_NONNUMERIC
from collections.abc import AsyncGenerator
from aiofiles import open

# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug


########################################################
#
# TXTImportable()
#
########################################################


TXTImportableSelf = TypeVar('TXTImportableSelf', bound='TXTImportable')
class TXTImportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT import"""
	
	@classmethod
	def from_txt(cls: type[TXTImportableSelf], 
	      			text: str, 
					**kwargs
				) -> TXTImportableSelf: ...
		
	@classmethod
	async def import_txt(cls : type[TXTImportableSelf], 
					filename : str, 
					**kwargs
					) -> AsyncGenerator[TXTImportableSelf, None]: ...
	

########################################################
#
# CSVImportable()
#
########################################################


CSVImportableSelf = TypeVar('CSVImportableSelf', bound='CSVImportable')

class CSVImportable(BaseModel):
	"""Abstract class to provide CSV export"""
	
	@classmethod
	def from_csv(cls: type[CSVImportableSelf], 
	      		row: dict[str, Any]
				) -> CSVImportableSelf | None: ...

	@classmethod
	def _set_field_types(cls, row: dict[str, Any]) -> dict[str, Any]: ...
		
	@classmethod
	async def import_csv(cls : type[CSVImportableSelf], 
					filename : str, 
					**kwargs
					) -> AsyncGenerator[CSVImportableSelf, None]: ...


########################################################
#
# JSONImportable()
#
########################################################


JSONImportableSelf = TypeVar('JSONImportableSelf', bound='JSONImportable')

class JSONImportable(BaseModel):

	@classmethod
	async def open(cls: type[JSONImportableSelf], 
					filename: str
					) -> JSONImportableSelf | None: ...
	
	@classmethod
	def from_str(cls: type[JSONImportableSelf],
	      		content: str
		  		) -> JSONImportableSelf | None: ...
	
	@classmethod
	def from_obj(cls: type[JSONImportableSelf], 
	      		content: Any
				) -> JSONImportableSelf | None: ...
	
	@classmethod
	async def import_json(cls : type[JSONImportableSelf], 
						filename : str, 
						**kwargs
						) -> AsyncGenerator[JSONImportableSelf, None]: ...

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
