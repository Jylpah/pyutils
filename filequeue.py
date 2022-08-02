


from cmath import exp
import logging
import asyncio
import aioconsole
from os import scandir, getcwd, path
from fnmatch import fnmatch

logger = logging.getLogger(__name__)

# inherit from asyncio.Queue? 
class FileQueue(asyncio.Queue):
	"""
	Class to create create a async queue of files based on given dirs files given as 
	arguments. Filters based on file names. 
	"""

	def __init__(self, maxsize=0, filter: str = '*', exclude: bool = False, 
				case_sensitive = False):
		assert filter != None, "None provided as filter"
		logger.debug(f"maxsize={str(maxsize)}, filter='{filter}', exclude={str(exclude)}, case_sensitive={str(case_sensitive)}")
		super().__init__(maxsize)
		self._done 			= False
		self._exclude 		= exclude
		self.case_sensitive = case_sensitive
		if self.case_sensitive:			
			self._filter = filter.lower()
		else:
			self._filter = filter


	async def mk_queue(self, files: list):
		"""Create file queue from arguments given
			'-' denotes for STDIN
		"""
		assert files != None and len(files) > 0, "No files given to process"

		try:		
			if files[0] == '-':
				stdin, _ = await aioconsole.get_standard_streams()
				while True:
					line = (await stdin.readline()).decode('utf-8').removesuffix("\n")
					if not line: 
						break
					else:
						await self.put(line)			
			else:
				for file in files:
					await self.put(file)
			return True
		except Exception as err:
			logger.error(str(err))
		return False

	
	async def put(self, filename) -> bool:
		"""Recursive function to build process queueu. Sanitize filename"""
		assert filename != None and len(filename) > 0, "None/zero-length filename given as input"
		
		try:			
			filename = path.normpath(filename)
			if  path.isdir(filename):
				with scandir(filename) as dirEntry:
					for entry in dirEntry:
						await self.put(entry.path)		
			elif path.isfile(filename) and self._match(filename):
				logger.debug(f"Adding file to queue: {filename}")
				await super().put(filename)
				return True
		except Exception as err:
			logger.error(str(err))
		return False


	def _match(self, filename: str) -> bool:
		""""Match file name with filter
		
		https://docs.python.org/3/library/fnmatch.html
		"""
		assert filename != None, "None provided as filename"
		try:
			filename = path.basename(filename)

			if self.case_sensitive:
				filename = filename.lower()
			
			m = fnmatch(filename, self._filter)
			if self._exclude:
				return not m
			else:
				return m
		except Exception as err:
			logger.error(str(err))
		return False
