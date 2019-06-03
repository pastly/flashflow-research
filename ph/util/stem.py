from stem.control import Controller
from stem.connection import IncorrectSocketType
from stem import (SocketError, ControllerError, InvalidArguments,
                  InvalidRequest, ProtocolError)
import stem.process
import copy
import logging
import os


log = logging.getLogger(__name__)

TORRC_STARTING_POINT = {
    'SocksPort': '0',
    'CookieAuthentication': '1',
    'UseEntryGuards': '0',
    'SafeLogging': '0',
    'LogTimeGranularity': '1',
    'ProtocolWarnings': '1',
    'LearnCircuitBuildTimeout': '0',
    'CircuitBuildTimeout': '10',
    'SplitScheduler': '1',
    'Schedulers': 'KIST,KISTLite',  # Vanilla not an option
}


def get_relay_ip_port(c, fp):
    assert len(fp) == 40
    assert _is_bootstrapped(c)
    try:
        ns = c.get_network_status(fp)
        if ns.address and ns.or_port:
            return ns.address, ns.or_port
    except Exception:
        pass
    return None


def _init_controller_socket(socket):
    assert isinstance(socket, str)
    try:
        c = Controller.from_socket_file(path=socket)
        c.authenticate()
    except (IncorrectSocketType, SocketError):
        log.debug("Error initting controller socket: socket error.")
        return None
    except Exception as e:
        log.exception("Error initting controller socket: %s", e)
        return None
    # TODO: Allow for auth via more than just CookieAuthentication
    return c


def _is_bootstrapped(c):
    try:
        line = c.get_info('status/bootstrap-phase')
    except (ControllerError, InvalidArguments, ProtocolError) as e:
        log.exception("Error trying to check bootstrap phase %s", e)
        return False
    state, _, progress, *_ = line.split()
    progress = int(progress.split('=')[1])
    if state == 'NOTICE' and progress == 100:
        return True
    log.debug('Not bootstrapped. state={} progress={}'.format(state, progress))
    return False


def _parse_user_torrc_config(torrc, torrc_text):
    """Parse the user configuration torrc text call `extra_lines`
    to a dictionary suitable to use with stem and return a new torrc
    dictionary that merges that dictionary with the existing torrc.
    Example:
        [tor]
        extra_lines =
            Log debug file /tmp/tor-debug.log
            NumCPUs 1
    """
    torrc_dict = torrc.copy()
    for line in torrc_text.split('\n'):
        # Remove leading and trailing whitespace, if any
        line = line.strip()
        # Ignore blank lines
        if len(line) < 1:
            continue
        # Some torrc options are only a key, some are a key value pair.
        kv = line.split(None, 1)
        if len(kv) > 1:
            key, value = kv
        else:
            key = kv[0]
            value = None
        # It's really easy to add to the torrc if the key doesn't exist
        if key not in torrc:
            torrc_dict.update({key: value})
        # But if it does, we have to make a list of values. For example, say
        # the user wants to add a SocksPort and we already have
        # 'SocksPort auto' in the torrc. We'll go from
        #     torrc['SocksPort'] == 'auto'
        # to
        #     torrc['SocksPort'] == ['auto', '9050']
        else:
            existing_val = torrc[key]
            if isinstance(existing_val, str):
                torrc_dict.update({key: [existing_val, value]})
            else:
                assert isinstance(existing_val, list)
                existing_val.append(value)
                torrc_dict.update({key: existing_val})
        log.debug('Adding "%s %s" to torrc with which we are launching Tor',
                  key, value)
    return torrc_dict


def launch_tor(conf, bw_lim=125000000):
    torrc = copy.deepcopy(TORRC_STARTING_POINT)
    datadir = conf.getpath('tor', 'datadir')
    pidfile = conf.getpath('tor', 'pidfile')
    ctrl_sock = conf.getpath('tor', 'control_socket')
    notice_log = conf.getpath('tor', 'notice_log')
    extra_lines = conf.get('tor', 'extra_lines')
    tor_path = conf.getpath('tor', 'path')
    os.makedirs(datadir, mode=0o700, exist_ok=True)
    torrc.update({
        'DataDirectory': datadir,
        'PidFile': pidfile,
        'ControlSocket': ctrl_sock,
        'Log': [
            'NOTICE file %s' % notice_log,
        ],
        'BandwidthRate': str(bw_lim),
        'BandwidthBurst': str(bw_lim),
    })
    log.debug('Launching Tor with BR %s and BB %s', bw_lim, bw_lim)
    torrc = _parse_user_torrc_config(torrc, extra_lines)
    try:
        stem.process.launch_tor_with_config(
            torrc, tor_cmd=tor_path, init_msg_handler=log.debug,
            take_ownership=True)
    except Exception as e:
        log.exception('Error trying to launch tor: %s', e)
        return None
    c = _init_controller_socket(ctrl_sock)
    try:
        # c.set_conf('__DisablePredictedCircuits', '1')
        # c.set_conf('__LeaveStreamsUnattached', '1')
        pass
    except (ControllerError, InvalidArguments, InvalidRequest) as e:
        log.exception('Error trying to launch tor: %s', e)
        return None
    return c
