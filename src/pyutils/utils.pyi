import logging
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Any, cast, Type, Literal, Sequence, TypeVar, ClassVar,\
	 Union, Mapping, Callable, Iterator, Self, Generic, AsyncGenerator
from abc import ABCMeta, ABC, abstractmethod
from re import compile
from itertools import islice
from aiofiles import open
from aiocsv.writers import AsyncDictWriter
from aiocsv.readers import AsyncDictReader
from alive_progress import alive_bar 				# type: ignore
from csv import Dialect, Sniffer, excel, QUOTE_NONNUMERIC
from ast import literal_eval
from os.path import isfile, exists
from os import linesep
from aiofiles import open
import json
from time import time
from aiohttp import ClientSession, ClientResponse, ClientError, ClientResponseError
from pydantic import BaseModel, ValidationError
from asyncio import sleep, CancelledError, Queue

from .eventcounter import EventCounter
from .urlqueue import UrlQueue, UrlQueueItemType, is_url


# Constants
MAX_RETRIES : int   = 3
SLEEP       : float = 1


T= TypeVar('T')
class Countable(ABC):
	
	@property
	@abstractmethod
	def count(self) -> int: ...


##############################################
#
## Functions
#
##############################################


def get_datestr(_datetime: datetime = datetime.now()) -> str: ...

def epoch_now() -> int: ...

def is_alphanum(string: str) -> bool: ...

def chunker(it : Sequence[T], size: int) -> Iterator[list[T]]: ...
	
def get_type(name: str) -> type[object] | None: ...
	
def get_sub_type(name: str, parent: type[T]) -> Optional[type[T]]: ...
	
async def alive_bar_monitor(monitor : list[Countable], 
			    			title : str, 
							total : int | None = None, 
							wait: float = 0.5,
							batch: int = 1, 
							*args, **kwargs) -> None: ...
	
async def get_url(session: ClientSession, url: str, max_retries : int = MAX_RETRIES) -> str | None: ...

async def get_url_JSON(session: ClientSession, url: str, retries : int = MAX_RETRIES) -> Any | None: ...

M = TypeVar('M', bound=BaseModel)

async def get_url_JSON_model(session: ClientSession, 
			     			url: str, 
			     			resp_model : type[M], 
							retries : int = MAX_RETRIES
							) -> Optional[M]: ...

async def get_url_JSON_models(session: ClientSession, 
			      				url: str, 
								item_model : type[M], 
								retries : int = MAX_RETRIES
								) -> Optional[list[M]]: ...

async def get_urls(session: ClientSession, 
		   			queue : UrlQueue, 
					stats : EventCounter = EventCounter(),
					max_retries : int = MAX_RETRIES
					) -> AsyncGenerator[tuple[str, str], None]: ...

async def get_urls_JSON(session: ClientSession, 
						queue : UrlQueue, 
						stats : EventCounter = EventCounter(),
						max_retries : int = MAX_RETRIES
						) -> AsyncGenerator[tuple[Any, str], None]: ...

async def get_urls_JSON_models(session: ClientSession, 
			       				queue : UrlQueue, resp_model : type[M], 
								stats : EventCounter = EventCounter(),
								max_retries : int = MAX_RETRIES
								) -> AsyncGenerator[tuple[M, str], None]: ...
