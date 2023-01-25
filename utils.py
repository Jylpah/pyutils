import logging
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any, cast, Type, Literal, TypeVar, ClassVar, Self, Mapping, Iterable, Generic
from abc import ABCMeta, ABC, abstractmethod
from re import compile
from aiofiles import open
from aiocsv.writers import AsyncDictWriter
from aiocsv.readers import AsyncDictReader
from alive_progress import alive_bar 							# type: ignore
from csv import Dialect, Sniffer, excel, QUOTE_NONNUMERIC
from ast import literal_eval
from os.path import isfile, exists
from os import linesep
from aiofiles import open
import json
from time import time
from aiohttp import ClientSession, ClientResponse, ClientError, ClientResponseError
from pydantic import BaseModel, ValidationError
from asyncio import sleep, CancelledError, Queue, AbstractEventLoop, Task, gather
from collections.abc import AsyncGenerator

from .eventcounter import EventCounter
from .urlqueue import UrlQueue, UrlQueueItemType, is_url


# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

# Constants
MAX_RETRIES : int   = 3
SLEEP       : float = 1


class Countable(ABC):
	
	@property
	@abstractmethod
	def count(self) -> int: 
		raise NotImplementedError		


class CSVExportable(metaclass=ABCMeta):
	"""Abstract class to provide CSV export"""

	@abstractmethod
	def csv_headers(self) -> list[str]:
		"""Provide CSV headers as list"""
		raise NotImplementedError

	
	@abstractmethod
	def csv_row(self) -> dict[str, str | int | float | bool]:
		"""Provide CSV row as a dict for csv.DictWriter"""
		raise NotImplementedError
	
	
	def clear_None(self, res: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool]:
		out : dict[str, str | int | float | bool] = dict()
		for key, value in res.items():
			if value is None:
				out[key]  = ''
			else:
				out[key] = value
		return out


CSVImportableSelf = TypeVar('CSVImportableSelf', bound='CSVImportable')

class CSVImportable(BaseModel):
	"""Abstract class to provide CSV export"""
	
	@classmethod
	def from_csv(cls: type[CSVImportableSelf], row: dict[str, Any]) -> CSVImportableSelf | None:
		"""Provide CSV row as a dict for csv.DictWriter"""
		try:
			row = cls._set_field_types(row)
			debug(str(row))
			return cls.parse_obj(row)
		except Exception as err:
			error(f'Could not parse row ({row}): {err}')
		return None


	@classmethod
	def _set_field_types(cls, row: dict[str, Any]) -> dict[str, Any]:
		assert type(row) is dict, 'row has to be type dict()'
		res : dict[str, Any] = dict()
		for field in row:			
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
					filename : str) -> AsyncGenerator[CSVImportableSelf, None]:
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


TypeExcludeDict = Mapping[int | str, Any]

# I = TypeVar('I', bound='JSONExportable')
JSONExportableSelf 	= TypeVar('JSONExportableSelf', bound='JSONExportable')
B 					= TypeVar('B', bound='BaseModel')

