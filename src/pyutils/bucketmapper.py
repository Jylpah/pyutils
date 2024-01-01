from operator import attrgetter
from bisect import bisect, insort, bisect_left
from typing import TypeVar, Generic, Optional
import logging

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug

T = TypeVar("T")

###############################################################################
#
## WARNING: This class does not perform as well as
#  sortedcollections.NearestDict()
#
###############################################################################


class BucketMapper(Generic[T]):
    """BucketMapper() is a generic class for mapping object based on a
    numeric, discrete key and retrieving objects by value that is
    less that the key. see python bisect module"""

    def __init__(self, attr: str):
        self._key = attrgetter(attr)
        self._data: list[T] = list()

    def insert(self, item: T) -> None:
        insort(self._data, item, key=self._key)
        return None

    def get(
        self,
        key: int | float,
        shift: int = 0,
    ) -> Optional[T]:
        """Get item that has the smallest key larger than key. Use shift to offset"""
        try:
            return self._data[bisect(self._data, key, key=self._key) + shift]
        except IndexError as err:
            error(f"key={key} is outside of the key range: {err}")
        except Exception as err:
            debug(f"Unknown error getting the value for key={key}: {err}")
        return None

    def pop(
        self,
        item: T | None = None,
        key: Optional[int | float] = None,
        shift: int = 0,
    ) -> Optional[T]:
        try:
            if item is not None:
                key = self._key(item)
            if key is not None:
                return self._data.pop(
                    bisect_left(self._data, key, key=self._key) + shift
                )
        except Exception as err:
            error(f"{err}")
        return None

    def list(self) -> list[T]:
        return self._data
