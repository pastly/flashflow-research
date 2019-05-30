from ..lib.chunkpayloads import Identify
from ..lib.chunkpayloads import MeasureResult, BwMeasureResult
from ..lib.chunkpayloads import MeasureCommand, MeasureCommandBw
from ..lib.chunkpayloads import ConnectToTargetCommand
from ..lib.connection import Connection
from ..lib.connection import ConnectionEventHandlers
from ..lib.controllercommands import ControllerCommandStatus
from ..lib.controllercommands import ControllerCommandMeasure
from ..lib.statemachine import StateMachine
from ..lib.relayconnection import TargetRelayConnection
from ..util.stem import launch_tor, get_relay_ip_port
from nacl.public import PublicKey, PrivateKey, Box
from argparse import ArgumentDefaultsHelpFormatter
import asyncio
import base64
import enum
import logging
import struct
import time

log = logging.getLogger(__name__)

TESTING_BW_TEST_DURATION = 60

tor_ctrl = None


class State(enum.Enum):
    Start = 1
    Idle = 2
    MeasurersConnecting = 3
    PerformingMeasurement = 4
    PostMeasurement = 5


state = StateMachine({
        State.Start: {State.Idle},
        State.Idle: {State.MeasurersConnecting},
        State.MeasurersConnecting: {State.PerformingMeasurement, State.Idle},
        State.PerformingMeasurement: {State.PostMeasurement, State.Idle},
        State.PostMeasurement: {State.Idle},
    },
    initial=State.Start,
    allow_noop=False
)

IP_TO_MPC_ID_MAP = {
    '127.0.0.1': 'local',
    '23.91.124.124': 'nrl',
    '100.15.234.208': 'ddns',
    '134.209.148.91': 'india.do',
    '104.248.93.55': 'amst.do',
}


def ip_to_mpc_id(ip):
    if ip not in IP_TO_MPC_ID_MAP:
        return None
    return IP_TO_MPC_ID_MAP[ip]


def split_x_by_y(x, y):
    ''' Divide X as evenly as possible Y ways using only ints, and return those
    ints. Consider x=5 and y=3. 5 cannot be divided into 3 pieces evenly using
    ints. This function would yield a generator producing 1, 2, 2.

    x=8, y=5 yields 1, 2, 1, 2, 2.
    x=6, y=3 yields 2, 2, 2
    '''
    frac_accum = 0
    for iters_left in range(y-1, 0-1, -1):
        frac_accum += x % y
        if frac_accum >= y or not iters_left and frac_accum:
            yield x // y + 1
        else:
            yield x // y
        if frac_accum >= y:
            frac_accum -= y


class TargetConnectionEventHandlers(ConnectionEventHandlers):
    def __init__(self):
        self.last_report_time = time.time()
        pass

    def on_connection_made(self, conn):
        pass

    def on_data_received(self, conn, data, decrypting_time):
        if state != State.PerformingMeasurement:
            return
        num_bytes = struct.unpack_from('!L', data, 0)[0]
        num_mib = num_bytes / 1024 / 1024
        log.debug(
            'Target relay reports %0.2f MiB background traffic', num_mib)
        now = time.time()
        result = BwMeasureResult(
            self.last_report_time, now, num_bytes, False)
        self.last_report_time = now
        status.buffer_results(conn, [result])

    def on_connection_lost(self, conn, exc):
        log.debug('Lost connection with %s: %s', conn.peer, exc)

    def on_eof_received(self, conn):
        log.debug('Lost connection with %s: eof', conn.peer)