class JSONExportable(BaseModel):

	_exclude_export_DB_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_exclude_export_src_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_include_export_DB_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_include_export_src_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_export_DB_by_alias			: bool = True


	def _export_helper(self, params: dict[str, Any], 
						fields: list[str] | None = None, **kwargs) -> dict:
		"""Helper func to process params for obj/src export funcs"""
		if fields is not None:
			# _exclude : dict[str, bool] = dict()
			# _include : dict[str, bool] = dict()
			# for f in fields:
			# 	_exclude[f] = False
			# 	_include[f] = True
			# params['exclude'] = _exclude
			# params['include'] = _include
			
			del params['exclude']
			params['include'] = { f: True for f in fields }
			params['exclude_defaults'] 	= False
			params['exclude_unset'] 	= False			
		else:
			for f in  ['exclude', 'include']:
				try:
					params[f].update(kwargs[f]) 
					del kwargs[f]
				except:
					pass
		params.update(kwargs)
		return params
		

	def obj_db(self, fields: list[str] | None = None, **kwargs) -> dict:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_DB_fields,
									'include'	: self._include_export_DB_fields,
									'exclude_defaults': True, 
									'by_alias'	: self._export_DB_by_alias 
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.dict(**params)
		

	def obj_src(self, fields: list[str] | None = None, **kwargs) -> dict:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_src_fields,
									'include'	: self._include_export_src_fields,
									'exclude_unset' : True, 
									'by_alias'	: not self._export_DB_by_alias 
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.dict(**params)


	def json_db(self, fields: list[str] | None = None, **kwargs) -> str:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_DB_fields,
									'include'	: self._include_export_DB_fields,
									'exclude_defaults': True, 
									'by_alias'	: self._export_DB_by_alias 
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.json(**params)
		

	def json_src(self, fields: list[str] | None = None,**kwargs) -> str:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_src_fields,
									'include'	: self._include_export_src_fields,
									'exclude_unset' : True, 
									'by_alias'	: not self._export_DB_by_alias 
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.json(**params)


	async def save(self, filename: str) -> int:
		"""Save object JSON into a file"""
		try:
			async with open(filename, 'w') as rf:
				return await rf.write(self.json_src())
		except Exception as err:
			error(f'Error writing replay {filename}: {err}')
		return -1


	@classmethod
	def transform(cls: type[JSONExportableSelf], in_obj: Any) -> Optional[JSONExportableSelf]:
		"""Transform object to out_type if supported"""
		return None


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
					filename : str) -> AsyncGenerator[JSONImportableSelf, None]:
		"""Import from filename, one model per line"""
		try:
			importable : JSONImportableSelf | None
			async with open(filename, 'r') as f:
				async for line in f:
					try:
						importable = cls.from_str(line)
						if importable is not None:
							yield importable
					except ValidationError as err:
						error(f'Could not validate mode: {err}')
					except Exception as err:
						error(f'{err}')				
		except Exception as err:
			error(f'Error importing file {filename}: {err}')
		

class TXTExportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT export"""
	
	@abstractmethod
	def txt_row(self, format : str = '') -> str:
		"""export data as single row of text	"""
		raise NotImplementedError


TXTImportableSelf = TypeVar('TXTImportableSelf', bound='TXTImportable')
class TXTImportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT import"""
	
	@classmethod
	def from_txt(cls: type[TXTImportableSelf], text: str) -> TXTImportableSelf:
		"""Provide CSV row as a dict for csv.DictWriter"""
		raise NotImplementedError


	@classmethod
	async def import_txt(cls : type[TXTImportableSelf], 
					filename : str) -> AsyncGenerator[TXTImportableSelf, None]:
		"""Import from filename, one model per line"""
		try:
			importable : TXTImportableSelf | None
			async with open(filename, 'r') as f:
				async for line in f:
					try:
						importable = cls.from_txt(line)
						if importable is not None:
							yield importable
					except ValidationError as err:
						error(f'Could not validate mode: {err}')
					except Exception as err:
						error(f'{err}')				
		except Exception as err:
			error(f'Error importing file {filename}: {err}')

Exportable = CSVExportable | TXTExportable | JSONExportable
Importable = CSVImportable | JSONImportable | TXTImportable
	

##############################################
#
## Functions
#
##############################################


def get_datestr(_datetime: datetime = datetime.now()) -> str:
	return _datetime.strftime('%Y%m%d_%H%M')


def epoch_now() -> int:
	return int(time())


def is_alphanum(string: str) -> bool:
	try:
		return not compile(r'[^a-zA-Z0-9_]').search(string)
	except:
		error(f'Illegal characters in the table name: {string}')
	return False


def get_type(name: str) -> type[object] | None:
	type_class : type[object]
	try:
		if is_alphanum(name):
			type_class = globals()[name]
		else:
			raise ValueError(f'model {name}() contains illegal characters')
		return type_class
	except Exception as err:
		error(f'Could not find class {name}(): {err}')
	return None

T = TypeVar('T', bound=object)

