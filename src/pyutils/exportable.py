import logging
from typing import Optional, cast, Type, Self, Any,Literal, Sequence, TypeVar, ClassVar,\
	 Union, Callable, Generic, get_args
from collections.abc import MutableMapping
from pydantic import BaseModel, ValidationError
from asyncio import CancelledError, Queue
from aiofiles import open
from os.path import isfile, exists
from os import linesep
from aiocsv.writers import AsyncDictWriter
from csv import Dialect, excel, QUOTE_NONNUMERIC
from bson.objectid import ObjectId
from abc import ABCMeta, abstractmethod

from .eventcounter import EventCounter

# Setup logging
logger	= logging.getLogger()
error 	= logger.error
message	= logger.warning
verbose	= logger.info
debug	= logger.debug

TypeExcludeDict = MutableMapping[int | str, Any]

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


########################################################
#
# TXTExportable()
#
########################################################


class TXTExportable(metaclass=ABCMeta):
	"""Abstract class to provide TXT export"""

	@abstractmethod
	def txt_row(self, format : str = '') -> str:
		"""export data as single row of text	"""
		raise NotImplementedError


########################################################
#
# CSVExportable()
#
########################################################


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


########################################################
#
# JSONExportable()
#
########################################################


def call_clsinit(cls):
	"""Decorator to call cls._clsinit to init the class. 
		This is needed for transformation register to work"""
	cls._clsinit()
	return cls


class JSONExportable(BaseModel):

	_exclude_export_DB_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_exclude_export_src_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_include_export_DB_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_include_export_src_fields	: ClassVar[Optional[TypeExcludeDict]] = None
	_export_DB_by_alias			: bool = True
	_exclude_defaults 			: bool = True
	_exclude_unset 				: bool = True
	_exclude_none				: bool = True
	
	# This has to be set again in every sub class
	_transformations : ClassVar[MutableMapping[Type, Callable[[Any], Optional[Self]]]] = dict()

	@classmethod
	def register_transformation(cls,
			     				obj_type: type[D],
								method: Callable[[D], Optional[Self]],
								) -> None:
		"""Register transformations"""
		cls._transformations[obj_type] = method
		return None
	

	@classmethod
	def _clsinit(cls):
		"""Init new dict for each class. Otherwise the dict() is shared among the subclasses"""
		cls._transformations = dict()


	@classmethod
	def transform(cls,
				  in_obj: Any) -> Optional[Self]:
		"""Transform object to out_type if supported"""
		try:
			# transform_func : Callable[[D], Optional[Self]] = cls._transformations[type(in_obj)]
			return cls._transformations[type(in_obj)](in_obj) # type: ignore
		except Exception as err:
			debug(f'failed to transform {type(in_obj)} to {cls}: {err}')
		return None


	@classmethod
	def transform_obj(cls,
					  obj: Any,
					  in_type: type[D] | None = None) -> Optional[Self]:
		"""Transform object to class' object"""
		try:
			obj_in : JSONExportable
			# debug(f'cls: {cls}, obj: {type(obj)}, in_type: {in_type}')
			if type(obj) is cls:
				return obj
			elif in_type is cls:
				return cls.parse_obj(obj)
			elif in_type is None:
				if isinstance(obj, JSONExportable):
					obj_in = obj
				else:
					raise ValueError("if if 'in_type' is not set, 'obj' has to be JSONExportable")
			elif type(obj) is in_type:		
				obj_in = obj
			else:
				# debug('transform(obj_in)')
				obj_in = in_type.parse_obj(obj)

			res : Optional[Self] = cls.transform(obj_in)
			if res is not None:
				# debug('transform(): OK')
				return res
			else:
				# debug('transform(): failed')
				return cls.parse_obj(obj_in.obj_db())

		except ValidationError as err:
			error(f'Could not validate {in_type} or transform it to {cls}: {obj}')
			error(f'{err}')
		except Exception as err:
			error(f'Could not export object type={in_type} to type={cls}')
			error(f'{err}: {obj}')
		return None


	@classmethod
	def transform_objs(cls,
					  objs: Sequence[Any],
					  in_type: type[D] | None = None) -> list[Self]:
		"""Transform a list of objects"""
		return [ out for obj in objs if (out:= cls.transform_obj(obj, in_type=in_type)) is not None ]


	def _export_helper(self, params: dict[str, Any],
						fields: list[str] | None = None, **kwargs) -> dict:
		"""Helper func to process params for obj/src export funcs"""
		if fields is not None:
			del params['exclude']
			params['include'] = { f: True for f in fields }
			params['exclude_defaults'] 	= False
			params['exclude_unset'] 	= False
			params['exclude_none'] 	= False
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
									'exclude_defaults': self._exclude_defaults,
									'by_alias'	: self._export_DB_by_alias
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.dict(**params)


	def obj_src(self, fields: list[str] | None = None, **kwargs) -> dict:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_src_fields,
									'include'	: self._include_export_src_fields,
									'exclude_unset' : self._exclude_unset,
									'exclude_none': self._exclude_none,
									'by_alias'	: not self._export_DB_by_alias
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.dict(**params)


	def json_db(self, fields: list[str] | None = None, **kwargs) -> str:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_DB_fields,
									'include'	: self._include_export_DB_fields,
									'exclude_defaults': self._exclude_defaults,									
									'by_alias'	: self._export_DB_by_alias
									}
		params = self._export_helper(params=params, fields=fields, **kwargs)
		return self.json(**params)


	def json_src(self, fields: list[str] | None = None,**kwargs) -> str:
		params: dict[str, Any] = {	'exclude' 	: self._exclude_export_src_fields,
									'include'	: self._include_export_src_fields,
									'exclude_unset' : self._exclude_unset,
									'exclude_none': self._exclude_none,
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


	@property
	def index(self) -> Idx:
		"""return backend index"""
		raise NotImplementedError

	@property
	def indexes(self) -> dict[str, Idx]:
		"""return backend indexes"""
		raise NotImplementedError


	@classmethod
	def backend_indexes(cls) -> list[list[tuple[str, BackendIndexType]]]:
		"""return backend search indexes"""
		raise NotImplementedError


EXPORT_FORMAT = Literal['txt', 'json', 'csv']
EXPORT_FORMATS = ['txt', 'json', 'csv']



async def export_csv(Q: Queue[CSVExportable], 
					 filename: str,
					 force: bool = False, 
					 append : bool = False) -> EventCounter:
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
			if not filename.lower().endswith('csv'):
				filename = f'{filename}.csv'
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


async def export_json(Q: Queue[JSONExportable], 
					  filename: str,
					  force: bool = False, 
					  append : bool = False
					  ) -> EventCounter:
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
			if not filename.lower().endswith('json'):
				filename = f'{filename}.json'
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


async def export_txt(Q: Queue[TXTExportable], 
					 filename: str,
					 force: bool = False, 
					 append : bool = False) -> EventCounter:
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
			if not filename.lower().endswith('txt'):
				filename = f'{filename}.txt'
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


async def export(Q: Queue[CSVExportable] | Queue[TXTExportable] | Queue[JSONExportable],
				format : EXPORT_FORMAT, 
				filename: str, 
				force: bool = False,
				append : bool = False) -> EventCounter:
	"""Export data to file or STDOUT"""
	debug('starting')
	stats : EventCounter = EventCounter('write')

	if filename != '-':
		for export_format in EXPORT_FORMATS:
			if filename.endswith(export_format) and export_format in get_args(EXPORT_FORMAT):
				format = cast(EXPORT_FORMAT, export_format)

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