class MeasurerConnectionEventHandlers(ConnectionEventHandlers):
    @property
    def conn(self):
        return self._conn

    @property
    def mpc_id(self):
        return ip_to_mpc_id(self.peer[0])

    @property
    def peer(self):
        return self.conn.peer

    def on_connection_made(self, conn):
        self._recv_connect_to_target_response = asyncio.Event()
        self._connect_to_target_response = None
        self._conn = conn
        # status.add_conn(self)

    def on_connection_lost(self, conn, exc):
        status.del_conn(self)

    def on_data_received(self, conn, obj):
        if state == State.Idle and isinstance(obj, Identify):
            ident = obj
            log.info(
                'Got Identify with message "%s" from %s %s', ident.message,
                self.mpc_id, conn.peer)
            status.add_conn(self)
        elif state == State.MeasurersConnecting:
            assert isinstance(obj, ConnectToTargetCommand)
            self._connect_to_target_response = obj
            self._recv_connect_to_target_response.set()
            return
        elif state == State.PerformingMeasurement:
            for res in obj:
                assert isinstance(res, MeasureResult)
            status.buffer_results(self, obj)
        else:
            log.warn(
                'Didn\'t handle %s object. Current state is %s' %
                (type(obj).__name__, state.current))

    async def relay_connect_command(self, command):
        assert isinstance(command, ConnectToTargetCommand)
        self._conn.write_object(command)
        await self._recv_connect_to_target_response.wait()
        assert self._connect_to_target_response
        resp = self._connect_to_target_response
        self._recv_connect_to_target_response.clear()
        self._connect_to_target_response = None
        return resp

    async def relay_measure_command(self, command):
        assert isinstance(command, MeasureCommand)
        self._conn.write_object(command)


class ControllerConnectionEventHandlers(ConnectionEventHandlers):
    @property
    def conn(self):
        return self._conn

    @property
    def peer(self):
        return self.conn.peer

    def on_connection_made(self, conn):
        self._conn = conn
        status.add_conn(self)

    def on_connection_lost(self, conn, exc):
        status.del_conn(self)

    def on_data_received(self, conn, obj):
        if state == State.Idle and isinstance(obj, Identify):
            ident = obj
            log.info(
                'Got Identify with message "%s" from %s', ident.message,
                conn.peer)
        elif state == State.Idle and isinstance(obj, ControllerCommandStatus):
            conn.write_object(status.get_status('multi_line_text'))
        elif state == State.Idle and isinstance(obj, ControllerCommandMeasure):
            command = obj
            log.info('Got measure commands from %s', conn.peer)
            asyncio.ensure_future(
                _perform_a_measurement(self, command.measure_commands))
        else:
            log.warn(
                'Didn\'t handle %s object. Current state is %s' %
                (type(obj).__name__, state.current))

    def relay_measure_results(self, results):
        # We have to replace the MeasurerConnectionEventhandler keys with
        # something that can actually be pickled. Besides, they wouldn't be
        # useful in a different process.
        out_results = {}
        for measurer in results:
            for res in results[measurer]:
                assert isinstance(res, MeasureResult)
            out_results[hash(measurer)] = results[measurer]
        self._conn.write_object(out_results)