def get_sub_type(name: str, parent: type[T]) -> Optional[type[T]]:
	if (model := get_type(name)) is not None:
		if issubclass(model, parent):
			return model
	return None


async def alive_bar_monitor(monitor : list[Countable], title : str, 
							total : int | None = None, wait: float = 0.5, 
							*args, **kwargs) -> None:
	"""Create a alive_progress bar for List[Countable]"""
	
	assert len(monitor) > 0, "'monitor' cannot be empty"
	
	prev 	: int = 0
	current : int = 0
			
	with alive_bar(total, *args, title=title, **kwargs) as bar:
		try:
			while total is None or current <= total:
				await sleep(wait)
				current = 0
				for m in monitor:
					current += m.count
				if current != prev:
					bar(current - prev)
				prev = current
				if current == total:
					break
		except CancelledError:
			pass
	
	return None


async def get_url(session: ClientSession, url: str, max_retries : int = MAX_RETRIES) -> str | None:
	"""Retrieve (GET) an URL and return JSON object"""
	assert session is not None, 'Session must be initialized first'
	assert url is not None, 'url cannot be None'

	if not is_url(url):
		raise ValueError(f"URL is malformed: {url}")

	for retry in range(1, max_retries + 1):
		try:
			async with session.get(url) as resp:
				if resp.status == 200:
					debug(f'HTTP request OK: {url}')
					# if logger.level == logging.DEBUG:
					# 	debug(await resp.text())
					return await resp.text()
				else:
					debug(f'HTTP error {resp.status}: {url}')
				if retry == max_retries:
					break
				debug(f'Retrying URL [ {retry}/{max_retries} ]: {url}')
			await sleep(SLEEP)

		except ClientError as err:
			debug(f"Could not retrieve URL: {url} : {err}")
		except CancelledError as err:
			debug(f'Cancelled while still working: {err}')
			break
		except Exception as err:
			debug(f'Unexpected error {err}')
	verbose(f"Could not retrieve URL: {url}")
	return None


async def get_url_JSON(session: ClientSession, url: str, retries : int = MAX_RETRIES) -> Any | None:
	"""Get JSON from URL and return object."""
	
	assert session is not None, "session cannot be None"
	assert url is not None, "url cannot be None"

	try:
		content : str | None = await get_url(session, url, retries)
		if content is None:
			return None		
		return await json.loads(content)
	except ClientResponseError  as err:
		error(f'Client response error: {url}: {err}')
	except Exception as err:
		error(f'Unexpected error: {err}') 
	return None


M = TypeVar('M', bound=BaseModel)

async def get_url_JSON_model(session: ClientSession, url: str, resp_model : type[M], 
						retries : int = MAX_RETRIES) -> Optional[M]:
	"""Get JSON from URL and return object. Validate JSON against resp_model, if given."""
	assert session is not None, "session cannot be None"
	assert url is not None, "url cannot be None"
	content : str | None = None
	try:
		content = await get_url(session, url, retries)
		if content is None:
			error('get_url() returned None')
			return None
		return resp_model.parse_raw(content)		
	except ValidationError as err:
		error(f'{resp_model.__name__}: Validation error {url}: {err}')
		if content is not None:
			debug(f'{content}')
	except Exception as err:
		error(f'Unexpected error: {err}') 
	return None


async def get_urls(session: ClientSession, queue : UrlQueue, stats : EventCounter = EventCounter(),
					max_retries : int = MAX_RETRIES) -> AsyncGenerator[tuple[str, str], None]:
	"""Async Generator to retrieve URLs read from an async Queue"""

	assert session is not None, 'Session must be initialized first'
	assert queue is not None, 'Queue must be initialized first'

	while True:
		try:
			url_item : UrlQueueItemType = await queue.get()					
			url 	: str = url_item[0]
			retry 	: int = url_item[1]  
			if retry > max_retries:
				debug(f'URL has been tried more than {max_retries} times: {url}')
				continue
			if retry > 0:
				debug(f'Retrying URL ({retry}/{max_retries}): {url}')
			else:
				debug(f'Retrieving URL: {url}')
			
			async with session.get(url) as resp:
				if resp.status == 200:
					debug(f'HTTP request OK/{resp.status}: {url}')
					stats.log('OK')
					yield await resp.text(), url
				else:
					error(f'HTTP error {resp.status}: {url}')
					if retry < max_retries:
						retry += 1
						stats.log('retries')				
						await queue.put(url, retry)
					else:
						error(f'Could not retrieve URL: {url}')
						stats.log('failed')

		except CancelledError as err:
			debug(f'Async operation has been cancelled. Ending loop.')
			break


