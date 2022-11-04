import logging
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any
from time import time
from aiohttp import ClientSession, ClientError, ClientResponse
from pydantic import BaseModel, ValidationError
from asyncio import sleep, CancelledError
from urllib.parse import urlparse

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


async def get_url_JSON_model(session: ClientSession, url: str, resp_model : BaseModel, 
						retries : int = MAX_RETRIES) -> BaseModel | None:
	"""Get JSON from URL and return object. Validate JSON against resp_model, if given."""
	assert session is not None, "session cannot be None"
	assert url is not None, "url cannot be None"

	try:
		resp : ClientResponse | None = await get_url(session, url, retries)
		if resp is None:
			return None
		return resp_model.parse_raw(await resp.text())		
	except ValidationError as err:
		error(f'Failed to validate response from URL: {url}: {str(err)}')
	except Exception as err:
		error(f'Unexpected Exception: {str(err)}') 
	return None


async def get_url_JSON(session: ClientSession, url: str, retries : int = MAX_RETRIES) -> Any | None:
	"""Get JSON from URL and return object."""
	assert session is not None, "session cannot be None"
	assert url is not None, "url cannot be None"

	try:
		resp : ClientResponse | None = await get_url(session, url, retries)
		if resp is None:
			return None
		
		return await resp.json()
	except ValidationError as err:
		error(f'Failed to validate response from URL: {url}: {str(err)}')
	except Exception as err:
		error(f'Unexpected Exception: {str(err)}') 
	return None


async def get_url(session: ClientSession, url: str, retries : int = MAX_RETRIES) -> ClientResponse | None:
	"""Retrieve (GET) an URL and return JSON object"""

	assert session is not None, 'Session must be initialized first'
	assert url is not None, 'url cannot be None'

	if not is_url(url):
		raise ValueError(f"URL is malformed: {url}")

	for retry in range(1, retries + 1):
		try:
			async with session.get(url) as resp:
				if resp.status == 200:
					logging.debug(f'HTTP request OK: {url}')
					return resp
				else:
					logging.error(f'HTTP error {str(resp.status)}: {url}')
				if retry == retries:
					break
				logging.debug(f'Retrying URL [ {str(retry)}/{str(retries)} ]: {url}')
			await sleep(SLEEP)

		except ClientError as err:
			logging.debug(f"Could not retrieve URL: {url} : {str(err)}")
		except CancelledError as err:
			logging.debug(f'Queue gets cancelled while still working: {str(err)}')
			break
		except Exception as err:
			logging.debug(f'Unexpected Exception {str(err)}')
	logging.debug(f"Could not retrieve URL: {url}")
	return None

			
def mk_id(account_id: int, last_battle_time: int, tank_id: int = 0) -> ObjectId:
	return ObjectId(hex(account_id)[2:].zfill(10) + hex(tank_id)[2:].zfill(6) + hex(last_battle_time)[2:].zfill(8))