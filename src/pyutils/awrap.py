"""awrap() is a async wrapper for Iterables

It converts an Iterable[T] to AsyncIterable[T]
"""

from typing import AsyncIterable, AsyncIterator, Iterable, Iterator, TypeVar

T = TypeVar("T")


class awrap(AsyncIterable[T]):
    def __init__(self, iterable: Iterable[T]):
        self.iterable: Iterable[T] = iterable
        self.iter: Iterator[T]

    def __aiter__(self) -> AsyncIterator[T]:
        self.iter = iter(self.iterable)
        return self

    async def __anext__(self) -> T:
        try:
            return self.iter.__next__()
        except StopIteration:
            raise StopAsyncIteration