async def get_urls_JSON(session: ClientSession, queue : UrlQueue, stats : EventCounter = EventCounter(),
					max_retries : int = MAX_RETRIES) -> AsyncGenerator[tuple[Any, str], None]:
	"""Async Generator to retrieve JSON from URLs read from an async Queue"""
	
	assert session is not None, 'Session must be initialized first'
	assert queue is not None, 'Queue must be initialized first'
	
	async for content, url in get_urls(session, queue=queue, stats=stats, max_retries=max_retries):
		try:
			yield await json.loads(content), url
		except ClientResponseError as err:
			error(f'Client response error: {url}: {err}')
		except Exception as err:
			error(f'Unexpected error: {err}') 


async def get_urls_JSON_models(session: ClientSession, queue : UrlQueue, resp_model : type[M], 
								stats : EventCounter = EventCounter(),
								max_retries : int = MAX_RETRIES) -> AsyncGenerator[tuple[M, str], None]:
	"""Async Generator to retrieve JSON from URLs read from an async Queue"""
	
	assert session is not None, 'Session must be initialized first'
	assert queue is not None, 'Queue must be initialized first'
	
	async for content, url in get_urls(session, queue=queue, stats=stats, max_retries=max_retries):
		try:
			yield resp_model.parse_raw(content), url
		except ValidationError as err:
			error(f'{resp_model.__name__}(): Validation error: {url}: {err}')		
		except Exception as err:
			error(f'Unexpected error: {err}') 


# def mk_id(account_id: int, last_battle_time: int, tank_id: int = 0) -> ObjectId:
# 	return ObjectId(hex(account_id)[2:].zfill(10) + hex(tank_id)[2:].zfill(6) + hex(last_battle_time)[2:].zfill(8))

FORMAT = Literal['txt', 'json', 'csv']

async def export(Q: Queue[CSVExportable] | Queue[TXTExportable] | Queue[JSONExportable], 
				format : FORMAT, filename: str, force: bool = False, 
				append : bool = False) -> EventCounter:
	"""Export data to file or STDOUT"""
	debug('starting')
	stats : EventCounter = EventCounter('write')
	try:
		
		if format == 'txt':
			stats.merge_child(await export_txt(Q=cast(Queue[TXTExportable], Q), 
											filename=filename, force=force, append=append))
		elif format == 'json':
			stats.merge_child(await export_json(Q=cast(Queue[JSONExportable], Q), 
											filename=filename, force=force, append=append))
		elif format == 'csv':
			stats.merge_child(await export_csv(Q=cast(Queue[CSVExportable], Q), 
											filename=filename, force=force, append=append))
		else:			
			raise ValueError(f'Unknown format: {format}')			
	except Exception as err:
		stats.log('errors')
		error(f'{err}')
	finally:
		return stats