class Status:
    KNOWN_FORMATS = {'multi_line_text', 'dict'}

    def __init__(self):
        self._conns = {
            # These allow us to -- for example -- figure out what connections
            # we have to measurers from a controller connection, and pass off
            # to them a command.
            MeasurerConnectionEventHandlers: set(),
            ControllerConnectionEventHandlers: set(),
            # The subset of measurers we are using for a measurement
            'used_measurers': set(),
        }
        self._buffered_results = {
            # Keys: an instance of MeasurerConnectionEventHandlers or
            #       TargetRelayConnection
            # Values: a list of results
        }

    def add_conn(self, conn):
        '''
        Register a new connection
        '''
        if type(conn) not in self._conns:
            log.warn('Do not known how to add connection type %s', type(conn))
            return
        self._conns[type(conn)].add(conn)

    def del_conn(self, conn):
        '''
        Deregister a connection
        '''
        if type(conn) not in self._conns:
            return
        try:
            self._conns[type(conn)].remove(conn)
        except KeyError:
            pass

    def use_conn(self, conn):
        assert isinstance(conn, MeasurerConnectionEventHandlers)
        self._conns['used_measurers'].add(conn)
        log.debug('Registered a measurer conn as in use. Now have %d',
                  len(self._conns['used_measurers']))

    def clear_used_conns(self):
        log.debug('Clearing our set of %d used measurer conns',
                  len(self._conns['used_measurers']))
        self._conns['used_measurers'].clear()

    def buffer_results(self, conn, results):
        '''
        Add some results that came from measurer **conn** to our buffer
        '''
        assert isinstance(conn, TargetRelayConnection) or\
            isinstance(conn, MeasurerConnectionEventHandlers)
        for res in results:
            assert isinstance(res, MeasureResult)
        if conn not in self._buffered_results:
            self._buffered_results[conn] = []
        self._buffered_results[conn].extend(results)
        log.debug(
            'Buffering %d results from %s. Now have %d stored from them',
            len(results), conn.peer, len(self._buffered_results[conn]))

    @property
    def buffered_results(self):
        '''
        Get the buffered results dictionary without clearing it
        '''
        return self._buffered_results

    def dump_results(self):
        '''
        Get the buffered results dictioanry, and clear it
        '''
        ret = self._buffered_results
        self._buffered_results = {}
        log.debug(
            'Dumping buffered results from %d measurers and clearing buffer',
            len(ret))
        return ret

    def get_status(self, format_='multi_line_text'):
        if format_ not in Status.KNOWN_FORMATS:
            raise NotImplementedError(
                'Can\'t get status in format %s' % format_)
        func = '_get_status_%s' % format_
        assert hasattr(self, func)
        return getattr(self, func)()

    def _get_status_dict(self):
        return {
            'used_measurers': self._conns['used_measurers'],
            'measurers': self._conns[MeasurerConnectionEventHandlers],
            'controllers': self._conns[ControllerConnectionEventHandlers],
        }

    def _get_status_multi_line_text(self):
        status = self.get_status('dict')
        lines = []
        lines.append('We have the following connections from measurers:')
        for measurer in status['measurers']:
            lines.append(
                '    - %s:%d' % (measurer.conn.peer[0], measurer.conn.peer[1]))
        lines.append('We have the following connections from controllers:')
        for cont in status['controllers']:
            lines.append(
                '    - %s:%d' % (cont.conn.peer[0], cont.conn.peer[1]))
        return '\n'.join(lines)


status = Status()


async def _make_my_target_connection(target_fp):
    target = get_relay_ip_port(tor_ctrl, target_fp)
    if target is None:
        return None
    log.debug('Will connect to %s', target)
    loop = asyncio.get_event_loop()
    eh = TargetConnectionEventHandlers()
    c = TargetRelayConnection(eh, target[0])
    _, target_conn = await loop.create_connection(
        lambda: c, target[0], target[1],
        ssl=TargetRelayConnection.make_ssl_context())
    await target_conn.handshake_done.wait()
    log.debug('Finished making conn')
    return target_conn


def _send_out_aborted_measurement_message(conns, msg=None):
    for c in conns:
        assert isinstance(c, ConnectionEventHandlers)
        c.send_aborted_measurement(msg)


def _calc_mpc_num_conn_generators(used_mprocs, num_c_per_mpc):
    used_mpcs = {m.mpc_id for m in used_mprocs}
    log.debug('%d used mpcs: %s', len(used_mpcs), used_mpcs)
    d = {}
    for mpc_id in used_mpcs:
        num_mprocs_on_mpc = len([1 for m in used_mprocs if m.mpc_id == mpc_id])
        log.debug(
            'mpc %s has %d of the %d in-use mprocs', mpc_id, num_mprocs_on_mpc,
            len(used_mprocs))
        log.debug(
            '%s\'s split: %s', mpc_id,
            ', '.join([str(_) for _ in split_x_by_y(
                    num_c_per_mpc, num_mprocs_on_mpc)]))
        d[mpc_id] = split_x_by_y(num_c_per_mpc, num_mprocs_on_mpc)
    return d


