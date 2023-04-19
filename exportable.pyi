from typing import Optional, cast, Type, Any,Literal, Sequence, TypeVar, ClassVar,\
	 Union, Mapping, Callable, Generic
from asyncio import Queue
from abc import ABCMeta, abstractmethod
from pydantic import BaseModel
from bson.objectid import ObjectId

from .eventcounter import EventCounter

TypeExcludeDict = Mapping[int | str, Any]

D = TypeVar('D', bound='JSONExportable')
J = TypeVar('J', bound='JSONExportable')
O = TypeVar('O', bound='JSONExportable')

DESCENDING 	: Literal[-1] 	  = -1
ASCENDING	: Literal[1]	  = 1
TEXT 		: Literal['text'] = 'text'

Idx 				= Union[str, int, ObjectId]
BackendIndexType 	= Literal[-1, 1, 'text']
BackendIndex 		= tuple[str, BackendIndexType]
I = TypeVar('I', bound=Idx)

class TXTExportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT export"""
	
	@abstractmethod
	def txt_row(self, format : str = '') -> str: ...


class CSVExportable(metaclass=ABCMeta):
	"""Abstract class to provide CSV export"""

	@abstractmethod
	def csv_headers(self) -> list[str]: ...
		
	@abstractmethod
	def csv_row(self) -> dict[str, str | int | float | bool]: ...
		
	def clear_None(self, 
					res: dict[str, str | int | float | bool | None]
					) -> dict[str, str | int | float | bool]: ...


class JSONExportable(Generic[J], BaseModel):

	@classmethod
	def register_transformation(cls : type[J], 
			     				obj_type: type[D], 
								method: Callable[[D], 
										Optional[J]]) -> None: ...
	
	@classmethod
	def transform(cls : type[J], 
				 in_obj: D) -> Optional[J]:  ...
		
	@classmethod
	def transform_obj(cls : type[J], 
					  obj: Any, 
					  in_type: type[D] | None = None) -> Optional[J]: ...
	
	@classmethod
	def transform_objs(cls, 
					  objs: Sequence[Any], 
					  in_type: type[D] | None = None) -> list[J]: ...

	def _export_helper(self, params: dict[str, Any], 
						fields: list[str] | None = None, **kwargs) -> dict: ...
	
	def obj_db(self, fields: list[str] | None = None, **kwargs) -> dict: ...
	
	def obj_src(self, fields: list[str] | None = None, **kwargs) -> dict: ...
	
	def json_db(self, fields: list[str] | None = None, **kwargs) -> str: ...
	
	def json_src(self, fields: list[str] | None = None,**kwargs) -> str: ...
	
	async def save(self, filename: str) -> int: ...
	
	@property
	def index(self) -> Idx: ...
	
	@property
	def indexes(self) -> dict[str, Idx]: ...
	
	@classmethod
	def backend_indexes(cls) -> list[list[tuple[str, BackendIndexType]]]: ...		

FORMAT = Literal['txt', 'json', 'csv']

async def export(Q: Queue[CSVExportable] | Queue[TXTExportable] | Queue[JSONExportable], 
				format : FORMAT, filename: str, force: bool = False, 
				append : bool = False) -> EventCounter: ...


async def export_csv(Q: Queue[CSVExportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter: ...

async def export_json(Q: Queue[JSONExportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter: ...
	

async def export_txt(Q: Queue[TXTExportable], filename: str, 
						force: bool = False, append : bool = False) -> EventCounter: ...