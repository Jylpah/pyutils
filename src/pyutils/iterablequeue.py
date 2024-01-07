from asyncio import Queue, QueueFull, QueueEmpty, Event, Lock
from typing import AsyncIterable, TypeVar, Optional
from .utils import Countable
import logging

# Setup logging
logger = logging.getLogger()
error = logger.error
message = logger.warning
verbose = logger.info
debug = logger.debug

T = TypeVar("T")


class QueueDone(Exception):
    pass


class IterableQueue(Queue[T], AsyncIterable[T], Countable):
    """Async.Queue subclass with automatic termination when the queue has been
    filled and emptied. Supports:
    - Queue() interface except _nowait() methods
    - AsyncIterable(): async for item in queue.get():
    - Automatic termination of the consumers when the queue has been emptied (QueueDone exception)
    - Producers must be registered with add_producer() and they must notify
      once they have finished adding items with finish()
    - Countable interface to count number of items task_done() through 'count' property
    - Countable property can be disabled with count_items=False. This is useful when you
    want to sum the count of multiple IterableQueues"""

    def __init__(self, count_items: bool = True, **kwargs):
        # _Q is required instead of inheriting from Queue()
        # using super() since Queue is Optional[T], not [T]
        self._Q: Queue[Optional[T]] = Queue(**kwargs)
        self._producers: int = 0
        self._count_items: bool = count_items
        self._count: int = 0
        self._wip: int = 0

        self._modify: Lock = Lock()
        self._put_lock: Lock = Lock()

        self._filled: Event = Event()
        self._empty: Event = Event()
        self._done: Event = Event()

        self._empty.set()

    @property
    def is_filled(self) -> bool:
        return self._filled.is_set()
    
    @property
    def is_done(self) -> bool:
        return self.is_filled and self.empty() and not self.has_wip

    @property
    def maxsize(self) -> int:
        return self._Q.maxsize

    @property
    def _maxsize(self) -> int:
        return self.maxsize

    def full(self) -> bool:
        return self._Q.full()



    def check_done(self) -> bool:
        if self.is_filled and self.empty() and not self.has_wip:
            self._done.set()
            return True
        return False

    def empty(self) -> bool:
        """Queue has not items except None as sentinel"""
        return self._empty.is_set() or self.qsize() == 0

    def qsize(self) -> int:
        if self.is_filled:
            return self._Q.qsize() - 1
        else:
            return self._Q.qsize()

    @property
    def wip(self) -> int:
        return self._wip

    @property
    def has_wip(self) -> bool:
        return self._wip > 0

    @property
    def count(self) -> int:
        if self._count_items:
            return self._count
        else:
            return 0

    async def add_producer(self, N: int = 1) -> int:
        """Add producer(s) to the queue"""
        assert N > 0, "N has to be positive"
        async with self._modify:
            if self.is_filled:
                raise QueueDone
            self._producers += N
        return self._producers

    async def finish(self, all: bool = False, empty: bool = False) -> bool:
        """Producer has finished adding items to the queue
        * all: finish() queue for all producers at once"""
        async with self._modify:
            if self._producers <= 0 or self.is_filled:
                # raise ValueError("finish() called more than the is producers")
                self._producers = 0
                return False
            self._producers -= 1

            if all or self._producers <= 0:
                self._filled.set()
                self._producers = 0

        if self._producers == 0:
            if empty:
                try:
                    while True:
                        _ = self.get_nowait()
                        self.task_done()
                except (QueueDone, QueueEmpty):
                    pass

            async with self._put_lock:
                if empty:
                    try:
                        _ = self.get_nowait()
                        self.task_done()
                    except (QueueDone, QueueEmpty):
                        pass
                self.check_done()
                await self._Q.put(None)
                return True
        return False

    async def put(self, item: T) -> None:
        async with self._put_lock:
            if self.is_filled:  # should this be inside put_lock?
                raise QueueDone
            if self._producers <= 0:
                raise ValueError("No registered producers")
            elif item is None:
                raise ValueError("Cannot add None to IterableQueue")
            await self._Q.put(item=item)
            self._empty.clear()
        return None

    def put_nowait(self, item: T) -> None:
        """Attempt to implement put_nowait()"""
        # raise NotImplementedError
        if self.is_filled:
            raise QueueDone
        if self._producers <= 0:
            raise ValueError("No registered producers")
        elif item is None:
            raise ValueError("Cannot add None to IterableQueue")
        self._Q.put_nowait(item=item)
        self._empty.clear()
        return None

    async def get(self) -> T:
        item = await self._Q.get()
        if item is None:
            self._empty.set()
            self._Q.task_done()
            self.check_done()
            async with self._put_lock:
                await self._Q.put(None)
                raise QueueDone
        else:
            if self._Q.qsize() == 0:
                self._empty.set()
            async with self._modify:
                self._wip += 1
            return item

    def get_nowait(self) -> T:
        """Attempt to implement get_nowait()"""
        # raise NotImplementedError
        item: T | None = self._Q.get_nowait()
        if item is None:
            self._empty.set()
            self._Q.task_done()
            self.check_done()
            try:
                self._Q.put_nowait(None)
            except QueueFull:
                pass
            raise QueueDone
        else:
            if self._Q.qsize() == 0:
                self._empty.set()
            self._wip += 1
            return item

    def task_done(self) -> None:
        self._Q.task_done()
        self._count += 1
        self._wip -= 1
        if self._wip < 0:
            raise ValueError("task_done() called more than tasks open")
        self.check_done()

    async def join(self) -> None:
        debug("Waiting queue to be filled")
        await self._filled.wait()
        debug("Queue filled, waiting when queue is done")
        await self._done.wait()
        debug("queue is done")
        return None

    def __aiter__(self):
        return self

    async def __anext__(self) -> T:
        async with self._modify:
            if self._wip > 0:  # do not mark task_done() at first call
                self.task_done()
        try:
            item = await self.get()
            return item
        except QueueDone:
            raise StopAsyncIteration
