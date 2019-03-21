#!/usr/bin/env python3
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import io
import os
import os.path as osp
import sys
import subprocess
import time
from subprocess import PIPE
import logging

log = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(funcName)s - %(message)s',
)
log.setLevel(logging.DEBUG)

###############################################################################
# EDIT HERE
###############################################################################
param_sets = [
    {'host': 'ddns',   'icwnd': 10,   'mem_def': '4M',   'mem_max': '4M',   'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 10,   'mem_def': '16M',  'mem_max': '16M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 10,   'mem_def': '32M',  'mem_max': '32M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 10,   'mem_def': '64M',  'mem_max': '64M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 100,  'mem_def': '4M',   'mem_max': '4M',   'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 100,  'mem_def': '16M',  'mem_max': '16M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 100,  'mem_def': '32M',  'mem_max': '32M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 100,  'mem_def': '64M',  'mem_max': '64M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 1000, 'mem_def': '4M',   'mem_max': '4M',   'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 1000, 'mem_def': '16M',  'mem_max': '16M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 1000, 'mem_def': '32M',  'mem_max': '32M',  'c': 1, 'rep': 4},
    {'host': 'ddns',   'icwnd': 1000, 'mem_def': '64M',  'mem_max': '64M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10,   'mem_def': '4M',   'mem_max': '4M',   'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10,   'mem_def': '16M',  'mem_max': '16M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10,   'mem_def': '32M',  'mem_max': '32M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10,   'mem_def': '64M',  'mem_max': '64M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 100,  'mem_def': '4M',   'mem_max': '4M',   'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 100,  'mem_def': '16M',  'mem_max': '16M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 100,  'mem_def': '32M',  'mem_max': '32M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 100,  'mem_def': '64M',  'mem_max': '64M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 1000, 'mem_def': '4M',   'mem_max': '4M',   'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 1000, 'mem_def': '16M',  'mem_max': '16M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 1000, 'mem_def': '32M',  'mem_max': '32M',  'c': 1, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 1000, 'mem_def': '64M',  'mem_max': '64M',  'c': 1, 'rep': 4},

    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 1,  'rep': 4},
    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 2,  'rep': 4},
    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 3,  'rep': 4},
    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 5,  'rep': 4},
    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 10, 'rep': 4},
    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 20, 'rep': 4},
    {'host': 'ddns',   'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 50, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 1,  'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 2,  'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 3,  'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 5,  'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 10, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 20, 'rep': 4},
    {'host': 'amjohn', 'icwnd': 10, 'mem_def': '1M', 'mem_max': '4M', 'c': 50, 'rep': 4},
]
###############################################################################
# NO MORE EDIT
###############################################################################

IPERF_MEASURE_TIME = 240

DEF_ROUTES = {
    'he': 'default via 216.218.222.9 dev eno1 proto static metric 100',
    'ddns': 'default via 192.168.1.1 dev enp0s25 proto dhcp metric 100',
    'amjohn': 'default via 23.91.124.1 dev eth0',
}

SYSCTL_TMPLS = {
    'custom': '''
net.ipv4.tcp_rmem = 4096 {default} {max}
net.ipv4.tcp_wmem = 4096 {default} {max}
net.core.rmem_max = {max}
net.core.wmem_max = {max}
net.core.rmem_default = {max}
net.core.wmem_default = {max}
net.ipv4.route.flush = 1
''',
    'he': '''
net.ipv4.tcp_rmem = 4096 87380 33554432
net.ipv4.tcp_wmem = 4096 65536 33554432
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
    'ddns': '''
net.ipv4.tcp_rmem = 4096 87380 6291456
net.ipv4.tcp_wmem = 4096 16384 4194304
net.core.rmem_max = 212992
net.core.wmem_max = 212992
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
    'amjohn': '''
net.ipv4.tcp_rmem = 4096 87380 4194304
net.ipv4.tcp_wmem = 4096 16384 4194304
net.core.rmem_max = 124928
net.core.wmem_max = 124928
net.core.rmem_default = 124928
net.core.wmem_default = 124928
net.ipv4.route.flush = 1
'''
}

def _mem_str_to_bytes(s):
    assert s[-1] in 'KMG'
    b = int(s[:-1])
    if s[-1] == 'K':
        return b * 1024
    elif s[-1] == 'M':
        return b * 1024 * 1024
    else:
        return b * 1024 * 1024 * 1024


def _execute(cmd, stdin=None, stdout=None, text_mode=True):
    log.debug('Executing: %s', cmd)
    proc = subprocess.Popen(
        cmd,
        stdin=None if not stdin else PIPE,
        stdout=stdout,
        universal_newlines=text_mode)
    stdout_data, stderr_data = proc.communicate(
        input=None if not stdin else stdin.read())
    ret = proc.returncode
    log.debug('Ret: %d', ret)
    output = None if not stdout else stdout_data
    return ret, output

