## -----------------------------------------------------------
#### Class ThrottledClientSession(aiohttp.ClientSession)
#
#  Rate-limited async http client session
#
#  Inherits aiohttp.ClientSession 
## -----------------------------------------------------------

from typing import Optional
import aiohttp
import asyncio
import time
import logging

class ThrottledClientSession(aiohttp.ClientSession):
    """Rate-throttled client session class inherited from aiohttp.ClientSession)""" 

    def __init__(self, rate_limit: float = 0, *args,**kwargs) -> None: 
        super().__init__(*args,**kwargs)
        
        self.rate_limit: float
        self._fillerTask    : Optional[asyncio.Task]= None
        self._queue         : Optional[asyncio.Queue]               = None
        self._start_time = time.time()
        self._count = 0   
        self.set_rate_limit(rate_limit)


    def _get_sleep(self) -> float:        
        if self.rate_limit > 0:
            return 1/self.rate_limit
        return 0


    def get_rate(self) -> float:
        """Return rate of requests"""
        return self._count / (time.time() - self._start_time)


    def get_stats(self) -> dict[str, float]:
        """Get session statistics"""
        res = {'rate' : self.get_rate(), 'rate_limit': self.rate_limit, 'count' : self._count }
        return res
        

    def get_stats_str(self) -> str:
        """Print session statistics"""
        return f"rate limit: {str(self.rate_limit if self.rate_limit != None else '-')} \
                rate:   {0:.1f}.format(self.get_rate()) requests: {str(self._count)}"


    def reset_counters(self) -> dict[str, float]:
        """Reset rate counters and return current results"""
        res = self.get_stats()
        self._start_time = time.time()
        self._count = 0
        return res


    def set_rate_limit(self, rate_limit: float = 0):
        assert rate_limit is not None, "rate_limit must not be None" 
        assert isinstance(rate_limit, float) and rate_limit >= 0, "rate_limit has to be type of 'float' >= 0"
        self.rate_limit = rate_limit

        if rate_limit > 0:
            self._queue     = asyncio.Queue(int(rate_limit)+1) 
            if self._fillerTask is not None: 
                self._fillerTask.cancel()  
            self._fillerTask = asyncio.create_task(self._filler())
        return self.rate_limit
        

    async def close(self):
        """Close rate-limiter's "bucket filler" task"""
        # DEBUG 
        logging.debug(self.get_stats_str())
        if self._fillerTask is not None:
            self._fillerTask.cancel()
        try:
            await asyncio.wait_for(self._fillerTask, timeout=0.5)
        except asyncio.TimeoutError as err:
            logging.error(str(err))
        await super().close()

    
    async def _filler(self) -> None:
        """Filler task to fill the leaky bucket algo"""
        try:
            if self._queue is None:
                return None            
            logging.debug('SLEEP: ' + str(self._get_sleep()))
            updated_at = time.monotonic()
            fraction        : float = 0
            extra_increment : float = 0
            for i in range(0, self._queue.maxsize):
                await self._queue.put(i)
            while True:
                if not self._queue.full():
                    now = time.monotonic()
                    increment = self.rate_limit * (now - updated_at)
                    fraction += increment % 1
                    extra_increment = fraction // 1
                    items_2_add = int(min(self._queue.maxsize - self._queue.qsize(), int(increment) + extra_increment))
                    fraction = fraction % 1
                    for i in range(0,items_2_add):
                        self._queue.put_nowait(i)
                    updated_at = now
                await asyncio.sleep(self._get_sleep())
        except asyncio.CancelledError:
            logging.debug('Cancelled')
        except Exception as err:
            logging.error(str(err))
        return None


    async def _request(self, *args,**kwargs) -> aiohttp.client_reqrep.ClientResponse:
        """Throttled _request()"""
        if self._queue is not None:
            await self._queue.get()
            self._queue.task_done()
        self._count += 1
        return await super()._request(*args,**kwargs)
