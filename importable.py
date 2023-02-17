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
# Importable()
#
########################################################


class Importable(metaclass=ABCMeta):
	"""Abstract class to provide import"""

	@classmethod
	async def import_file(cls, file : str, 					  
					  	**kwargs,
					 	 ) ->  AsyncGenerator[Self, None]:
		debug('starting')
		try:
			if file.endswith('.txt') and issubclass(cls, TXTImportable):
				async for obj in cls.import_txt(file, **kwargs):
					yield obj
			elif file.endswith('.json') and issubclass(cls, JSONImportable):
				async for obj in cls.import_json(file, **kwargs):
					yield obj
			elif file.endswith('.csv') and issubclass(cls, CSVImportable):
				async for obj in cls.import_csv(file, **kwargs):
					yield obj
		except Exception as err:
			error(f'{err}')


########################################################
#
# TXTImportable()
#
########################################################


TXTImportableSelf = TypeVar('TXTImportableSelf', bound='TXTImportable')
class TXTImportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT import"""
	
	@classmethod
	def from_txt(cls: type[TXTImportableSelf], text: str, **kwargs) -> TXTImportableSelf:
		"""Provide CSV row as a dict for csv.DictWriter"""
		raise NotImplementedError


	@classmethod
	async def import_txt(cls : type[TXTImportableSelf], 
					filename : str, 
					**kwargs) -> AsyncGenerator[TXTImportableSelf, None]:
		"""Import from filename, one model per line"""
		try:
			importable : TXTImportableSelf | None
			async with open(filename, 'r') as f:
				async for line in f:
					try:
						importable = cls.from_txt(line, **kwargs)
						if importable is not None:
							yield importable
					except ValidationError as err:
						error(f'Could not validate mode: {err}')
					except Exception as err:
						error(f'{err}')				
		except Exception as err:
			error(f'Error importing file {filename}: {err}')
	

########################################################
#
# CSVImportable()
#
########################################################


CSVImportableSelf = TypeVar('CSVImportableSelf', bound='CSVImportable')

class CSVImportable(BaseModel):
	"""Abstract class to provide CSV export"""
	
	@classmethod
	def from_csv(cls: type[CSVImportableSelf], row: dict[str, Any]) -> CSVImportableSelf | None:
		"""Provide CSV row as a dict for csv.DictWriter"""
		try:
			row = cls._set_field_types(row)
			return cls.parse_obj(row)
		except Exception as err:
			error(f'Could not parse row ({row}): {err}')
		return None


	@classmethod
	def _set_field_types(cls, row: dict[str, Any]) -> dict[str, Any]:
		## Does NOT WORK with Alias field names
		assert type(row) is dict, 'row has to be type dict()'
		res : dict[str, Any] = dict()
		for field in row.keys():			
			if row[field] != '':
				try:
					field_type = cls.__fields__[field].type_
					res[field] = (field_type)(eval(row[field]))
				except KeyError:												# field not in cls
					continue
				except (TypeError, ValueError, NameError) as err:
					res[field] = row[field]
				except AttributeError as err:
					error(f'Class {cls.__name__}() does not have attribute: {field}')
				except Exception as err:
					error(f'Could not parse field {field}: {type(err)}: {err}')
		return res


	@classmethod
	async def import_csv(cls : type[CSVImportableSelf], 
					filename : str, 
					**kwargs,) -> AsyncGenerator[CSVImportableSelf, None]:
		"""Import from filename, one model per line"""
		try:
			dialect 	: Type[Dialect] = excel
			importable 	: CSVImportableSelf | None
			async with open(filename, mode='r', newline='') as f:
				async for row in AsyncDictReader(f, dialect=dialect):
					try:						
						if (importable := cls.from_csv(row)) is not None:
							yield importable
					except ValidationError as err:
						error(f'Could not validate mode: {err}')
					except Exception as err:
						error(f'{err}')				
		except Exception as err:
			error(f'Error importing file {filename}: {err}')


########################################################
#
# JSONImportable()
#
########################################################


JSONImportableSelf = TypeVar('JSONImportableSelf', bound='JSONImportable')

class JSONImportable(BaseModel):

	@classmethod
	async def open(cls: type[JSONImportableSelf], filename: str) -> JSONImportableSelf | None:
		"""Open replay JSON file and return WoTBlitzReplayJSON instance"""
		try:
			async with open(filename, 'r') as f:
				return cls.parse_raw(await f.read())
		except Exception as err:
			error(f'Error reading replay: {err}')
		return None


	@classmethod
	def from_str(cls: type[JSONImportableSelf], content: str) -> JSONImportableSelf | None:
		"""Open replay JSON file and return WoTBlitzReplayJSON instance"""
		try:
			return cls.parse_raw(content)
		except ValidationError as err:
			error(f'Invalid replay format: {err}')
		except Exception as err:
			error(f'{err}')
		return None


	@classmethod
	def from_obj(cls: type[JSONImportableSelf], content: Any) -> JSONImportableSelf | None:
		"""Open replay JSON file and return WoTBlitzReplayJSON instance"""
		try:
			return cls.parse_obj(content)
		except ValidationError as err:
			error(f'Invalid format: {err}')
		except Exception as err:
			error(f'{err}')
		return None


	@classmethod
	async def import_json(cls : type[JSONImportableSelf], 
						filename : str, 
						**kwargs) -> AsyncGenerator[JSONImportableSelf, None]:
		"""Import from filename, one model per line"""
		try:
			importable : JSONImportableSelf | None
			async with open(filename, 'r') as f:
				async for line in f:
					try:
						importable = cls.from_str(line, **kwargs)
						if importable is not None:
							yield importable
					except ValidationError as err:
						error(f'Could not validate mode: {err}')
					except Exception as err:
						error(f'{err}')				
		except Exception as err:
			error(f'Error importing file {filename}: {err}')
		


