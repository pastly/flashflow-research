from enum import Enum
import logging
import pickle
import struct
import zlib

MAX_PAYLOAD_SIZE = 400
# First 4 for chunk_type field
# Second 4 for chunk_len field
# Last 4 for CRC field
CHUNK_SIZE = MAX_PAYLOAD_SIZE + 4 + 4 + 4

log = logging.getLogger(__name__)

'''
A Chunk has the following format:

    (4 byte uint): len of payload data
    (4 bytes)    : type of chunk
    (X bytes)    : payload data
    (Y bytes)    : padding
    (4 bytes)    : CRC

Where X and Y must add up to MAX_PAYLOAD_SIZE, thus making every Chunk have a
length of MAX_PAYLOAD_SIZE + 4 + 4 + 4.

The CRC is calculated over the type field, the payload, and the padding

Chunk subclasses store their fields in the payload field section of the above
diagram.
'''


class _StrEnum(str, Enum):
    pass


class ChunkType(_StrEnum):
    '''
    4-char strings appearing near the front of chunks to identify their type.
    '''
    Data = 'data'


def chunkify(obj):
    '''
    Takes an object and turns it into a list of DataChunks that can be sent to
    someone, such as over the network.
    '''
    all_data = pickle.dumps(obj, protocol=4)
    all_data_to_chunk = []
    idx = 0
    # Break a long string of bytes into a list of strings of bytes, each at
    # most DataChunk.MAX_SIZE bytes long
    while idx < len(all_data):
        data = all_data[idx:idx+DataChunk.MAX_SIZE]
        idx += DataChunk.MAX_SIZE
        assert len(data) <= DataChunk.MAX_SIZE
        all_data_to_chunk.append(data)
    # For eaxh string of bytes, encode it into a chunk. We need to know the
    # number of remaining chunks for the DataChunk object, so this for loop is
    # a little extra complex in order to determine that.
    chunks = []
    for idx in range(len(all_data_to_chunk)):
        data = all_data_to_chunk[idx]
        remaining = len(all_data_to_chunk) - idx - 1
        assert len(data) <= DataChunk.MAX_SIZE
        assert remaining < len(all_data_to_chunk) and remaining >= 0
        chunks.append(DataChunk(remaining, data))
    return chunks


def dechunkify(chunks):
    '''
    Given a list of DataChunks, return a list of objects decoded from those
    chunks and any remaining unused chunks in the input list.
    '''
    out_objs = []
    out_chunks = []
    if not len(chunks):
        return out_objs, out_chunks
    for chunk in chunks:
        assert isinstance(chunk, DataChunk)
    idx = 0
    while idx < len(chunks):
        # Look at the next chunk
        working_chunk = chunks[idx]
        # Determine how many chunks after it need to exist
        num_look_ahead = working_chunk.remaining
        # If there aren't enough chunks, we've done all we can
        if num_look_ahead + idx >= len(chunks):
            break
        # Otherwise there are enough chunks. Make sure they each have the
        # correct **remaining** field, (perhaps not strictly needed, but most
        # likely a sign of bugs if this fails)
        for i in range(num_look_ahead+1):
            assert chunks[idx+i].remaining == num_look_ahead - i
        # Things seem okay. So take the data from the chunks
        data = b''.join([c.data for c in chunks[idx:idx+num_look_ahead+1]])
        # Turn the data into an object and add it to the output
        out_objs.append(pickle.loads(data))
        # Advance the index past the last chunk we just consumed
        idx += num_look_ahead + 1
    # We've consumed as many chunks as we can, but there may be more left. If
    # so, add them to **out_chunks**
    if idx < len(chunks):
        out_chunks = chunks[idx:]
    return out_objs, out_chunks


