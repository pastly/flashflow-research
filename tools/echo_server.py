#!/usr/bin/env python3
import asyncio
# import cProfile
from ph.lib.tokenbucket import TokenBucket

TB_CAPACITY = 5000 * 1024 * 1024  # MiB
TB_RATE = 10000 * 1024 * 1024  # MiB/s
tb = TokenBucket(TB_CAPACITY, TB_RATE)
TB_ENABLED = False

READ_HIGH_WATER = 1 * 1024 * 1024
READ_LOW_WATER = 1 * 1024 * 1024
MAX_WRITE_PER_CALL = 4096 * 100


class EchoConnection(asyncio.streams.StreamReaderProtocol):
    def __init__(self):
        self._buf = b''
        self._echoer = None
        self._reader = asyncio.StreamReader()
        super().__init__(self._reader)

    def connection_made(self, trans):
        # self._pr = cProfile.Profile()
        # self._pr.enable()
        loop = asyncio.get_event_loop()
        self._trans = trans
        self._writer = asyncio.StreamWriter(
            self._trans, self, self._reader, loop)
        self._peer = self._trans.get_extra_info('peername')
        # vars for statistics about how the buffer changes over time
        self._time_spent_empty = 0
        self._time_spent_full = 0
        self._lifetime = 0
        self._last_event = loop.time()
        print('Connection from', self._peer)

    def _update_buffer_stats(self):
        loop = asyncio.get_event_loop()
        now = loop.time()
        elapsed = now - self._last_event
        self._lifetime += elapsed
        if not len(self._buf):
            self._time_spent_empty += elapsed
        elif len(self._buf) >= READ_HIGH_WATER:
            self._time_spent_full += elapsed
        self._last_event = now

    def connection_lost(self, exc):
        self._update_buffer_stats()
        print('Lost connection from %s (%s)' % (self._peer, exc))
        print(
            'Spent %f/%f (%f%%) of the time empty, %f/%f (%f%%) of the time '
            'full' % (
            self._time_spent_empty, self._lifetime, self._time_spent_empty*100/self._lifetime,
            self._time_spent_full, self._lifetime, self._time_spent_full*100/self._lifetime))
        if self._echoer:
            self._echoer.cancel()
        # self._pr.disable()
        # self._pr.dump_stats('profile.dat')
        # self._pr.print_stats()

    def data_received(self, data):
        # print('Got %s' % data)
        self._update_buffer_stats()
        self._buf += data
        if len(self._buf) >= READ_HIGH_WATER:
            self._trans.pause_reading()
        if not self._echoer or self._echoer.done():
            self._echoer = asyncio.ensure_future(self._handle_echoing())
        self._update_buffer_stats()

    async def _handle_echoing(self):
        self._update_buffer_stats()
        tb.top_off()
        writer = self._writer
        to_send = min(tb.tokens, len(self._buf), MAX_WRITE_PER_CALL)
        # print('Echoing %s/%s bytes' % (to_send, len(self._buf)))
        try:
            writer.write(self._buf[:to_send])
            await writer.drain()
            self._buf = self._buf[to_send:]
        except Exception as e:
            print('Exception (%s): Quitting' % e)
            return
        to_sleep = 0 if not TB_ENABLED else tb.consume(to_send)
        await asyncio.sleep(to_sleep)
        if len(self._buf) < READ_LOW_WATER:
            try:
                self._trans.resume_reading()
            except RuntimeError:
                pass
        if len(self._buf):
            self._echoer = asyncio.ensure_future(self._handle_echoing())
        else:
            self._echoer = None
        self._update_buffer_stats()


async def main():
    loop = asyncio.get_event_loop()
    await loop.create_server(EchoConnection, host, port)

if __name__ == '__main__':
    host = '127.0.0.1'
    port = 23432
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    print('Listening on %s:%d' % (host, port))
    loop.run_forever()
