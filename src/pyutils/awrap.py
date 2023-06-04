"""awrap() is a async wrapper for Iterables

It converts an Iterable[T] to AsyncGenerator[T]. 
AsyncGenerator[T] is also AsyncIterable[T] allowing it to be used in async for
"""

from typing import Iterable, TypeVar, AsyncGenerator

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


async def awrap(iterable: Iterable[T]) -> AsyncGenerator[T, None]:
    """Async wrapper for Iterable[T] so it can be used in async for"""
    for item in iter(iterable):
        yield item
