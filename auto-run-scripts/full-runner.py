#!/usr/bin/env python3
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import copy
import os
import io
import sys
import subprocess
import logging

log = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - '
    '%(funcName)s - %(message)s',
)
log.setLevel(logging.DEBUG)

###############################################################################
# EDIT HERE
###############################################################################
# From ~/src/ripe-global-map data
# These are latencies
# 0 percentile: 0.198960
# 5 percentile: 13.701477
# 25 percentile: 27.386052
# 50 percentile: 59.257986
# 75 percentile: 98.815692
# 95 percentile: 170.764294
# 100 percentile: 3669.489161
param_sets = [
    {'rtt': 340, 'mem_def': 'def', 'mem_max': 'def', 'rep': 5},
    {'rtt': 340, 'mem_def':  '1M', 'mem_max': '64M', 'rep': 5},
#    {'rtt': 340, 'mem_def':  '1M', 'mem_max': '16M', 'rep': 2},
#    {'rtt': 200, 'mem_def': 'def', 'mem_max': 'def', 'rep': 2},
#    {'rtt': 200, 'mem_def':  '1M', 'mem_max': '64M', 'rep': 2},
#    {'rtt': 200, 'mem_def':  '1M', 'mem_max': '16M', 'rep': 2},
#    {'rtt': 120, 'mem_def': 'def', 'mem_max': 'def', 'rep': 2},
#    {'rtt': 120, 'mem_def':  '1M', 'mem_max': '64M', 'rep': 2},
#    {'rtt': 120, 'mem_def':  '1M', 'mem_max': '16M', 'rep': 2},
#    {'rtt':  56, 'mem_def': 'def', 'mem_max': 'def', 'rep': 2},
#    {'rtt':  56, 'mem_def':  '1M', 'mem_max': '64M', 'rep': 2},
#    {'rtt':  56, 'mem_def':  '1M', 'mem_max': '16M', 'rep': 2},
#    {'rtt':  28, 'mem_def': 'def', 'mem_max': 'def', 'rep': 2},
#    {'rtt':  28, 'mem_def':  '1M', 'mem_max': '64M', 'rep': 2},
#    {'rtt':  28, 'mem_def':  '1M', 'mem_max': '16M', 'rep': 2},
]
###############################################################################
# NO MORE EDIT
###############################################################################
for params in param_sets:
    params['bw'] = '8Gbps'

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
    'koiosX': '''
net.ipv4.tcp_rmem = 4096        87380   6291456
net.ipv4.tcp_wmem = 4096        16384   4194304
net.core.rmem_max = 212992
net.core.wmem_max = 212992
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
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


def _bw_str_to_iperf_bw(bwstr):
    ''' returns, for example, 100M when given 100Mbps '''
    assert bwstr.endswith('Mbps') or bwstr.endswith('Gbps')
    return bwstr[:-3]


def _start_servers(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'start-servers.sh')
    cmd = [start_fname, args.host_target, args.host_ph]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _stop_servers(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'stop-servers.sh')
    cmd = [stop_fname, args.host_target, args.host_ph]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _start_top(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    script_fname = os.path.join(script_dname, 'start-top.sh')
    for host in [args.host_target, args.host_ph]:
        cmd = [script_fname, host, '/scratch/mtraudt/top.txt']
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)


def _stop_top(args, out_dir_part, i):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    script_fname = os.path.join(script_dname, 'stop-top.sh')
    out_dir = os.path.join(args.out_dir, out_dir_part)
    os.makedirs(out_dir, exist_ok=True)
    target_out_fname = os.path.join(out_dir, 'target.cpu.%d.txt.xz' % i)
    measurer_out_fname = os.path.join(out_dir, 'measurer.cpu.%d.txt.xz' % i)
    target_out_fd = open(target_out_fname, 'wb')
    measurer_out_fd = open(measurer_out_fname, 'wb')
    cmd = [script_fname, args.host_target, '/scratch/mtraudt/top.txt']
    log.debug('Executing: %s', cmd)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        target_out_fd.write(proc.stdout.read())
    # log.debug('ret: %s', ret)
    cmd = [script_fname, args.host_ph, '/scratch/mtraudt/top.txt']
    log.debug('Executing: %s', cmd)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        measurer_out_fd.write(proc.stdout.read())
    # log.debug('ret: %s', ret)


def _set_tc(args, lat_ms):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'set-tc.sh')
    for host in [args.host_target, args.host_ph]:
        cmd = [start_fname, host, args.nic, str(lat_ms)]
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)


def _unset_tc(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'unset-tc.sh')

    for host in [args.host_target, args.host_ph]:
        cmd = [stop_fname, host, args.nic]
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)


def _start_ph(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'start-ph.sh')
    cmd = [start_fname, args.host_ph, args.host_target, args.tor_net_dir]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _stop_ph(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'stop-ph.sh')
    cmd = [stop_fname, args.host_ph]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _bw_str_to_bytes(bw_str):
    num = int(bw_str[:-4])
    tail = bw_str[-4:]
    assert tail in ('Mbps', 'Gbps')
    if tail == 'Mbps':
        return int(num * 1000 * 1000 / 8)
    return int(num * 1000 * 1000 * 1000 / 8)


def _start_tor(args, params):
    bw = _bw_str_to_bytes(params['bw'])
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'start-tor.sh')
    cmd = [start_fname, args.host_target, args.tor_net_dir, str(bw)]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _stop_tor(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'stop-tor.sh')
    cmd = [stop_fname, args.host_target, args.tor_net_dir]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _set_sysctl(args, params):
    if params['mem_def'] == 'def':
        assert params['mem_max'] == 'def'
        tmpl = SYSCTL_TMPLS['koiosX']
        text = tmpl
    else:
        tmpl = SYSCTL_TMPLS['custom']
        text = tmpl.format(
            default=_mem_str_to_bytes(params['mem_def']),
            max=_mem_str_to_bytes(params['mem_max']),
        )
    for host in [args.host_target, args.host_ph]:
        cmd = 'sudo sysctl -p -'
        cmd = ['ssh', host, cmd]
        log.debug('Executing: %s', cmd)
        sin = io.StringIO(text)
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout_data, stderr_data = proc.communicate(input=sin.read())
        ret = proc.returncode
        log.debug('%s', stdout_data)
        log.debug('ret: %s', ret)


def _unset_sysctl(args, params):
    p = copy.deepcopy(params)
    p['mem_def'] = 'def'
    p['mem_max'] = 'def'
    return _set_sysctl(args, p)


def _measure(args, out_dir_part, i, params):
    bw = _bw_str_to_iperf_bw(params['bw'])
    out_dir = os.path.join(args.out_dir, out_dir_part)
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'measure.sh')
    cmd = [
        start_fname, args.host_ph, str(i), str(bw), args.tor_net_dir,
        out_dir]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def main(args):
    # _start_servers(args)
    try:
        for params in param_sets:
            rtt = params['rtt']
            out_dir_part = '%sms-%sdef%smax' % (
                rtt, params['mem_def'], params['mem_max'])
            for i in range(1, 1+params['rep']):
                # raise Exception('foo')
                _set_sysctl(args, params)
                _start_tor(args, params)
                _start_ph(args)
                _start_top(args)
                _set_tc(args, int(rtt / 2))
                _measure(args, out_dir_part, i, params)
                _unset_tc(args)
                _stop_top(args, out_dir_part, i)
                _stop_ph(args)
                _stop_tor(args)
                _unset_sysctl(args, params)
    finally:
        _unset_tc(args)
        _stop_top(args, out_dir_part, i)
        _stop_tor(args)
        _stop_ph(args)
        _unset_sysctl(args, params)
        # _stop_servers(args)


if __name__ == '__main__':
    p = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    p.add_argument('--host-target', type=str, default='koios2',
                   help='runs echo server and iperf server')
    p.add_argument('--host-ph', type=str, default='koios3',
                   help='runs all ph processes')
    p.add_argument('--ph-dir', type=str,
                   default='/scratch/mtraudt/purple-hurtz-code',
                   help='path to source code, must exist on this machine and '
                   '--host-ph')
    p.add_argument('--tor-net-dir', type=str,
                   default='/scratch/mtraudt/run',
                   help='path a copy of Matt\'s simple little localhost tor '
                   'network')
    p.add_argument('--nic', type=str, default='p2p1',
                   help='NIC on ph and target machines')
    p.add_argument('-o', '--out-dir', type=str, default=os.path.abspath('.'),
                   help='path to store results in')
    args = p.parse_args()
    args.ph_dir = os.path.abspath(args.ph_dir)
    args.tor_net_dir = os.path.abspath(args.tor_net_dir)
    args.out_dir = os.path.abspath(args.out_dir)
    main(args)
