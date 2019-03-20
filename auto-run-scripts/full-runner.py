#!/usr/bin/env python3
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import os
import subprocess

###############################################################################
# EDIT HERE
###############################################################################
param_sets = [
#    {'rtt': 0, 'bw': '10Mbps',   'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 2},
#    {'rtt': 0, 'bw': '100Mbps',  'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 2},
#    {'rtt': 0, 'bw': '500Mbps',  'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 2},
#    {'rtt': 0, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 2},
#
    # aaron <--> he (east to west coast)
#    {'rtt': 60,  'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 1},
#    # tityos <--> he (UK to west coast)
#    {'rtt': 140, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 2},
#    # insane high RTT
#    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'rep': 2},
#
#    {'rtt': 0, 'bw': '1000Mbps', 'ploss': '0.001%', 'm': 1, 's': 1, 'rep': 2},
#    {'rtt': 0, 'bw': '1000Mbps', 'ploss': '0.01%',  'm': 1, 's': 1, 'rep': 2},
#    {'rtt': 0, 'bw': '1000Mbps', 'ploss': '0.1%',   'm': 1, 's': 1, 'rep': 2},
#    {'rtt': 0, 'bw': '1000Mbps', 'ploss': '1.0%',   'm': 1, 's': 1, 'rep': 2},

#    {'rtt': 60,  'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '10Mnogrow', 'rep': 2},
#    {'rtt': 60,  'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '20Mnogrow', 'rep': 2},
#    {'rtt': 60,  'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '30Mnogrow', 'rep': 2},
#    {'rtt': 140, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '10Mnogrow', 'rep': 2},
#    {'rtt': 140, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '20Mnogrow', 'rep': 2},
#    {'rtt': 140, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '30Mnogrow', 'rep': 2},
#    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '10Mnogrow', 'rep': 2},
#    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '20Mnogrow', 'rep': 2},
#    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': '30Mnogrow', 'rep': 2},
#    {'rtt': 60,  'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': 'defaults', 'rep': 2},
#    {'rtt': 140, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': 'defaults', 'rep': 2},
#    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': 'defaults', 'rep': 2},

    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 1, 's': 1, 'sysctl': 'defaults', 'rep': 2},
    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 2, 's': 1, 'sysctl': 'defaults', 'rep': 2},
    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 5, 's': 1, 'sysctl': 'defaults', 'rep': 2},
    {'rtt': 200, 'bw': '1000Mbps', 'ploss': '0.0%', 'm': 10, 's': 1, 'sysctl': 'defaults', 'rep': 2},
]
###############################################################################
# NO MORE EDIT
###############################################################################


def _bw_str_to_iperf_bw(bwstr):
    ''' returns, for example, 100M when given 100Mbps '''
    assert bwstr.endswith('Mbps') or bwstr.endswith('Gbps')
    return bwstr[:-3]


def _start_servers(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'start-servers.sh')
    cmd = [start_fname, args.host_target, args.host_ph]
    print('Executing: ', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


def _stop_servers(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'stop-servers.sh')
    cmd = [stop_fname, args.host_target, args.host_ph]
    print('Executing: ', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


def _set_tc(args, lat_ms, ploss_str):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'set-tc.sh')
    for host in [args.host_target, args.host_ph]:
        cmd = [start_fname, host, args.nic, str(lat_ms), ploss_str]
        print('Executing: ', cmd)
        ret = subprocess.call(cmd)
        print('ret:', ret)


def _unset_tc(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'unset-tc.sh')

    for host in [args.host_target, args.host_ph]:
        cmd = [stop_fname, host, args.nic]
        print('Executing: ', cmd)
        ret = subprocess.call(cmd)
        print('ret:', ret)


def _start_ph(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'start-ph.sh')
    cmd = [start_fname, args.host_ph, args.ph_dir]
    print('Executing: ', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


def _stop_ph(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'stop-ph.sh')
    cmd = [stop_fname, args.host_ph]
    print('Executing: ', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


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
    cmd = [start_fname, args.host_target, args.host_ph, args.tor_net_dir, str(bw)]
    print('Executing:', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


def _stop_tor(args):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    stop_fname = os.path.join(script_dname, 'stop-tor.sh')
    cmd = [stop_fname, args.host_target, args.host_ph, args.tor_net_dir]
    print('Executing:', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


def _set_sysctl(args, params):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    script_fname = os.path.join(script_dname, 'set-sysctl.sh')
    sysctl_fname = os.path.join(
        script_dname, 'sysctl.%s.txt' % params['sysctl'])
    for host in [args.host_target, args.host_ph]:
        cmd = [script_fname, host, sysctl_fname]
        print('Executing:', cmd)
        ret = subprocess.call(cmd)
        print('ret:', ret)


def _unset_sysctl(args, params):
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    script_fname = os.path.join(script_dname, 'unset-sysctl.sh')
    sysctl_fname = os.path.join(script_dname, 'sysctl.defaults.txt')
    for host in [args.host_target, args.host_ph]:
        cmd = [script_fname, host, sysctl_fname]
        print('Executing:', cmd)
        ret = subprocess.call(cmd)
        print('ret:', ret)


def _measure(args, out_dir_part, params):
    rep, m, s = params['rep'], params['m'], params['s']
    bw = _bw_str_to_iperf_bw(params['bw'])
    out_dir = os.path.join(args.out_dir, out_dir_part)
    script_dname = os.path.join(args.ph_dir, 'auto-run-scripts')
    start_fname = os.path.join(script_dname, 'measure.sh')
    cmd = [start_fname, args.host_ph, str(rep), str(m), str(s), str(bw), out_dir]
    print('Executing: ', cmd)
    ret = subprocess.call(cmd)
    print('ret:', ret)


def main(args):
    _start_servers(args)
    try:
        for params in param_sets:
            rtt, bw, ploss = params['rtt'], params['bw'], params['ploss']
            sysctl = params['sysctl']
            out_dir_part = '%s-%sms-%sploss-%ssysctl-%sm%sc' % (
                bw, rtt, ploss, sysctl, params['m'], params['s'])
            _set_sysctl(args, params)
            _start_tor(args, params)
            _start_ph(args)
            _set_tc(args, int(rtt / 2), ploss)
            _measure(args, out_dir_part, params)
            _unset_tc(args)
            _stop_ph(args)
            _stop_tor(args)
            _unset_sysctl(args, params)
    finally:
        _unset_tc(args)
        _stop_tor(args)
        _stop_ph(args)
        _unset_sysctl(args, params)
        _stop_servers(args)


if __name__ == '__main__':
    p = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    p.add_argument('--host-target', type=str, default='koios2',
                   help='runs echo server and iperf server')
    p.add_argument('--host-ph', type=str, default='koios3',
                   help='runs all ph processes')
    p.add_argument('--ph-dir', type=str, default=os.path.abspath('.'),
                   help='path to source code, same on all machines')
    p.add_argument('--tor-net-dir', type=str,
                   default='./run',
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
