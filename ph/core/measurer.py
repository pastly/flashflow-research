from ..lib.connection import Connection
from ..lib.connection import ConnectionEventHandlers
from ..lib.chunkpayloads import Aborted
from ..lib.chunkpayloads import ConnectToTargetCommand
from ..lib.chunkpayloads import Identify
from ..lib.chunkpayloads import MeasureCommandBw
from ..lib.chunkpayloads import MeasureResult, BwMeasureResult
from ..lib.statemachine import StateMachine
from ..util.stem import launch_tor
from argparse import ArgumentDefaultsHelpFormatter
from nacl.public import PublicKey, PrivateKey, Box
import asyncio
import base64
import enum
import logging
import time

log = logging.getLogger(__name__)

tor_ctrl = None

# HANDSHAKE_MAGIC_STRING = b'bwpngplz'


class State(enum.Enum):
    Start = 1
    ConnectingToCoordinator = 2
    Idle = 3
    ConnectingToTarget = 4
    WaitingToStart = 5
    PerformingMeasurement = 6


state = StateMachine({
        State.Start: {State.ConnectingToCoordinator},
        State.ConnectingToCoordinator: {State.Idle},
        State.Idle: {State.Idle, State.ConnectingToTarget},
        State.ConnectingToTarget: {State.WaitingToStart, State.Idle},
        State.WaitingToStart: {State.PerformingMeasurement, State.Idle},
        State.PerformingMeasurement: {State.Idle},
    },
    initial=State.Start,
    allow_noop=False
)

need_reconnect_event = asyncio.Event()
allowed_to_start = asyncio.Event()
current_measure_command = None
existing_measurement = None


class CoordinatorConnectionEventHandlers(ConnectionEventHandlers):
    def __init__(self):
        self._connected_to_target = asyncio.Event()
        self._target_conns = []
        pass

    def on_connection_made(self, conn):
        conn.write_object(Identify('Measurer Matt'))
        state.transition(State.Idle)

    def on_data_received(self, coord_conn, obj):
        log.debug('Got from coord: %s', type(obj).__name__)
        if state == State.Idle:
            global existing_measurement
            assert isinstance(obj, ConnectToTargetCommand)
            assert existing_measurement is None
            existing_measurement = asyncio.ensure_future(
                _perform_a_measurement(coord_conn, obj.target))
            return
        elif state == State.ConnectingToTarget:
            assert isinstance(obj, Aborted)
            log.error('Coordinator aborted measurement: %s', obj.msg)
            state.transition(State.Idle)
        elif state == State.WaitingToStart and isinstance(obj, Aborted):
            assert isinstance(obj, Aborted)
            log.error('Coordinator aborted measurement: %s', obj.msg)
            state.transition(State.Idle)
        elif state == State.WaitingToStart and\
                isinstance(obj, MeasureCommandBw):
            global current_measure_command
            assert current_measure_command is None
            current_measure_command = obj
            allowed_to_start.set()
        elif state == State.PerformingMeasurement:
            assert isinstance(obj, Aborted)
            log.error('Coordinator aborted measurement: %s', obj.msg)
            state.transition(State.Idle)
        else:
            log.warn(
                'Don\'t know how to handle %s. Our state is %s',
                type(obj).__name__, state.current)
        return

    def on_connection_lost(self, coord_conn, exc):
        log.debug('Lost connection with coordinator: %s', exc)
        need_reconnect_event.set()


async def _tell_tor_connect_to_target(target_fp):
    log.debug('Telling Tor to connect to %s', target_fp[0:8])
    cmd = 'TESTSPEED %s' % target_fp
    try:
        resp = tor_ctrl.msg(cmd)
    except Exception:
        return None
    else:
        resp = str(resp).split(' ')
        assert len(resp) == 2
        assert resp[0] == 'SPEEDTESTING'
        return resp[1]  # circ id


