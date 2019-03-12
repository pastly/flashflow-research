import asyncio
import logging

log = logging.getLogger(__name__)


class TokenBucket:
    def __init__(self, capacity, refill_rate, top_off_per_sec=10):
        loop = asyncio.get_event_loop()
        self._loop = loop
        self._cap = capacity
        self._refill_rate = refill_rate
        self._tokens = 0
        self._last_top_off = loop.time()
        self._top_off_per_sec = top_off_per_sec

    def top_off(self):
        loop = asyncio.get_event_loop()
        dur = loop.time() - self._last_top_off
        earned = self._refill_rate * dur
        # print('We earned %f tokens in the last %f secs' % (earned, dur))
        self._tokens += earned
        if self.tokens > self.capacity:
            self._tokens = self.capacity
        self._last_top_off = loop.time()
        # print('We now have %s tokens' % self.tokens)

    def consume(self, num):
        '''
        Spend some tokens. Returns how many seconds we must wait before
        spending any more. If there are tokens remaining, this will be 0 time.
        '''
        assert num <= self.tokens
        self._tokens -= num
        # print('Consuemd %s tokens. %s remain. Now need to sleep %f secs' %
        #       (num, self.tokens,
        #        0 if self.tokens > 0 else self._next_top_off()))
        if self.tokens > 0:
            return 0
        return self._next_top_off()

    def _next_top_off(self):
        loop = asyncio.get_event_loop()
        interval = 1.0 / self._top_off_per_sec
        time_since_last = loop.time() - self._last_top_off
        if time_since_last >= interval:
            return 0
        return interval - time_since_last

    @property
    def capacity(self):
        return self._cap

    @property
    def refill_rate(self):
        return self._refill_rate

    @property
    def tokens(self):
        return int(self._tokens)
