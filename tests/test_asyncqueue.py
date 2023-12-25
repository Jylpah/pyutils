import sys
import pytest  # type: ignore
from pathlib import Path
from queue import Queue

# from asyncio.queues import QueueEmpty, QueueFull
from asyncio import (
    Task,
    create_task,
    sleep,
    timeout,
    TimeoutError,
    QueueEmpty,
    QueueFull,
)

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import AsyncQueue  # noqa: E402

QSIZE: int = 10
N: int = 100  # N >> QSIZE
# N : int = int(1e10)


@pytest.fixture
def test_asyncqueue_int() -> AsyncQueue[int]:
    Q: Queue[int] = Queue[int](maxsize=QSIZE)  # queue.Queue / non-async
    return AsyncQueue(queue=Q)


async def _producer_int(Q: AsyncQueue[int], n: int):
    for i in range(n):
        await Q.put(i)


async def _consumer_int(Q: AsyncQueue[int], n: int = -1):
    while n != 0:
        _ = await Q.get()
        Q.task_done()
        n -= 1


# Test: put(), get(), join(), qsize()
@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_1_put_get_async(test_asyncqueue_int: AsyncQueue[int]):
    Q = test_asyncqueue_int
    consumer: Task = create_task(_consumer_int(Q))
    try:
        async with timeout(3):
            await _producer_int(Q, N)
    except TimeoutError:
        assert False, "AsyncQueue got stuck"
    await Q.join()
    assert Q.qsize() == 0, "queue not empty"
    assert Q.empty(), "queue not empty"
    assert Q.items == N, "Queue items counted wrong"
    consumer.cancel()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_2_put_get_nowait(test_asyncqueue_int: AsyncQueue[int]):
    Q = test_asyncqueue_int
    producer: Task = create_task(_producer_int(Q, N))
    await sleep(1)
    # In theory this could fail without a real error
    # if QSIZE is huge and/or system is slow
    assert Q.qsize() == Q.maxsize, "Queue was supposed to be at maxsize"
    assert Q.full(), "Queue should be full"
    assert Q.items == Q.maxsize, "Queue items counted wrong"
    assert not Q.empty(), "Queue should not be empty"
    assert Q.done == 0, "No queue items have been done"

    try:
        Q.put_nowait(1)
        assert False, "Queue was supposed to be full, but was not"
    except QueueFull:
        pass  # OK, Queue was supposed to be full

    try:
        while True:
            _ = Q.get_nowait()
            Q.task_done()
            await sleep(0.01)
    except QueueEmpty:
        assert Q.qsize() == 0, "Queue size should be zero"
        assert Q.done == N, f"Items done: {Q.done}"

    try:
        async with timeout(5):
            await Q.join()
    except TimeoutError:
        assert False, "Queue.join() took longer than it should"
    assert producer.done(), "producer has not finished"
    assert Q.qsize() == 0, "queue not empty"
    assert Q.empty(), "queue not empty"


# @pytest.mark.timeout(10)
# @pytest.mark.asyncio
# async def test_3_from_Queue() -> None:
#     queue: Queue[int] = Queue()

#     Q: AsyncQueue[int] = AsyncQueue.from_queue(queue)
#     assert Q.maxsize == 0, "maxsize should be 0 since queue.Queue does not support maxsize property"
#     try:
#         Q.task_done()
#         assert False, "This should raise ValueError"
#     except ValueError:
#         pass  # OK

#     await Q.put(1)
#     assert Q.done == 0, "done should be 0"
#     assert Q.items == 1, "Queue items counted wrong"

#     _ = await Q.get()
#     assert Q.done == 0, "done should be 0"
#     try:
#         Q.task_done()
#         assert True, "This should not raise ValueError"
#     except ValueError:
#         assert False, "This should not raise ValueError"
#     assert Q.done == 1, "done should be 1"
