from asyncio import Queue
from typing import cast
import logging

from .utils import is_url

# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

UrlQueueItemType = tuple[str, int]

class UrlQueue(Queue):

	async def put(self, url : str, retry : int = 0):
		assert isinstance(retry, int) and retry >=0, \
				f"retry has to be positive int, {retry} ({type(retry)}) given"
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