async def export_csv(Q: Queue[CSVExportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter:
	"""Export data to a CSVfile"""
	debug('starting')
	assert isinstance(Q, Queue), 'Q has to be type of asyncio.Queue[CSVExportable]'
	assert type(filename) is str and len(filename) > 0, 'filename has to be str'
	stats : EventCounter = EventCounter('CSV')	
	try:
		dialect 	: Type[Dialect] = excel
		exportable 	: CSVExportable	= await Q.get()
		fields 		: list[str]		= exportable.csv_headers()
		
		if filename == '-':				# STDOUT
			try:
				# print header
				print(dialect.delimiter.join(fields))
				while True:
					try:
						row : dict[str, str |int |float | bool] = exportable.csv_row()
						print(dialect.delimiter.join([ str(row[key]) for key in fields]))
					except KeyError as err:
						error(f'CSVExportable object does not have field: {err}')
					except Exception as err:
						error(f'{err}')
					finally:
						Q.task_done()
					exportable = await Q.get()
			except CancelledError as err:
				debug(f'Cancelled')
			
		else:							# File
			filename += '.csv'
			file_exists : bool = isfile(filename)
			if exists(filename) and (not file_exists or not (force or append)):
				raise FileExistsError(f'Cannot export to {filename }')

			mode : Literal['w', 'a'] = 'w'
			if append and file_exists:
				mode = 'a'				
			else:
				append = False
			debug(f'opening {filename} for writing in mode={mode}')
			async with open(filename, mode=mode, newline='') as csvfile:
				try:
					writer = AsyncDictWriter(csvfile, fieldnames=fields, dialect=dialect)
					if not append:
						await writer.writeheader()
					while True:					
						try:
							# debug(f'Writing row: {exportable.csv_row()}')
							await writer.writerow(exportable.csv_row())
							stats.log('Rows')
						except Exception as err:
							error(f'{err}')
							stats.log('errors')
						finally:
							Q.task_done()
						exportable = await Q.get()
				except CancelledError as err:
					debug(f'Cancelled')
				finally:
					pass
	
	except Exception as err:
		error(f'{err}')
	return stats


async def export_json(Q: Queue[JSONExportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter:
	"""Export data to a JSON file"""
	assert isinstance(Q, Queue), 'Q has to be type of asyncio.Queue[JSONExportable]'
	assert type(filename) is str and len(filename) > 0, 'filename has to be str'
	stats : EventCounter = EventCounter('JSON')
	try:
		exportable 	: JSONExportable
		if filename == '-':			
			while True:
				exportable = await Q.get()
				try:
					print(exportable.json_src())
				except Exception as err:
					error(f'{err}')
				finally:
					Q.task_done()
		else:
			filename += '.json'
			file_exists : bool = isfile(filename)
			if exists(filename) and (not file_exists or not (force or append)):
				raise FileExistsError(f'Cannot export to {filename }')
			mode : Literal['w', 'a'] = 'w'
			if append and file_exists:
				mode = 'a'
			async with open(filename, mode=mode) as txtfile:
				while True:
					exportable = await Q.get()
					try:
						await txtfile.write(exportable.json_src() + linesep)
						stats.log('Rows')
					except Exception as err:
						error(f'{err}')
						stats.log('errors')
					finally:
						Q.task_done()

	except CancelledError as err:
		debug(f'Cancelled')
	except Exception as err:
		error(f'{err}')
	return stats


async def export_txt(Q: Queue[TXTExportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter:
	"""Export data to a text file"""
	assert isinstance(Q, Queue), 'Q has to be type of asyncio.Queue'
	assert type(filename) is str and len(filename) > 0, 'filename has to be str'
	stats : EventCounter = EventCounter('Text')
	try:
		exportable 	: TXTExportable
		if filename == '-':			
			while True:
				exportable = await Q.get()
				try:
					print(exportable.txt_row(format='rich'))
				except Exception as err:
					error(f'{err}')
				finally:
					Q.task_done()
		else:
			filename += '.txt'
			file_exists : bool = isfile(filename)
			if exists(filename) and (not file_exists or not (force or append)):
				raise FileExistsError(f'Cannot export to {filename }')
			mode : Literal['w', 'a'] = 'w'
			if append and file_exists:
				mode = 'a'
			async with open(filename, mode=mode) as txtfile:
				while True:
					exportable = await Q.get()
					try:
						await txtfile.write(exportable.txt_row() + linesep)
						stats.log('rows')
					except Exception as err:
						error(f'{err}')
						stats.log('errors')
					finally:
						Q.task_done()

	except CancelledError as err:
		debug(f'Cancelled')
	except Exception as err:
		error(f'{err}')
	return stats