async def _tell_tor_duration(duration):
    log.debug('Telling Tor to measure for %d secs', duration)
    cmd = 'TESTSPEED %d' % duration
    try:
        tor_ctrl.msg(cmd)
    except Exception:
        return False
    return True


def _report_result(coord_conn):
    last_report_time = time.time()

    def report_results_wrapper(ev_str):
        nonlocal last_report_time
        parts = str(ev_str).strip().split()
        assert len(parts) == 3
        assert parts[0] == 'SPEEDTESTING'
        recv, sent = int(parts[1]), int(parts[2])
        log.debug("%d/%d bytes recv/sent", recv, sent)
        now = time.time()
        res = BwMeasureResult(last_report_time, now, recv, True)
        coord_conn.write_object([res])
        last_report_time = now
    return report_results_wrapper


def _report_results(coord_conn, results):
    for res in results:
        assert isinstance(res, MeasureResult)
    # log.debug('Reporting %d results', len(results))
    coord_conn.write_object(results)


async def _perform_a_measurement(coord_conn, target_fp):
    global existing_measurement
    global current_measure_command
    assert state == State.Idle
    state.transition(State.ConnectingToTarget)
    circ_id = await _tell_tor_connect_to_target(target_fp)
    resp = ConnectToTargetCommand(target_fp, success=circ_id is not None)
    coord_conn.write_object(resp)
    state.transition(State.WaitingToStart)
    log.info('Waiting for coordinator to tell us to start ...')
    await allowed_to_start.wait()
    allowed_to_start.clear()
    assert current_measure_command
    command = current_measure_command
    current_measure_command = None
    log.debug('Starting measurement command %s', type(command).__name__)
    success = await _tell_tor_duration(command.duration)
    assert success
    state.transition(State.PerformingMeasurement)
    ev_listener = _report_result(coord_conn)
    try:
        tor_ctrl.add_event_listener(ev_listener, 'SPEEDTESTING')
    except Exception as e:
        log.error('%s', e)
    assert isinstance(command, MeasureCommandBw)
    existing_measurement = None
    start = time.time()
    end = start + command.duration
    while time.time() < end and state == State.PerformingMeasurement:
        await asyncio.sleep(0.49)
    tor_ctrl.remove_event_listener(ev_listener)
    tor_ctrl.close_circuit(circ_id)
    return


def _get_skey(conf):
    fname = conf.getpath('measurer', 'skey_fname')
    with open(fname, 'rb') as fd:
        return PrivateKey(fd.read())


def gen_parser(sub):
    d = 'Run a command measurer'
    p = sub.add_parser(
        'measurer', formatter_class=ArgumentDefaultsHelpFormatter,
        description=d)
    p


async def main(args, conf):
    global tor_ctrl
    tor_ctrl = launch_tor(conf)

    coordinator_pkey = PublicKey(bytes(base64.b64decode(
        conf['measurer']['coordinator_pkey'])))
    skey = _get_skey(conf)
    log.info('My public key is %s', base64.b64encode(bytes(skey.public_key)))
    boxes = set()
    boxes.add(Box(skey, coordinator_pkey))

    coord_host, coord_port =\
        conf['measurer']['coordinator_hostport'].split(':')
    coord_port = int(coord_port)
    loop = asyncio.get_event_loop()
    state.transition(State.ConnectingToCoordinator)
    sleep_time = 1
    max_sleep_time = 4
    need_reconnect_event.set()
    while True:
        try:
            await loop.create_connection(
                lambda: Connection(
                    boxes, CoordinatorConnectionEventHandlers()),
                coord_host, coord_port)
        except ConnectionRefusedError:
            log.debug('Couldn\'t connect to coordinator')
            sleep_time *= 2
            sleep_time = min(sleep_time, max_sleep_time)
        else:
            sleep_time = 1
            need_reconnect_event.clear()
        await need_reconnect_event.wait()
        log.debug(
            'Attempting reconnection to coordinator in %d seconds', sleep_time)
        await asyncio.sleep(sleep_time)