async def _perform_a_measurement(cont_conn, commands):
    assert state.current == State.Idle
    for c in commands:
        assert isinstance(c, MeasureCommand)
    # Make sure certain parameters are the same for all commands
    assert len(set(c.target for c in commands)) == 1
    assert len(set(c.num_measurers for c in commands)) == 1
    target_fp = commands[0].target
    # num_m_procs: the num of ph measurer processes. one ph measurer computer
    # (m-pc) can have multiple m-procs
    num_m_procs = commands[0].num_measurers
    # num_c_per_mpc: num of connections a m-pc should make total spread evenly
    # across its m-procs
    num_c_per_mpc = commands[0].num_conns_per_measurer
    conns_interested_in_aborts = list(status.get_status('dict')['controllers'])
    # Make sure we have enough m-procs
    if len(status.get_status('dict')['measurers']) < num_m_procs:
        _send_out_aborted_measurement_message(
            conns_interested_in_aborts, 'Not enough measurers available')
        return
    log.info('Starting a measurement with %d commands', len(commands))
    target_conn = await _make_my_target_connection(target_fp)
    if target_conn is None:
        log.error(
            'Could not establish connection to %s. Aborting', target_fp)
        _send_out_aborted_measurement_message(
            conns_interested_in_aborts,
            'Coordinator could not connect to target fp %s' % target_fp)
        return
    log.info('Made our connection to target %s', target_conn.peer)
    state.transition(State.MeasurersConnecting)
    # Choose the m-procs to use
    for m in status.get_status('dict')['measurers']:
        if len(status.get_status('dict')['used_measurers']) == num_m_procs:
            break
        log.debug('Using m-proc with peer %s', m.peer)
        status.use_conn(m)
    # Determine how we're going to split conns across each m-pc's m-procs
    mpc_num_conn_generators = _calc_mpc_num_conn_generators(
        status.get_status('dict')['used_measurers'], num_c_per_mpc)
    # Wait for all m-procs to connect
    # We will either
    # - Hear back, and they say they did connect
    # - Hear back, and they say they failed to connect
    # - Fail to hear back
    tasks = []
    for m in status.get_status('dict')['used_measurers']:
        num_c = next(mpc_num_conn_generators[m.mpc_id])
        if not num_c:
            continue
        log.debug('Telling %s %s to use %d conns', m.mpc_id, m.peer, num_c)
        connect_command = ConnectToTargetCommand(target_fp, num_c)
        tasks.append(
            asyncio.ensure_future(m.relay_connect_command(connect_command)))
    assert len(status.get_status('dict')['used_measurers']) == num_m_procs
    conns_interested_in_aborts.extend(
        status.get_status('dict')['used_measurers'])
    log.debug(
        'Waiting for all measurers to report they\'ve connected to target ...')
    done_tasks, pending_tasks = await asyncio.wait(
        tasks, timeout=10, return_when=asyncio.FIRST_EXCEPTION)
    log.debug(
        '%d measurers are done connecting and haven\'t heard from %d',
        len(done_tasks), len(pending_tasks))
    if len(pending_tasks):
        log.error('Not all measurers responded to our connect command')
        _send_out_aborted_measurement_message(
            conns_interested_in_aborts,
            '%d measurers could not connect to target in time' %
            len(pending_tasks))
        state.transition(State.Idle)
        return
    for task in done_tasks:
        if task.cancelled():
            _send_out_aborted_measurement_message(
                conns_interested_in_aborts,
                'A task waiting for a measurer to connect to target was '
                'cancelled')
            state.transition(State.Idle)
            return
    results = []
    for task in done_tasks:
        assert task.done()
        result = None
        try:
            result = task.result()
        except Exception as e:
            log.error(e)
            _send_out_aborted_measurement_message(
                conns_interested_in_aborts,
                'A task waiting for a measurer to connect to target had an '
                'exception: %s' % e)
            state.transition(State.Idle)
            return
        else:
            results.append(result)
    for res in results:
        if not res.success:
            log.error('A measurer was unable to connect to the target')
            _send_out_aborted_measurement_message(
                conns_interested_in_aborts,
                'A measurer was unable to connect to the target')
            state.transition(State.Idle)
            return
    # All measurers are connected
    state.transition(State.PerformingMeasurement)
    # Tell target to start telling us its background data stats
    target_conn.write_speedtest_start(1)
    # Send each measurement command to the measurers
    assert len(commands) == 1, "Can only send one measurement command"
    for command in commands:
        assert isinstance(command, MeasureCommandBw), "Msm command must be bw"
        command.duration = int(max(
            TESTING_BW_TEST_DURATION * 1.05, TESTING_BW_TEST_DURATION + 1))
        for m in status.get_status('dict')['used_measurers']:
            await m.relay_measure_command(command)

    # Check every second how many results we have until the end of the
    # measurement. Just for fun right now, but eventually with the intension of
    # stopping the measurement once steady state is reached
    start = time.time()
    end = start + TESTING_BW_TEST_DURATION
    while time.time() < end:
        results = status.buffered_results
        num_m = len(results)
        num_res = sum(len(results[m]) for m in results)
        log.debug('Have %d total results from %d measurers', num_res, num_m)
        await asyncio.sleep(1)

    # Tell target relay that we're done
    target_conn.write_speedtest_stop()

    # Reported to controller all results
    results = status.dump_results()
    cont_conn.relay_measure_results(results)

    # Tell everyone we're done
    log.debug('Everything okay so far, but stopping')
    status.clear_used_conns()
    _send_out_aborted_measurement_message(
        conns_interested_in_aborts, 'Everything okay. We\'re done now.')
    state.transition(State.Idle)
    return