class Chunk():
    def __init__(self, chunk_type, data):
        assert len(data) <= MAX_PAYLOAD_SIZE
        padding = b'\x00' * (MAX_PAYLOAD_SIZE - len(data))
        chunk_type = bytes(chunk_type, 'utf-8')
        self._data = struct.pack('>I', len(data)) + chunk_type + data +\
            padding +\
            struct.pack('>I', zlib.crc32(chunk_type + data + padding))
        assert self.is_valid

    @classmethod
    def from_byte_stream(cls, stream):
        ''' If you have some bytes that are supposed to represent a Chunk
        (with its headers and everything), use this function to create a Chunk
        instance. '''
        chunk_len, = struct.unpack('>I', stream.read(4))
        chunk_type, = struct.unpack('>4s', stream.read(4))
        chunk_type_str = str(chunk_type, 'utf-8')
        chunk_type = ChunkType(chunk_type_str)
        chunk_data = stream.read(chunk_len)
        stream.read(MAX_PAYLOAD_SIZE - chunk_len)
        chunk_crc, = struct.unpack('>I', stream.read(4))
        chunk = Chunk(chunk_type_str, chunk_data)
        if chunk_type is None:
            pass
        elif chunk_type == ChunkType.Data:
            chunk = DataChunk.from_chunk(chunk)
        else:
            assert None, 'Can\'t parse %s from byte stream' % chunk_type
        # it should be valid ... because we just calculated the crc ourselves
        assert chunk.is_valid
        # but what may not be true is that the calculated crc matches the
        # given crc
        if chunk.crc != chunk_crc:
            log.warning('Created chunk of type %s and its CRC doesn\'t match '
                        'the given one.', chunk.type)
        return chunk

    @classmethod
    def from_chunk(cls, chunk):
        assert None, 'Not implemented for class %s' % cls.__name__

    @property
    def length(self):
        ''' 4-byte uint for number of bytes in data field '''
        l, = struct.unpack_from('>I', self._data, 0)
        return l

    @property
    def type(self):
        ''' 4-byte string naming the chunk type '''
        t, = struct.unpack_from('>4s', self._data, 4)
        return str(t, 'utf-8')

    @property
    def chunk_payload(self):
        ''' payload data in this chunk '''
        return self._data[8:8+self.length]

    @property
    def chunk_padding(self):
        ''' padding data in this chunk '''
        return self._data[8+self.length:-4]

    @property
    def crc(self):
        ''' 4-byte uint crc calculated on type, data, and padding
        (not length) '''
        # r = self._data[8+self.length:]
        r = self._data[-4:]
        assert len(r) == 4
        r, = struct.unpack('>I', r)
        return r

    @property
    def is_valid(self):
        ''' calculates the crc and checks that it matches the crc that we were
        given '''
        crc1 = self.crc
        crc2 = zlib.crc32(bytes(self.type, 'utf-8') + self.chunk_payload +
                          self.chunk_padding)
        return crc1 == crc2

    @property
    def raw_data(self):
        ''' the length, type, chunk_payload, padding, and crc all smooshed
        together like it would appear as a series of bytes'''
        if not self.is_valid:
            log('Returning raw_bytes for Chunk that is not valid')
        return self._data


class DataChunk(Chunk):
    MAX_SIZE = MAX_PAYLOAD_SIZE - 4

    def __init__(self, remaining, data):
        assert isinstance(remaining, int)
        assert remaining >= 0
        assert isinstance(data, bytes)
        d = struct.pack('>I%ss' % len(data), remaining, data)
        super().__init__(ChunkType.Data, d)

    @property
    def remaining(self):
        val, = struct.unpack_from('>I', self.chunk_payload, 0)
        return val

    @property
    def data(self):
        return self.chunk_payload[4:]

    @classmethod
    def from_chunk(cls, chunk):
        assert isinstance(chunk, Chunk)
        # log.debug('Chunk payload len %d' % len(chunk.chunk_payload))
        remaining, = struct.unpack_from('>I', chunk.chunk_payload, 0)
        data = chunk.chunk_payload[4:]
        return DataChunk(remaining, data)