def _start_iperf_server(args, params):
    cmd = '%s --global-bitrate --server --daemon --port %d' %\
        (osp.abspath(osp.expanduser(args.iperf)), args.iperf_server_port)
    _execute(cmd.split(' '))

def _stop_iperf_server(args, params):
    cmd = 'pkill -9 iperf3'
    _execute(cmd.split(' '))


def _measure(args, params):
    for i in range(params['rep']):
        cmd = '%s --client %s --port %d --global-bitrate --bidir -P %d --json '\
            '--time %d | xz' %\
            (args.iperf, args.ip, args.iperf_server_port, params['c'],
            IPERF_MEASURE_TIME)
        cmd = ['ssh', params['host'], cmd]
        _, output = _execute(cmd, stdout=PIPE, text_mode=False)
        out_dir_part = '%s-%dc-%sdef%smax-%scwnd' % (
            params['host'], params['c'],
            params['mem_def'], params['mem_max'],
            params['icwnd'],
        )
        fname_part = 'iperf.%d.json.xz' % i
        fname = osp.join(args.out_dir, out_dir_part, fname_part)
        os.makedirs(osp.dirname(fname), exist_ok=True)
        log.info('Writing %d bytes of output to %s', len(output), fname)
        with open(fname, 'wb') as fd:
            fd.write(output)
        time.sleep(3)


def _set_icwnd(args, params):
    # set here on HE
    cmd = 'sudo ip route change %s initcwnd %d' % (
        DEF_ROUTES['he'], params['icwnd'],
    )
    _execute(cmd.split(' '), text_mode=True)
    # set on remote machine
    cmd = 'sudo ip route change %s initcwnd %d' % (
        DEF_ROUTES[params['host']], params['icwnd'],
    )
    cmd = ['ssh', params['host'], cmd]
    _execute(cmd, text_mode=True)


def _unset_icwnd(args, params):
    # set here on HE
    cmd = 'sudo ip route change %s initcwnd %d' % (
        DEF_ROUTES['he'], 10,
    )
    _execute(cmd.split(' '), text_mode=True)
    # set on remote machine
    cmd = 'sudo ip route change %s initcwnd %d' % (
        DEF_ROUTES[params['host']], 10,
    )
    cmd = ['ssh', params['host'], cmd]
    _execute(cmd, text_mode=True)


def _set_sysctl(args, params):
    cmd = 'sudo sysctl -p -'.split(' ')
    # set it here on HE
    sin = io.StringIO(SYSCTL_TMPLS['custom'].format(
        default=_mem_str_to_bytes(params['mem_def']),
        max=_mem_str_to_bytes(params['mem_max']),
    ))
    _execute(cmd, stdin=sin, text_mode=True)
    # set it on remote machine
    sin = io.StringIO(SYSCTL_TMPLS['custom'].format(
        default=_mem_str_to_bytes(params['mem_def']),
        max=_mem_str_to_bytes(params['mem_max']),
    ))
    cmd = 'sudo sysctl -p -'
    cmd = ['ssh', params['host'], cmd]
    _execute(cmd, stdin=sin, text_mode=True)


def _unset_sysctl(args, params):
    cmd = 'sudo sysctl -p -'.split(' ')
    # set it here on HE
    sin = io.StringIO(SYSCTL_TMPLS['he'])
    _execute(cmd, stdin=sin, text_mode=True)
    # set it on remote machine
    sin = io.StringIO(SYSCTL_TMPLS[params['host']])
    cmd = 'sudo sysctl -p -'
    cmd = ['ssh', params['host'], cmd]
    _execute(cmd, stdin=sin, text_mode=True)


def main(args):
    try:
        for params in param_sets:
            log.debug('--------------------')
            log.debug('Params: %s', params)
            _start_iperf_server(args, params)
            _set_sysctl(args, params)
            _set_icwnd(args, params)
            _measure(args, params)
            _unset_icwnd(args, params)
            _unset_sysctl(args, params)
            _stop_iperf_server(args, params)
    except Exception as e:
        log.exception(e)
    finally:
        _unset_icwnd(args, params)
        _unset_sysctl(args, params)
        _stop_iperf_server(args, params)


if __name__ == '__main__':
    p = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    p.add_argument('--ip', type=str, default='216.218.222.10')
    p.add_argument('--iperf', type=str, default='~/src/iperf3/src/iperf3')
    p.add_argument('--iperf-server-port', type=int, default=10200)
    p.add_argument('-o', '--out-dir', type=str, default=osp.abspath('.'),
                   help='path to store results in')
    args = p.parse_args()
    args.out_dir = osp.abspath(args.out_dir)
    # Don't do this until the last minute. Some hosts that we ssh to have
    # different usernames but otherwise keep the binary in the same location.
    # args.iperf = osp.abspath(args.iperf)
    exit(main(args))
