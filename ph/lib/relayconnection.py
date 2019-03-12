import asyncio
import logging
import stem.client
from stem.client.datatype import ZERO, Address, KDF, LinkProtocol
from stem.client.cell import Cell, VersionsCell, NetinfoCell, CreateFastCell,\
    RelayCell
import hashlib
import socket
import ssl
import time
import struct

log = logging.getLogger(__name__)

_CELL_SIZE = 514
_CELL_HEADER_SIZE = 5
_RELAY_CELL_HEADER_SIZE = 11
MAX_PAYLOAD_BYTES = _CELL_SIZE - _CELL_HEADER_SIZE - \
    _RELAY_CELL_HEADER_SIZE


def _resolve(host):
    results = socket.getaddrinfo(host, 0)
    result = results[0]  # just take the first
    _, _, _, _, addr = result
    return addr[0]  # (ip, port), just return ip


class _Circuit:
    def __init__(self, circ_id, kdf, link_proto):
        if not stem.prereq.is_crypto_available():
            raise ImportError(
                'Circuit construction requires the cryptography module')
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms,\
            modes
        from cryptography.hazmat.backends import default_backend
        ctr = modes.CTR(ZERO * (algorithms.AES.block_size // 8))
        self.id = circ_id
        self.forward_digest = hashlib.sha1(kdf.forward_digest)
        self.backward_digest = hashlib.sha1(kdf.backward_digest)
        self.forward_key = Cipher(
            algorithms.AES(kdf.forward_key), ctr, default_backend())\
            .encryptor()
        self.backward_key = Cipher(
            algorithms.AES(kdf.backward_key), ctr, default_backend())\
            .decryptor()
        self.link_proto = link_proto

    def encrypt_cell(self, cell):
        data, self.forward_key, self.forward_digest = cell.encrypt(
            self.link_proto, self.forward_key, self.forward_digest)
        return data

    def decrypt_cell(self, data, assume_already_decrypted=False):
        if assume_already_decrypted:
            cells = stem.client.cell.Cell.unpack(data, self.link_proto)
            cells = [_ for _ in cells]
            assert len(cells) == 1
            return cells[0]
        try:
            cell, self.backward_key, self.backward_digest = \
                stem.client.cell.RelayCell.decrypt(
                    self.link_proto, data,
                    self.backward_key, self.backward_digest)
            return cell
        except stem.ProtocolError:
            cells = stem.client.cell.Cell.unpack(data, self.link_proto)
            cells = [c for c in cells]
            assert len(cells) == 1
            return cells[0]


class TargetRelayConnection(asyncio.Protocol):
    DEFAULT_LINK_PROTOCOLS = stem.client.DEFAULT_LINK_PROTOCOLS
    FIRST_CIRC_ID = 0x80000000

    @staticmethod
    def chunk(l, n):
        for i in range(0, len(l), n):
            yield l[i:i+n]

    @staticmethod
    def make_ssl_context():
        c = ssl.create_default_context()
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return c

    @staticmethod
    def _make_versions_cell():
        c = VersionsCell(TargetRelayConnection.DEFAULT_LINK_PROTOCOLS)
        return c

    @staticmethod
    def _make_netinfo_cell(remote_host):
        try:
            c = NetinfoCell(Address(remote_host), [])
        except ValueError as e:
            if 'an IPv4 or IPv6 address' in str(e):
                remote_host = _resolve(remote_host)
                c = NetinfoCell(Address(remote_host), [])
                return c
            raise e
        else:
            return c

    @staticmethod
    def _make_create_fast_cell(circ_id):
        c = CreateFastCell(circ_id)
        return c

    @staticmethod
    def _make_relay_ping_cell(circ_id, data, recognized):
        # The first time recognized should be 0 so that the relay knows the
        # cell is for it, processes it, and marks the circuit as an echo
        # circuit. After that, recognized should be non-zero 16 bit integer so
        # the cell doesn't look recognized. The relay will still give it back
        # to us since it is an echo circuit.
        command = 'RELAY_PING'
        stream_id = 0
        c = RelayCell(
            circ_id, command, data, stream_id=stream_id, recognized=recognized)
        return c

    @staticmethod
    def _make_relay_speedtest_startstop_cell(
            circ_id, is_start, report_interval=None):
        if is_start:
            # should not be None, and should be in seconds (so convert to ms)
            assert report_interval is not None
            report_interval = int(report_interval * 1000)
        else:
            report_interval = 0
        command = 'RELAY_SPEEDTEST_STARTSTOP'
        stream_id = 0
        # is_start = 0 if is_start else 1  # convert from bool to int
        data = struct.pack('!LL', is_start, report_interval)
        c = RelayCell(circ_id, command, data, stream_id=stream_id)
        return c

    def __init__(self, event_handlers, relay_hostname):
        self._done_negotiating_versions = asyncio.Event()
        self._done_making_circuit = asyncio.Event()
        self._relay_hostname = relay_hostname
        self.saved_create_fast_cell = None
        self.assume_already_decrypted = False
        self._trans = None
        self._circ = None
        self._inbuf = b''
        self._sent_first_echo_cell = False
        self._event_handlers = event_handlers
        self.handshake_done = asyncio.Event()

    def abort(self):
        self._trans.abort()

    async def drain(self):
        return self._trans.drain()

    def write_echo_bytes(self, data):
        assert self.handshake_done.is_set()
        encrypt_time = 0
        send_time = 0
        for d in TargetRelayConnection.chunk(data, MAX_PAYLOAD_BYTES):
            recognized = 1 if self._sent_first_echo_cell else 0
            self._sent_first_echo_cell = True
            cell = TargetRelayConnection._make_relay_ping_cell(
                self._circ.id, d, recognized)
            start = time.time()
            d = self._circ.encrypt_cell(cell)
            encrypt_time += time.time() - start
            start = time.time()
            self._trans.write(d)
            send_time += time.time() - start
        return encrypt_time, send_time

    def _write_speedtest_startstop(self, is_start, report_interval=None):
        c = TargetRelayConnection._make_relay_speedtest_startstop_cell(
            self._circ.id, is_start, report_interval)
        d = self._circ.encrypt_cell(c)
        self._trans.write(d)

    def write_speedtest_start(self, report_interval):
        return self._write_speedtest_startstop(True, report_interval)

    def write_speedtest_stop(self):
        return self._write_speedtest_startstop(False)

    def data_received(self, data):
        self._inbuf += data
        # log.debug('Got %d bytes', len(data))
        if not self._done_negotiating_versions.is_set():
            v_cell, self._inbuf = Cell.pop(self._inbuf, 2)
            common_protos = set(
                TargetRelayConnection.DEFAULT_LINK_PROTOCOLS)\
                .intersection(v_cell.versions)
            if not common_protos:
                assert None, 'Cannot continue: no common link proto versions'
            self.link_proto = LinkProtocol(max(common_protos))
            for cell in Cell.unpack(self._inbuf, self.link_proto.version):
                log.debug('Got (ignoring1): %s', cell)
            cell = TargetRelayConnection._make_netinfo_cell(
                self._relay_hostname)
            self._trans.write(cell.pack(self.link_proto.version))
            self._done_negotiating_versions.set()
            log.debug('Done negotiating versions')
            cell = TargetRelayConnection._make_create_fast_cell(
                TargetRelayConnection.FIRST_CIRC_ID)
            self.saved_create_fast_cell = cell
            self._trans.write(cell.pack(self.link_proto.version))
            self._inbuf = b''  # ignore remaining cells
            return
        assert self._done_negotiating_versions.is_set()
        if not self._done_making_circuit.is_set():
            cell, self._inbuf = Cell.pop(self._inbuf, self.link_proto.version)
            assert not self._inbuf
            assert isinstance(cell, stem.client.cell.CreatedFastCell),\
                'Got a %s cell when waiting for CreatedFastCell' % cell
            kdf = KDF.from_value(
                self.saved_create_fast_cell.key_material + cell.key_material)
            self.saved_create_fast_cell = None
            assert cell.derivative_key == kdf.key_hash,\
                'Remote failed to prove that it knows our shared key'
            self._circ = _Circuit(cell.circ_id, kdf, self.link_proto)
            log.debug('Done making circuit')
            self._done_making_circuit.set()
            log.debug('Done handhskaing')
            self.handshake_done.set()
            self.assume_already_decrypted = True
            self._event_handlers.on_connection_made(self)
            return
        assert self._done_making_circuit.is_set()
        assert self.handshake_done.is_set()
        data = b''
        decrypting_time = 0
        while len(self._inbuf) >= self.link_proto.fixed_cell_length:
            cell_data, self._inbuf =\
                self._inbuf[:self.link_proto.fixed_cell_length],\
                self._inbuf[self.link_proto.fixed_cell_length:]
            start = time.time()
            cell = self._circ.decrypt_cell(
                cell_data,
                assume_already_decrypted=self.assume_already_decrypted)
            decrypting_time += time.time() - start
            if cell.NAME == 'DESTROY':
                log.warning('Got destory cell. Aborting connection')
                self.abort()
                return
            # log.debug('Got %s', type(cell).__name__)
            assert isinstance(cell, stem.client.cell.RelayCell)
            assert cell.command in ['RELAY_PING', 'RELAY_SPEEDTEST_STARTSTOP']
            data += cell.data
        # log.debug('Returning %d bytes and Leaving %d on inbuf',
        #           len(data), len(self._inbuf))
        self._event_handlers.on_data_received(self, data, decrypting_time)

    def connection_made(self, trans):
        self._trans = trans
        self._peer = self._trans.get_extra_info('peername')
        log.debug('Connection to/from %s', self._peer)
        cell = TargetRelayConnection._make_versions_cell()
        self._trans.write(cell.pack(2))
        # Will do on_connection_made event when we are done handshaking

    @property
    def peer(self):
        return self._peer

    def connection_lost(self, exc):
        log.debug('Lost connection with %s (%s)', self._peer, exc)
        self._event_handlers.on_connection_lost(self, exc)

    def eof_received(self):
        self._event_handlers.on_eof_received(self)
