import logging
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any, cast, Type, Literal, TypeVar, ClassVar, Self, Mapping
from abc import ABCMeta, abstractmethod
from aiofiles import open
from aiocsv.writers import AsyncDictWriter
from aiocsv.readers import AsyncDictReader
from csv import Dialect, Sniffer, excel, QUOTE_NONNUMERIC
from sys import stdout
from os.path import isfile, exists
from os import linesep
from aiofiles import open
import json
from time import time
from aiohttp import ClientSession, ClientResponse, ClientError, ClientResponseError
from pydantic import BaseModel, ValidationError
from asyncio import sleep, CancelledError, Queue, AbstractEventLoop
from pyutils.eventcounter import EventCounter
from urllib.parse import urlparse
from collections.abc import AsyncGenerator

# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

# Constants
MAX_RETRIES : int   = 3
SLEEP       : float = 1


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


CSVImportableSelf = TypeVar('CSVImportableSelf', bound='CSVImportable')
class CSVImportable(metaclass=ABCMeta):
	"""Abstract class to provide CSV export"""
	
	@classmethod
	def from_csv(cls: type[CSVImportableSelf], row: dict[str, Any]) -> CSVImportableSelf:
		"""Provide CSV row as a dict for csv.DictWriter"""
		raise NotImplementedError


	@classmethod
	def _set_field_types(cls,row: dict[str, Any], fields: list[str], value_type: type ) -> dict[str, Any]:
		for field in fields:
			if field in row:
				if row[field] == '':
					del row[field]
				else:
					row[field] = value_type(row[field])
					KESKEN
		return row


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
						importable = cls.from_csv(row)
						if importable is not None:
							yield importable
					except ValidationError as err:
						error(f'Could not validate mode: {err}')
					except Exception as err:
						error(f'{err}')				
		except Exception as err:
			error(f'Error importing file {filename}: {err}')



TypeExcludeDict = Mapping[int | str, Any]


class JSONExportable(BaseModel):
	_exclude_export_DB_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_exclude_export_src_fields	: ClassVar[Optional[TypeExcludeDict]] = None

	def obj_db(self, **kwargs) -> dict:
		return self.dict(exclude=self._exclude_export_DB_fields, exclude_defaults=True, 
							by_alias=True, **kwargs)
		

	def obj_src(self, **kwargs) -> dict:
		return self.dict(exclude=self._exclude_export_src_fields, 
							exclude_unset=True, by_alias=False, **kwargs)


	def json_db(self, **kwargs) -> str:
		return self.json(exclude=self._exclude_export_DB_fields, exclude_defaults=True, 
							by_alias=True, **kwargs)
		

	def json_src(self, **kwargs) -> str:
		return self.json(exclude=self._exclude_export_src_fields, 
							exclude_unset=True, by_alias=False, **kwargs)


	async def save(self, filename: str) -> int:
		"""Save object JSON into a file"""
		try:
			async with open(filename, 'w') as rf:
				return await rf.write(self.json_src())
		except Exception as err:
			error(f'Error writing replay {filename}: {err}')
		return -1


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


def is_url(url) -> bool:
	try:
		result = urlparse(url)
		return all([result.scheme, result.netloc])
	except ValueError:
		return False


from asyncio import Queue

UrlQueueItemType = tuple[str, int]

class UrlQueue(Queue):

	async def put(self, url : str, retry : int = 0):
		assert type(retry) is int, f"retry has to be int, {type(retry)} given"
		if is_url(url):
			return super().put((url, retry))
		raise ValueError(f'malformed URL given: {url}')
		

	async def get(self) -> UrlQueueItemType:
		while True:
			item = await super().get()
			if type(item) is not UrlQueueItemType:
				error('Queue item is not type of Tuple[str, int]')
				continue
			return cast(UrlQueueItemType, item)
		

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
			debug(f'Queue gets cancelled while still working: {err}')
			break
		except Exception as err:
			debug(f'Unexpected error {err}')
	debug(f"Could not retrieve URL: {url}")
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


async def get_url_JSON_model(session: ClientSession, url: str, resp_model : type[BaseModel], 
						retries : int = MAX_RETRIES) -> BaseModel | None:
	"""Get JSON from URL and return object. Validate JSON against resp_model, if given."""
	assert session is not None, "session cannot be None"
	assert url is not None, "url cannot be None"
	content : str | None = None
	try:
		content = await get_url(session, url, retries)
		if content is None:
			return None
		return resp_model.parse_raw(content)		
	except ValidationError as err:
		debug(f'Failed to validate response from URL: {url}: {err}')
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


async def get_urls_JSON_models(session: ClientSession, queue : UrlQueue, resp_model : type[BaseModel], 
								stats : EventCounter = EventCounter(),
								max_retries : int = MAX_RETRIES) -> AsyncGenerator[tuple[BaseModel, str], None]:
	"""Async Generator to retrieve JSON from URLs read from an async Queue"""
	
	assert session is not None, 'Session must be initialized first'
	assert queue is not None, 'Queue must be initialized first'
	
	async for content, url in get_urls(session, queue=queue, stats=stats, max_retries=max_retries):
		try:
			yield resp_model.parse_raw(content), url
		except ValidationError as err:
			error(f'Failed to validate response from URL: {url}: {err}')		
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
		error(str(err))
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
						error(str(err))
					finally:
						Q.task_done()
					exportable = await Q.get()
			except CancelledError as err:
				debug(f'Cancelled')
			
		else:							# File
			filename += '.csv'
			file_exists : bool = isfile(filename)
			if exists(filename) and (not file_exists or not (force or append)):
				raise FileExistsError(f'Cannot export accounts to {filename }')

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
							error(str(err))
							stats.log('errors')
						finally:
							Q.task_done()
						exportable = await Q.get()
				except CancelledError as err:
					debug(f'Cancelled')
				finally:
					pass
					#await csvfile.flush()
	
	except Exception as err:
		error(str(err))
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
					error(str(err))
				finally:
					Q.task_done()
		else:
			filename += '.json'
			file_exists : bool = isfile(filename)
			if exists(filename) and (not file_exists or not (force or append)):
				raise FileExistsError(f'Cannot export accounts to {filename }')
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
						error(str(err))
						stats.log('errors')
					finally:
						Q.task_done()

	except CancelledError as err:
		debug(f'Cancelled')
	except Exception as err:
		error(str(err))
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
					print(exportable.txt_row())
				except Exception as err:
					error(str(err))
				finally:
					Q.task_done()
		else:
			filename += '.txt'
			file_exists : bool = isfile(filename)
			if exists(filename) and (not file_exists or not (force or append)):
				raise FileExistsError(f'Cannot export accounts to {filename }')
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
						error(str(err))
						stats.log('errors')
					finally:
						Q.task_done()

	except CancelledError as err:
		debug(f'Cancelled')
	except Exception as err:
		error(str(err))
	return stats