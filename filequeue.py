


from cmath import exp
import logging
import asyncio
import aioconsole
from os import scandir, path
from fnmatch import fnmatch

logger = logging.getLogger(__name__)

class FileQueue:

	def __init__(self, filter: str = '*', size: int = None, case_sensitive = False):
		assert filter != None, "None provided as filter"

		self.queue 	= asyncio.Queue(size)
		self.done 	= False
		
		if case_sensitive:
			self.case_sensitive = True
			self.filter = filter.lower()
		else:
			self.filter = filter


	async def add_file(self, filename, suffixes: list = None):
		"""Recursive function to build process queueu"""
		if  path.isdir(filename):
			with scandir(filename) as dirEntry:
				for entry in dirEntry:
					await self.add_file(entry.path)		
		elif path.isfile(filename):
			if self.match_suffix(filename):
				await self.queue.put(filename)


	def files_added(self):
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
