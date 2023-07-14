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

* [AliasMapper()](aliasmapper.py): [Pydantic](https://pydantic.dev/) helper class to map field names to field aliases.
* [AsyncQueue(asyncio.Queue, Generic[T])](asyncqueue.py): Implement `async.Queue()` interface for non-async queues using `asyncio.sleep()` and `get_nowait()` and `put_nowait()` methods. Handy when using async code with `multiprocessing`
* [BucketMapper(Generic[T])](bucketmapper.py): Class to map objects into fixed buckets according to an attribute (`float|int`). Uses `bisect` package. 
* [CounterQueue(asyncio.Queue)](counterqueue.py): Async Queue that keeps count on `task_done()` completed
* [EventCounter()](eventcounter.py): Count / log statistics and merge different `EventCounter()` instances to provide aggregated stats of the events counted
* [FileQueue(asyncio.Queue)](filequeue.py): Class to build file queue to process from command line arguments or STDIN (`-`)
* [IterableQueue(Queue[T], AsyncIterable[T], Countable):](iterablequeue.py): Async queue that implements `AsyncIterable()`. The queue supports join(). Bit complex, but I could not figure how to simplify it while implenting both `join()` and `AsyncIterable()`
* [MultilevelFormatter(logging.Formatter)](multilevelformatter.py): Log using different formats per logging level
* [ThrottledClientSession(aiohttp.ClientSession)](throttledclientsession.py): Rate-throttled client session class inherited from aiohttp.ClientSession
* [utils](utils.py) module for ... utils of [pyutils](.)

