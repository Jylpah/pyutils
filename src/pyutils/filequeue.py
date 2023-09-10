## -----------------------------------------------------------
#### Class FileQueue(asyncio.Queue)
#
#  Class to build async Queue of files based on arguments given.
#  Supports filtering
#
## -----------------------------------------------------------

import logging
import asyncio

# from asyncio import Queue
import aioconsole  # type: ignore
from os import scandir, path
from fnmatch import fnmatch, fnmatchcase
from typing import Optional
from .iterablequeue import IterableQueue, QueueDone

logger = logging.getLogger(__name__)
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


# inherit from asyncio.Queue?
class FileQueue(IterableQueue):
    """
    Class to create create a async queue of files based on given dirs files given as
    arguments. Filters based on file names.
    """

    def __init__(
        self,
        base: Optional[str] = None,
        filter: str = "*",
        exclude: bool = False,
        case_sensitive: bool = True,
        **kwargs,
    ):
        # assert maxsize >= 0, "maxsize has to be >= 0"
        assert isinstance(case_sensitive, bool), "case_sensitive has to be bool"
        assert isinstance(filter, str), "filter has to be string"

        # debug(f"maxsize={str(maxsize)}, filter='{filter}'")
        super().__init__(count_items=True, **kwargs)
        self._base: Optional[str] = base
        # self._done: bool = False
        self._case_sensitive: bool = False
        self._exclude: bool = False
        self.set_filter(filter=filter, exclude=exclude, case_sensitive=case_sensitive)

    def set_filter(
        self,
        filter: str = "*",
        exclude: bool = False,
        case_sensitive: bool = False,
    ):
        """set filtering logic. Only set (!= None) params are changed"""
        assert isinstance(case_sensitive, bool), "case_sensitive must be type of bool"
        assert isinstance(exclude, bool), "exclude must be type of bool"

        self._case_sensitive = case_sensitive
        self._exclude = exclude
        if self._case_sensitive:
            self._filter = filter.lower()
        else:
            self._filter = filter
        debug(
            "filter=%s exclude=%b, case_sensitive=%b",
            str(self._filter),
            self._exclude,
            self._case_sensitive,
        )

    async def mk_queue(self, files: list[str]) -> bool:
        """Create file queue from arguments given
        '-' denotes for STDIN
        """
        assert files is not None and len(files) > 0, "No files given to process"
        await self.add_producer()
        try:
            if files[0] == "-":
                stdin, _ = await aioconsole.get_standard_streams()
                while True:
                    line = (await stdin.readline()).decode("utf-8").removesuffix("\n")
                    if not line:
                        break
                    else:
                        if self._base is None:
                            await self.put(line)
                        else:
                            await self.put(path.join(self._base, line))
            else:
                for file in files:
                    if self._base is None:
                        await self.put(file)
                    else:
                        await self.put(path.join(self._base, file))
        except Exception as err:
            error(f"{err}")
        return await self.finish()

    async def put(self, filename: str) -> None:
        """Recursive function to build process queueu. Sanitize filename"""
        assert (
            filename is not None and len(filename) > 0
        ), "None/zero-length filename given as input"

        try:
            # filename = path.normpath(filename)   # string operation
            if path.isdir(filename):
                with scandir(filename) as dirEntry:
                    for entry in dirEntry:
                        await self.put(entry.path)
            elif path.isfile(filename) and self._match(filename):
                debug(f"Adding file to queue: {filename}")
                await super().put(filename)
                # self._count += 1
        except Exception as err:
            error(f"{err}")
        return None

    # def count(self) -> int:
    #     """Return the number of items added to the queue"""
    #     return self._count

    def _match(self, filename: str) -> bool:
        """ "Match file name with filter

        https://docs.python.org/3/library/fnmatch.html
        """
        assert filename is not None, "None provided as filename"
        try:
            filename = path.basename(filename)

            m: bool
            if self._case_sensitive:
                m = fnmatch(filename, self._filter)
            else:
                m = fnmatchcase(filename, self._filter)
            return m != self._exclude
        except Exception as err:
            error(f"{err}")
        return False
