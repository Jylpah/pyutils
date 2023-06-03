"""awrap() is a async wrapper for Iterables

It converts an Iterable[T] to AsyncIterable[T]
"""

from typing import Iterator, TypeVar, AsyncGenerator

T = TypeVar("T")


# class awrap(AsyncIterable[T]):
#     def __init__(self, iterable: Iterable[T]):
#         self.iterable: Iterable[T] = iterable
#         self.iter: Iterator[T]

#     def __aiter__(self) -> AsyncIterator[T]:
#         self.iter = iter(self.iterable)
#         return self

#     async def __anext__(self) -> T:
#         try:
#             return self.iter.__next__()
#         except StopIteration:
#             raise StopAsyncIteration


async def awrap(iterator: Iterator[T]) -> AsyncGenerator[T, None]:
    """Async wrapper for Iterable[T] so it can be used in async for"""
    for item in iterator:
        yield item
