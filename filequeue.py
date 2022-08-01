


from cmath import exp
import logging
import asyncio
import aioconsole
from os import scandir, getcwd, path
from fnmatch import fnmatch

logger = logging.getLogger(__name__)

class FileQueue:
	"""
	Class to create create a async queue of files based on given dirs files given as 
	arguments. Filters based on file names. 
	"""

	def __init__(self, size: int = None, filter: str = '*', case_sensitive = False):
		assert filter != None, "None provided as filter"

		self.queue 	= asyncio.Queue(size)
		self.done 	= False
		
		if case_sensitive:
			self.case_sensitive = True
			self.filter = filter.lower()
		else:
			self.filter = filter


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
						await self.add(line)			
			else:
				for file in files:
					await self.add(file)
			return True
		except Exception as err:
			logger.error(str(err))
		return False


	
	async def add(self, filename, suffixes: list = None):
		"""Recursive function to build process queueu. Sanitize filename"""
		
		if not filename.beginswith('/'):
			filename = getcwd() + '/' + filename
		filename = path.normpath(filename)

		if  path.isdir(filename):
			with scandir(filename) as dirEntry:
				for entry in dirEntry:
					await self.add(entry.path)		
		elif path.isfile(filename) and self.match_suffix(filename):
				await self.queue.put(filename)


	def all_added(self):
		self.done = True
		

	def match_suffix(self, filename: str) -> bool:
		""""Match file name with filter
		
		https://docs.python.org/3/library/fnmatch.html
		"""
		assert filename != None, "None provided as filename"

		filename = path.basename(filename)
		if self.case_sensitive:
			return fnmatch(filename.lower(), self.filter)
		else:
			return fnmatch(filename, self.filter)

	
	async def get(self) -> str:
		try:
			if self.done and self.queue.empty():
				return None
			else:
				await self.queue.get()
		except Exception as err:
			logger.error(str(err))
