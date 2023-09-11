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
from pathlib import Path
from typing import Optional
from .iterablequeue import IterableQueue, QueueDone

logger = logging.getLogger(__name__)
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug


# inherit from asyncio.Queue?
class FileQueue(IterableQueue[Path]):
    """
    Class to create create a async queue of files based on given dirs files given as
    arguments. Filters based on file names.
    """

    def __init__(
        self,
        base: Optional[Path] = None,
        filter: str = "*",
        exclude: bool = False,
        case_sensitive: bool = True,
        **kwargs,
    ):
        # assert maxsize >= 0, "maxsize has to be >= 0"
        assert isinstance(case_sensitive, bool), "case_sensitive has to be bool"
        assert isinstance(filter, str), "filter has to be string"
        assert base is None or isinstance(base, Path), "base has to be Path or None"

        # debug(f"maxsize={str(maxsize)}, filter='{filter}'")
        super().__init__(count_items=True, **kwargs)
        self._base: Optional[Path] = base
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
        path: Path
        file: str
        try:
            if files[0] == "-":
                stdin, _ = await aioconsole.get_standard_streams()
                while (line := await stdin.readline()) is not None:
                    path = Path(line.decode("utf-8").removesuffix("\n"))
                    if self._base is not None:
                        path = self._base / path
                    await self.put(path)
            else:
                for file in files:
                    path = Path(file)
                    if self._base is not None:
                        path = self._base / path
                    await self.put(path)
        except Exception as err:
            error(f"{err}")
        return await self.finish()

    async def put(self, path: Path) -> None:
        """Recursive function to build process queueu. Sanitize filename"""
        assert isinstance(path, Path), "path has to be type Path()"
        try:
            if path.is_dir():
                for child in path.rglob(self._filter):
                    if child.is_file():
                        debug("Adding file to queue: %s", str(child))
                        await super().put(child)
            elif path.is_file() and self.match(path):
                debug("Adding file to queue: %s", str(path))
                await super().put(path)
                # self._count += 1
        except Exception as err:
            error(f"{err}")
        return None

    def match(self, path: Path) -> bool:
        """ "Match file name with filter

        https://docs.python.org/3/library/fnmatch.html
        """
        assert isinstance(path, Path), "path has to be type Path()"
        try:
            m: bool
            if self._case_sensitive:
                m = fnmatch(path.name, self._filter)
            else:
                m = fnmatchcase(path.name, self._filter)
            return m != self._exclude
        except Exception as err:
            error(f"{err}")
        return False
