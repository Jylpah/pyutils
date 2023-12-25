![CI](https://github.com/Jylpah/pyutils/actions/workflows/python-package.yml/badge.svg) [![codecov](https://codecov.io/gh/Jylpah/pyutils/graph/badge.svg?token=5EJ07RU78R)](https://codecov.io/gh/Jylpah/pyutils)

# pyutils

Misc Python utils

# Install

```
pip install git+https://github.com/Jylpah/pyutils.git
```

# Upgrade

```
pip install --upgrade git+https://github.com/Jylpah/pyutils.git
```

# MODULES 

* [AsyncQueue(asyncio.Queue, Generic[T])](src/pyutils/asyncqueue.py): Implement `async.Queue()` interface for non-async queues using `asyncio.sleep()` and `get_nowait()` and `put_nowait()` methods. Handy when using async code with `multiprocessing`
* [AsyncTyper(Typer)](src/pyutils/asynctyper.py): An wrapper for `Typer` to run `asyncio` commands.
* [BucketMapper(Generic[T])](src/pyutils/bucketmapper.py): Class to map objects into fixed buckets according to an attribute (`float|int`). Uses `bisect` package. 
* [CounterQueue(asyncio.Queue)](src/pyutils/counterqueue.py): Async Queue that keeps count on `task_done()` completed
* [EventCounter()](src/pyutils/eventcounter.py): Count / log statistics and merge different `EventCounter()` instances to provide aggregated stats of the events counted
* [FileQueue(asyncio.Queue)](src/pyutils/filequeue.py): Class to build file queue to process from command line arguments or STDIN (`-`)
* [IterableQueue(Queue[T], AsyncIterable[T], Countable):](src/pyutils/iterablequeue.py): Async queue that implements `AsyncIterable()`. The queue supports join(). Bit complex, but I could not figure how to simplify it while implenting both `join()` and `AsyncIterable()`
* [MultilevelFormatter(logging.Formatter)](src/pyutils/multilevelformatter.py): Log using different formats per logging level
* [ThrottledClientSession(aiohttp.ClientSession)](src/pyutils/throttledclientsession.py): Rate-throttled client session class inherited from aiohttp.ClientSession
* [utils](src/pyutils/utils.py) module for ... utils of [pyutils](.)

