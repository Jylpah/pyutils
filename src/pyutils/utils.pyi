from datetime import datetime
from typing import Optional, Any, Sequence, TypeVar, Iterator, AsyncGenerator
from abc import ABC, abstractmethod
from aiohttp import ClientSession
from pydantic import BaseModel

from .eventcounter import EventCounter
from .urlqueue import UrlQueue


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
