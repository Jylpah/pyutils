## -----------------------------------------------------------
#### Class ThrottledClientSession(aiohttp.ClientSession)
#
#  Rate-limited async http client session
#
#  Inherits aiohttp.ClientSession 
## -----------------------------------------------------------

from typing import Optional, Union
import aiohttp

class ThrottledClientSession(aiohttp.ClientSession):

	def __init__(self, rate_limit: float = 0, filters: list[str] = list() , 
				limit_filtered: bool = False, re_filter: bool = False, *args,**kwargs) -> None: ...

	@classmethod
	def print_stats(cls, stats: dict[str, float]) -> str: ...

	def _get_sleep(self) -> float: ...

	def get_rate(self) -> float: ...

	def get_stats(self) -> dict[str, float]: ...

	def get_stats_str(self) -> str: ...
	
	def reset_counters(self) -> dict[str, float]: ...
	
	def set_rate_limit(self, rate_limit: float = 0) -> float: ...
	
	async def close(self) -> None: ...
	
	async def _filler(self) -> None: ...
	
	async def _request(self, *args,**kwargs) -> aiohttp.ClientResponse: ...
	
	def is_limited(self, *args: str) -> bool: ...
