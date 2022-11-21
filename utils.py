import logging
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any, cast, Type, Literal
from abc import ABCMeta, abstractmethod
from aiocsv.writers import AsyncDictWriter
from csv import Dialect, Sniffer, excel
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


class CSVexportable(metaclass=ABCMeta):
	"""Abstract class to provide CSV export"""

	@abstractmethod
	def csv_headers(self) -> list[str]:
		"""Provide CSV headers as list"""
		raise NotImplementedError

	
	@abstractmethod
	def csv_row(self) -> dict[str, str | int | float | bool]:
		"""Provide CSV row as a dict for csv.DictWriter"""
		raise NotImplementedError


class CSVimportable(metaclass=ABCMeta):
	"""Abstract class to provide CSV export"""
	
	@abstractmethod
	def from_csv(self, row: dict[str, Any]) -> Any:
		"""Provide CSV row as a dict for csv.DictWriter"""
		raise NotImplementedError


class JSONexportable(metaclass=ABCMeta):
	"""Abstract class to provide JSON export"""
	
	@classmethod
	def json_formats(cls) -> list[str]:
		return []


	@abstractmethod
	def json_str(self, format: str = 'src') -> str:
		"""Export data as JSON string"""
		raise NotImplementedError

	
	@abstractmethod
	def json_obj(self, format: str = 'src') -> Any:
		"""Export object as JSON object"""
		raise NotImplementedError
		

class TXTexportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT export"""
	
	@abstractmethod
	def txt_row(self, format : str = '') -> str:
		"""export data as single row of text	"""
		raise NotImplementedError

Exportable = CSVexportable | TXTexportable | JSONexportable

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
			debug(f"Could not retrieve URL: {url} : {str(err)}")
		except CancelledError as err:
			debug(f'Queue gets cancelled while still working: {str(err)}')
			break
		except Exception as err:
			debug(f'Unexpected error {str(err)}')
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
		error(f'Client response error: {url}: {str(err)}')
	except Exception as err:
		error(f'Unexpected error: {str(err)}') 
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
		debug(f'Failed to validate response from URL: {url}: {str(err)}')
		if content is not None:
			debug(f'{content}')
	except Exception as err:
		error(f'Unexpected error: {str(err)}') 
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
			error(f'Client response error: {url}: {str(err)}')
		except Exception as err:
			error(f'Unexpected error: {str(err)}') 


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
			error(f'Failed to validate response from URL: {url}: {str(err)}')		
		except Exception as err:
			error(f'Unexpected error: {str(err)}') 


# def mk_id(account_id: int, last_battle_time: int, tank_id: int = 0) -> ObjectId:
# 	return ObjectId(hex(account_id)[2:].zfill(10) + hex(tank_id)[2:].zfill(6) + hex(last_battle_time)[2:].zfill(8))

FORMAT = Literal['txt', 'json', 'csv']

async def export(Q: Queue[CSVexportable] | Queue[TXTexportable] | Queue[JSONexportable], 
				format : FORMAT, filename: str, force: bool = False, 
				append : bool = False) -> EventCounter:
	"""Export data to file or STDOUT"""
	debug('starting')
	stats : EventCounter = EventCounter('write')
	try:
		
		if format == 'txt':
			stats.merge_child(await export_txt(Q=cast(Queue[TXTexportable], Q), 
											filename=filename, force=force, append=append))
		elif format == 'json':
			stats.merge_child(await export_json(Q=cast(Queue[JSONexportable], Q), 
											filename=filename, force=force, append=append))
		elif format == 'csv':
			stats.merge_child(await export_csv(Q=cast(Queue[CSVexportable], Q), 
											filename=filename, force=force, append=append))
		else:			
			raise ValueError(f'Unknown format: {format}')			
	except Exception as err:
		stats.log('errors')
		error(str(err))
	finally:
		return stats



async def export_csv(Q: Queue[CSVexportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter:
	"""Export data to a CSVfile"""
	debug('starting')
	assert isinstance(Q, Queue), 'Q has to be type of asyncio.Queue[CSVexportable]'
	assert type(filename) is str and len(filename) > 0, 'filename has to be str'
	stats : EventCounter = EventCounter('CSV')	
	try:
		dialect 	: Type[Dialect] = excel
		exportable 	: CSVexportable	= await Q.get()
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
						error(f'CSVexportable object does not have field: {err}')
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
			async with open(filename, mode=mode) as csvfile:
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


async def export_json(Q: Queue[JSONexportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter:
	"""Export data to a JSON file"""
	assert isinstance(Q, Queue), 'Q has to be type of asyncio.Queue[JSONexportable]'
	assert type(filename) is str and len(filename) > 0, 'filename has to be str'
	stats : EventCounter = EventCounter('JSON')
	try:
		exportable 	: JSONexportable
		if filename == '-':			
			while True:
				exportable = await Q.get()
				try:
					print(exportable.json_str())
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
						await txtfile.write(exportable.json_str() + linesep)
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


async def export_txt(Q: Queue[TXTexportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter:
	"""Export data to a text file"""
	assert isinstance(Q, Queue), 'Q has to be type of asyncio.Queue'
	assert type(filename) is str and len(filename) > 0, 'filename has to be str'
	stats : EventCounter = EventCounter('Text')
	try:
		exportable 	: TXTexportable
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