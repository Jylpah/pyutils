# pyutils

Python utils library

# Install

```
pip install git+https://github.com/Jylpah/pyutils.git
```

# Upgrade

```
pip install --upgrade git+https://github.com/Jylpah/pyutils.git
```


# MODULES 

* [counterqueue](counterqueue.py): `CounterQueue(asyncio.Queue)`: Async Queue that keeps count on `task_done()` completed
* [eventcounter](eventcounter.py): `EventCounter()`: Count / log statistics and merge different `EventCounter()` instances to provide aggregated stats of ecents counted
* [filequeue](filequeue.py): `FileQueue(asyncio.Queue)`: Class to build file queue to process from command line arguments or STDIN (`-`)
* [iterablequeue](iterablequeue.py): `IterableQueue(asyncio.Queue)`: Async Queue that support async iteration and exits when the last item has been processed. 
* [throttledclientsession](throttledclientsession.py):  `ThrottledClientSession(aiohttp.ClientSession)`: Rate-throttled client session class inherited from aiohttp.ClientSession)
* [multilevelformatter](multilevelformatter.py): `MultiLevelFormatter(logging.Formatter)`: Different message formats per logging level
* [Utils](utils.py) module for ... utils of [pyutils](.)

