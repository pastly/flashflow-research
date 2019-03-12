#!/usr/bin/env python3
import stem.client

data = b'kira' * 42
_CELL_SIZE = 514
_CELL_HEADER_SIZE = 5
_RELAY_CELL_HEADER_SIZE = 11
PAYLOAD_BYTES_PER_CELL = _CELL_SIZE - _CELL_HEADER_SIZE - \
    _RELAY_CELL_HEADER_SIZE


def main(host, or_port):
    with stem.client.Relay.connect(host, or_port) as r:
        assert(r.is_alive())
        with r.create_circuit() as circ:
            for i in range(0, len(data), PAYLOAD_BYTES_PER_CELL):
                d = data[i:i+PAYLOAD_BYTES_PER_CELL]
                resp = circ.send('RELAY_PING', d, stream_id=1)
                for item in resp:
                    print(type(item).__name__, item.command, item.data)


if __name__ == '__main__':
    host = '127.0.0.1'
    or_port = 2002
    main(host, or_port)
