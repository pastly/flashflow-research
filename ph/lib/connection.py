import ph.util.crypto as crypto
from ph.lib.chunk import CHUNK_SIZE, Chunk, DataChunk, chunkify, dechunkify
from ph.lib.chunkpayloads import Aborted
import asyncio
import io
import logging

log = logging.getLogger(__name__)

BOX_OVERHEAD = 40
BOX_SIZE = CHUNK_SIZE + BOX_OVERHEAD


class ConnectionEventHandlers:
    def on_data_received(self, conn, obj):
        pass

    def on_eof_received(self, conn):
        pass

    def on_connection_made(self, conn):
        pass

    def on_connection_lost(self, conn, exc):
        pass

    def send_aborted_measurement(self, msg=None):
        self._conn.write_object(Aborted(msg=msg))


class Connection(asyncio.Protocol):
    def __init__(self, boxes, event_handlers):
        self._box = None
        self._boxes = boxes
        if len(self._boxes) == 1:
            self._box = list(self._boxes)[0]
        # Encrypted data from the network
        self._netbuf = b''
        # Decrypted data from the netbuf that should be bytes representing
        # chunks
        self._chunkbuf = b''
        # Chunks from the chunkbuf waiting to have objects extracted from them
        self._objbuf = []
        # Objects finally ready to be handled
        self._buf = []
        self._current_on_read = self._on_read_noop
        assert isinstance(event_handlers, ConnectionEventHandlers)
        self._event_handlers = event_handlers

    def connection_made(self, trans):
        self._trans = trans
        self._peer = self._trans.get_extra_info('peername')
        log.debug('Connection to/from %s', self._peer)
        self._event_handlers.on_connection_made(self)

    @property
    def peer(self):
        return self._peer

    def connection_lost(self, exc):
        log.debug('Lost connection with %s (%s)', self._peer, exc)
        self._event_handlers.on_connection_lost(self, exc)

    def data_received(self, data):
        # Take in the data off the wire
        self._netbuf += data
        # Decrypt the data from the network into a buffer of bytes
        self._parse_netbuf()
        # Decode the buffer of bytes into chunks
        self._parse_chunkbuf()
        # Extract objects from the buffer of chunks
        self._parse_objbuf()
        # Handle the chunk(s) we have received
        # log.debug('len of conn buf %s', len(self._buf))
        for obj in self._buf:
            self._event_handlers.on_data_received(self, obj)
        self._buf = []

    def eof_received(self):
        self._event_handlers.on_eof_received(self)

    def write_object(self, obj):
        assert self._box is not None
        for chunk in chunkify(obj):
            self._trans.write(self._box.encrypt(chunk.raw_data))

    def _on_read_noop(self):
        log.warning(
            'We ended up in NOOP reading function. Most likely, this should '
            'never happen. There is %d bytes in the netbuf, %d bytes in the '
            'chunkbuf, %d chunks in the objbuf, and %d objects in the buf.',
            len(self._netbuf), len(self._chunkbuf), len(self._objbuf),
            len(self._buf))

    def _parse_netbuf(self):
        '''
        Takes bytes we've just read off the wire and decrypts them. We use
        PyNaCl's Boxes for encryption, so we must be able to read a set amount
        of bytes. If we don't have that many yet, leave them on the _netbuf
        '''
        if len(self._netbuf) < BOX_SIZE:
            return
        while len(self._netbuf) >= BOX_SIZE:
            cypher = self._netbuf[:BOX_SIZE]
            self._netbuf = self._netbuf[BOX_SIZE:]
            if not self._box:
                self._box, _ = crypto.find_correct_box(self._boxes, cypher)
                if self._box is None:
                    log.warning(
                        'Could not figure out who the measurer is. Closing '
                        'connection to %s', self._peer)
                    self._trans.close()
                    return
            assert self._box is not None
            plain = crypto.try_decrypt(self._box, cypher)
            if plain is None:
                log.warning(
                    'Got %d byte from %s that we didn\'t know how to decrypt. '
                    'Closing connection.', len(cypher), self._peer)
                self._trans.close()
                return
            # log.debug('Adding %d bytes to chunkbuf', len(plain))
            self._chunkbuf += plain

    def _parse_chunkbuf(self):
        '''
        Take decrypted bytes that should represent chunks, and turn them into
        chunks. Chunks are a fixed size, so if we don't have enough bytes yet,
        leave them on the _chunkbuf.
        '''
        if len(self._chunkbuf) < CHUNK_SIZE:
            return
        while len(self._chunkbuf) >= CHUNK_SIZE:
            data = self._chunkbuf[:CHUNK_SIZE]
            self._chunkbuf = self._chunkbuf[CHUNK_SIZE:]
            chunk = Chunk.from_byte_stream(io.BytesIO(data))
            if chunk is None:
                log.warning(
                    'Unable to parse chunk from %s. Closing connection.',
                    self._peer)
                self._trans.close()
                return
            assert isinstance(chunk, DataChunk)
            self._objbuf.append(chunk)
            log.debug('Got %s chunk from %s', chunk.type, self._peer)

    def _parse_objbuf(self):
        '''
        Takes DataChunks off the objbuf and parses them into objects that we
        are finally ready to handle. Let ph.lib.chunk.dechunkify() do the heavy
        lifting.
        '''
        new_objs, self._objbuf = dechunkify(self._objbuf)
        if new_objs:
            # log.debug('Got %s from %s', new_objs, self._peer)
            self._buf.extend(new_objs)