def _get_skey(conf):
    fname = conf.getpath('coordinator', 'skey_fname')
    with open(fname, 'rb') as fd:
        return PrivateKey(fd.read())


def gen_parser(sub):
    d = 'Run a command coordinator'
    p = sub.add_parser(
        'coordinator', formatter_class=ArgumentDefaultsHelpFormatter,
        description=d)
    p


async def _listen_for_measurers(conf, boxes):
    host, port = conf['coordinator']['listen_measurer_hostport'].split(':')
    port = int(port)
    loop = asyncio.get_event_loop()
    await loop.create_server(
        lambda: Connection(
            boxes, MeasurerConnectionEventHandlers()), host, port)
    log.info('Listening for measurers on %s:%d', host, port)


async def _listen_for_controllers(conf, boxes):
    host, port = conf['coordinator']['listen_controller_hostport'].split(':')
    port = int(port)
    loop = asyncio.get_event_loop()
    await loop.create_server(
        lambda: Connection(
            boxes, ControllerConnectionEventHandlers()), host, port)
    log.info('Listening for controllers on %s:%d', host, port)


def _load_controller_pkeys(conf):
    for name in conf['known_controllers']:
        log.info('Loading public key for controller %s', name)
        pkey = conf['known_controllers'][name]
        yield PublicKey(bytes(base64.b64decode(pkey)))


def _load_measurer_pkeys(conf):
    for name in conf['known_measurers']:
        log.info('Loading public key for measurer %s', name)
        pkey = conf['known_measurers'][name]
        yield PublicKey(bytes(base64.b64decode(pkey)))


def _load_controller_boxes(conf, skey):
    boxes = []
    for controller_pkey in _load_controller_pkeys(conf):
        boxes.append(Box(skey, controller_pkey))
    return boxes


def _load_measurer_boxes(conf, skey):
    boxes = []
    for measurer_pkey in _load_measurer_pkeys(conf):
        boxes.append(Box(skey, measurer_pkey))
    return boxes


async def main(args, conf):
    global tor_ctrl
    tor_ctrl = launch_tor(conf)
    if not tor_ctrl:
        return 1

    skey = _get_skey(conf)
    log.info('My public key is %s', base64.b64encode(bytes(skey.public_key)))
    measurer_boxes = set(_load_measurer_boxes(conf, skey))
    controller_boxes = set(_load_controller_boxes(conf, skey))

    await _listen_for_measurers(conf, measurer_boxes)
    await _listen_for_controllers(conf, controller_boxes)
    state.transition(State.Idle)
    while True:
        await asyncio.sleep(10)
