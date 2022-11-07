import logging
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any, cast
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
					return await resp.text()
				else:
					error(f'HTTP error {resp.status}: {url}')
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

	try:
		content : str | None = await get_url(session, url, retries)
		if content is None:
			return None
		return resp_model.parse_raw(content)		
	except ValidationError as err:
		error(f'Failed to validate response from URL: {url}: {str(err)}')
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


def mk_id(account_id: int, last_battle_time: int, tank_id: int = 0) -> ObjectId:
	return ObjectId(hex(account_id)[2:].zfill(10) + hex(tank_id)[2:].zfill(6) + hex(last_battle_time)[2:].zfill(8))