from ..lib.connection import Connection
from ..lib.connection import ConnectionEventHandlers
from ..lib.chunkpayloads import Identify, MeasureResult, Aborted
from ..lib.controllercommands import ControllerCommand
from ..lib.controllercommands import ControllerCommandHelp
from ..lib.controllercommands import ControllerCommandStatus
from ..lib.controllercommands import ControllerCommandMeasure
from ..lib.controllercommands import ControllerCommandQuit
from ..lib.controllercommands import MalformedControllerCommand
from ..lib.controllercommands import UnknownControllerCommand
from ..lib.controllercommands import get_help_string
from ..lib.statemachine import StateMachine
from argparse import ArgumentDefaultsHelpFormatter
from aioconsole.stream import ainput
from nacl.public import PublicKey, PrivateKey, Box
from collections import deque
import asyncio
import base64
import enum
import logging
import pickle

log = logging.getLogger(__name__)
command_queue = deque()
cached_controller_command = None
one_command = False


class State(enum.Enum):
    Start = 1
    Idle = 2
    GetStatus = 3
    GetMeasurement = 4


state = StateMachine({
        State.Start: {State.Idle},
        State.Idle: {State.GetStatus, State.GetMeasurement},
        State.GetStatus: {State.Idle},
        State.GetMeasurement: {State.Idle},
    },
    initial=State.Start,
    allow_noop=False
)


class CoordinatorConnectionEventHandlers(ConnectionEventHandlers):
    def on_connection_made(self, conn):
        conn.write_object(Identify('Controller Matt'))
        state.transition(State.Idle)
        while len(command_queue):
            command = command_queue.pop()
            _handle_remote_command(conn, command)

    def on_data_received(self, conn, obj):
        if state == State.GetStatus:
            assert isinstance(obj, str)
            print(obj)
            state.transition(State.Idle)
        elif state == State.GetMeasurement:
            if isinstance(obj, Aborted):
                log.error('Measurement was aborted: %s', obj.msg)
                state.transition(State.Idle)
                if one_command:
                    exit(0)
                return
            assert isinstance(obj, dict)
            for measurer in obj:
                for res in obj[measurer]:
                    assert isinstance(res, MeasureResult)
            global cached_controller_command
            _write_result_file(cached_controller_command, obj)
            cached_controller_command = None
            state.transition(State.Idle)
        else:
            log.warn(
                'Didn\'t handle %s object. Current state is %s' %
                (type(obj).__name__, state.current))
        if one_command:
            exit(0)


def _get_skey(conf):
    fname = conf.getpath('controller', 'skey_fname')
    with open(fname, 'rb') as fd:
        return PrivateKey(fd.read())


async def _get_command():
    while True:
        command = (await ainput('command> ')).strip()
        if command:
            return command


def _write_result_file(command, results):
    log.info('Writing results to %s', command.name)
    with open(command.name, 'wb') as fd:
        pickle.dump({
            'command': command,
            'results': results
        }, fd, protocol=4)


def _handle_local_command(command):
    log.debug('Got local command %s', command)
    if isinstance(command, ControllerCommandHelp):
        print(get_help_string())


def _handle_remote_command(conn, command):
    log.debug('Sending %s command' % type(command).__name__)
    if isinstance(command, ControllerCommandStatus):
        state.transition(State.GetStatus)
    elif isinstance(command, ControllerCommandMeasure):
        state.transition(State.GetMeasurement)
        global cached_controller_command
        assert cached_controller_command is None
        cached_controller_command = command
    else:
        assert None, 'Don\'t know how to send %s command' %\
            type(command).__name__
    conn.write_object(command)


def gen_parser(sub):
    d = 'Interact with a coordinator'
    p = sub.add_parser(
        'controller', formatter_class=ArgumentDefaultsHelpFormatter,
        description=d)
    p.add_argument(
        '-c', '--command', dest='immediate_command', default=None,
        help='Command to run after connecting to the coordinator')
    p.add_argument(
        '--one', action='store_true', help='Exit after first command')


async def main(args, conf):
    global one_command
    one_command = args.one
    coordinator_pkey = bytes(base64.b64decode(
        conf['controller']['coordinator_pkey']))
    coordinator_pkey = PublicKey(coordinator_pkey)
    skey = _get_skey(conf)
    log.info('My public key is %s', base64.b64encode(bytes(skey.public_key)))
    box = Box(skey, coordinator_pkey)

    coord_host, coord_port =\
        conf['controller']['coordinator_hostport'].split(':')
    coord_port = int(coord_port)
    loop = asyncio.get_event_loop()

    if args.immediate_command:
        command_queue.appendleft(ControllerCommand.from_string(
            args.immediate_command))

    connection = Connection({box}, CoordinatorConnectionEventHandlers())

    await loop.create_connection(
        lambda: connection, coord_host, coord_port)
    while True:
        try:
            command = ControllerCommand.from_string(await _get_command())
        except UnknownControllerCommand as e:
            log.warn('%s', e)
            continue
        except MalformedControllerCommand as e:
            print(e)
            continue
        except EOFError:
            break

        if isinstance(command, ControllerCommandQuit):
            break

        if command.is_local:
            _handle_local_command(command)
        else:
            _handle_remote_command(connection, command)
    # connection.quitting()
