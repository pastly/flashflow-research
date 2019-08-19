#!/usr/bin/env python3
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import copy
import datetime
import io
import os
import sys
import subprocess
import time
import logging
import re
from math import ceil
from itertools import chain, combinations

log = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    format='full-runner %(asctime)s %(levelname)s %(filename)s:%(lineno)s - '
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
    {
        'hosts': ['ddns'],
        'host_bws': ['unlim'], 'target_bw': 'unlim',
        'host_tor_bws': ['unlim'], 'tor_bw': 'unlim',
        'mem_def': 'def', 'mem_max': 'def',
        'num_c_overall': 160,
    },
]
###############################################################################
# NO MORE EDIT
###############################################################################
# orig = copy.deepcopy(param_sets)
param_sets = []
# for params in orig:
#     for bw in ['250Mbps', '500Mbps', '750Mbps', 'unlim']:
#         for hostset in chain(
#                 combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 4),
#                 combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 3),
#                 combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 2),
#                 combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 1)):
#             #if len(hostset) != 4:
#             #    continue
#             #if bw != '250Mbps':
#             #    continue
#             # measurer-limited
#             new = copy.deepcopy(params)
#             new['hosts'] = list(hostset)
#             new['host_bws'] = ['unlim'] * len(hostset)
#             new['host_tor_bws'] = [bw] * len(hostset)
#             new['tor_bw'] = 'unlim'
#             param_sets.append(new)
#             # target-limited
#             if bw == 'unlim': continue
#             new = copy.deepcopy(params)
#             new['hosts'] = list(hostset)
#             new['host_bws'] = ['unlim'] * len(hostset)
#             new['host_tor_bws'] = ['unlim'] * len(hostset)
#             new['tor_bw'] = bw
#             param_sets.append(new)

# for p in param_sets:
#     print(p)
# exit(0)

SYSCTL_TMPLS = {
    'custom': '''
net.ipv4.tcp_rmem = 4096 {default} {max}
net.ipv4.tcp_wmem = 4096 {default} {max}
net.core.rmem_max = {max}
net.core.wmem_max = {max}
net.core.rmem_default = {default}
net.core.wmem_default = {default}
net.ipv4.route.flush = 1
''',
    'ddns': '''
net.ipv4.tcp_rmem = 4096	87380	6291456
net.ipv4.tcp_wmem = 4096	16384	4194304
net.core.rmem_max = 212992
net.core.wmem_max = 212992
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
    'he': '''
net.ipv4.tcp_rmem = 4096	87380	33554432
net.ipv4.tcp_wmem = 4096	65536	33554432
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
    'nrl': '''
net.ipv4.tcp_rmem = 4096	87380	4194304
net.ipv4.tcp_wmem = 4096	16384	4194304
net.core.rmem_max = 124928
net.core.wmem_max = 124928
net.core.rmem_default = 124928
net.core.wmem_default = 124928
net.ipv4.route.flush = 1
''',
    'india.do': '''
net.ipv4.tcp_rmem = 4096	87380	6291456
net.ipv4.tcp_wmem = 4096	16384	4194304
net.core.rmem_max = 212992
net.core.wmem_max = 212992
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
    'amst.do': '''
net.ipv4.tcp_rmem = 4096	87380	6291456
net.ipv4.tcp_wmem = 4096	16384	4194304
net.core.rmem_max = 212992
net.core.wmem_max = 212992
net.core.rmem_default = 212992
net.core.wmem_default = 212992
net.ipv4.route.flush = 1
''',
}

IP_MAP = {
    'ddns': '100.15.232.6',
    'nrl': '23.91.124.124',
    'amst.do': '104.248.93.55',
    'india.do': '134.209.148.91',
}

PHNEW_CTRL_PORT_MAP = {
    'ddns': 9000,
    'nrl': 9000,
    'amst.do': 9000,
    'india.do': 9000,
}

INTERFACE_MAP = {
    'ddns': 'enp0s25',
    'nrl': 'eth0',
    'he': 'eno1',
    'india.do': 'eth0',
    'amst.do': 'eth0',
}

NUM_CPU_MAP = {
    'ddns': 12,
    'nrl': 8,
    'he': 8,
    'india.do': 2,
    'amst.do': 2,
}

TCP_BOMB_BW = {
    'he':       918.52,
    'nrl':      563.09,
    'ddns':     713.48,
    'india.do': 1283.87,
    'amst.do':  1170.49,
}

UDP_BOMB_BW = {
    'he':       954.78,
    'nrl':      946.44,
    'ddns':     941.81,
    'india.do': 1076.27,
    'amst.do':  1611.19,
}


def param_sets_from_file(fname):
    with open(fname, 'rt') as fd:
        for line in fd:
            line = line.strip()
            if not len(line) or line.startswith('#'):
                continue
            out = {
                'hosts': [],
                'host_bws': [], 'target_bw': '',
                'host_tor_bws': [], 'tor_bw': '',
                'mem_def': 'def', 'mem_max': 'def',
                'num_c_overall': 0,
                'bg_pcent': 0,
            }
            # make sure its a match
            pat = r'.*(he-.*-defdefdefmax)/?.*'
            match = re.match(pat, line)
            assert match
            match = match.group(1)
            assert match.startswith('he-')
            assert match.endswith('-defdefdefmax')
            parts = match.split('-')
            target, measurers, n_socks, bg_pcent, target_bw_str, measurers_bw_str, mem = parts
            # set stuff fetched from the line
            assert target == 'he'
            out['hosts'] = measurers.split(',')
            # assert n_socks == '160s'
            assert n_socks.endswith('s')
            out['num_c_overall'] = int(n_socks[:n_socks.index('s')])
            out['tor_bw'] = target_bw_str
            out['host_tor_bws'] = measurers_bw_str.split(',')
            assert int(bg_pcent) >= 1 and int(bg_pcent) <= 99
            out['bg_pcent'] = int(bg_pcent)
            assert mem == 'defdefdefmax'
            # set other stuff stuff
            out['host_bws'] = ['unlim'] * len(out['hosts'])
            out['target_bw'] = 'unlim'
            # final sanity check
            assert out['hosts']
            assert out['host_bws']
            assert out['target_bw']
            assert out['host_tor_bws']
            assert out['tor_bw']
            assert out['mem_def']
            assert out['mem_max']
            assert out['num_c_overall']
            assert out['bg_pcent'] >= 1 and out['bg_pcent'] <= 99
            yield out

def _split_x_by_y(x, y):
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


def _num_socks_for_host(host, others, total_socks):
    ''' Give **host** part of **total_socks** proportional to its fraction of
    UDP-bomb-measured bandwidth of all hosts **host** + **others**
    '''
    host_bw = TCP_BOMB_BW[host]
    total_bw = host_bw + sum(TCP_BOMB_BW[h] for h in others)
    return round(host_bw * total_socks / total_bw)


def _bw_str_to_bytes(bw_str):
    num = float(bw_str[:-4])
    tail = bw_str[-4:]
    assert tail in ('Kbps', 'Mbps', 'Gbps')
    if tail == 'Kbps':
        return ceil(num * 1000 / 8)
    if tail == 'Mbps':
        return ceil(num * 1000 * 1000 / 8)
    return ceil(num * 1000 * 1000 * 1000 / 8)


def _mem_str_to_bytes(s):
    assert s[-1] in 'KMG'
    b = int(s[:-1])
    if s[-1] == 'K':
        return b * 1024
    elif s[-1] == 'M':
        return b * 1024 * 1024
    else:
        return b * 1024 * 1024 * 1024



def _set_sysctl(args, params):
    for host in [args.target_ssh_ip, *params['hosts']]:
        if params['mem_def'] == 'def':
            assert params['mem_max'] == 'def'
            tmpl = SYSCTL_TMPLS[host]
            text = tmpl
        else:
            tmpl = SYSCTL_TMPLS['custom']
            text = tmpl.format(
                default=_mem_str_to_bytes(params['mem_def']),
                max=_mem_str_to_bytes(params['mem_max']),
            )
        cmd = 'sudo sysctl -p -'
        cmd = ['ssh', host, cmd]
        log.debug('Executing: %s', cmd)
        log.debug('With input: %s', text)
        sin = io.StringIO(text)
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            universal_newlines=True)
        stdout_data, stderr_data = proc.communicate(input=sin.read())
        log.debug('ret: %s', proc.returncode)


def _unset_sysctl(args, params):
    p = copy.deepcopy(params)
    p['mem_def'] = 'def'
    p['mem_max'] = 'def'
    return _set_sysctl(args, p)


def _set_tc(args, params):
    script = 'set-tc.sh'
    # set tc on target
    host = args.target_ssh_ip
    dev = INTERFACE_MAP[host]
    rate = params['target_bw']
    lat = 0
    if rate != 'unlim' or lat != 0:
        rate = '%dbps' % _bw_str_to_bytes(rate)
        cmd = 'bash -ls {dev} {r} {lat}'.format(dev=dev, r=rate, lat=lat)
        cmd = ['ssh', host, cmd]
        log.debug('Executing: %s (with %s as input)', cmd, script)
        ret = subprocess.call(cmd, stdin=open(script, 'rt'))
        log.debug('ret: %s', ret)
    else:
        log.debug(
            'Skipping tc for host %s b/c %s rate and %d lat', host, rate, lat)
    # set tc on each measurer
    for host, rate in zip(params['hosts'], params['host_bws']):
        dev = INTERFACE_MAP[host]
        lat = 0
        if rate != 'unlim' or lat != 0:
            rate = '%dbps' % _bw_str_to_bytes(rate)
            cmd = 'bash -ls {dev} {r} {lat}'.format(dev=dev, r=rate, lat=lat)
            cmd = ['ssh', host, cmd]
            log.debug('Executing: %s (with %s as input)', cmd, script)
            ret = subprocess.call(cmd, stdin=open(script, 'rt'))
            log.debug('ret: %s', ret)
        else:
            log.debug(
                'Skipping tc for host %s b/c %s rate and %d lat',
                host, rate, lat)


def _unset_tc(args, params):
    script = 'unset-tc.sh'
    for host in [args.target_ssh_ip, *params['hosts']]:
        dev = INTERFACE_MAP[host]
        cmd = 'bash -ls {dev}'.format(dev=dev)
        cmd = ['ssh', host, cmd]
        log.debug('Executing: %s (with %s as input)', cmd, script)
        ret = subprocess.call(cmd, stdin=open(script, 'rt'))
        log.debug('ret: %s', ret)


def _measure_ping(args, out_dir, i, params):
    assert len(params['hosts']) == 1
    cmd = 'ssh %s ping -c %d %s' % (
        params['hosts'][0],
        args.num_pings,
        args.target_bind_ip,
    )
    cmd = cmd.split()
    os.makedirs(out_dir, exist_ok=True)
    out_fname = _get_next_fname(out_dir, 'ping.{i}.txt', i)
    with open(out_fname, 'wt') as fd:
        fd.write('#\n# %s\n#\n' % str(datetime.datetime.now()))
    log.debug('Executing: %s (with %s getting output)', cmd, out_fname)
    ret = subprocess.call(cmd, stdout=open(out_fname, 'at'))
    log.debug('ret: %s', ret)


def _start_bwevents(args, params):
    script = 'start-bwevents.sh'
    if params['tor_bw'] == 'unlim':
        tor_bw = 125000000
    else:
        tor_bw = max(_bw_str_to_bytes(params['tor_bw']), 76800)
    assert params['bg_pcent'] >= 1 and params['bg_pcent'] <= 99
    cmd = 'bash -ls {bw} {bg_pcent} {fname}'.format(
        bw=tor_bw,
        bg_pcent=params['bg_pcent'],
        net_dir=args.target_tor_net_dir,
        fname='/tmp/bwevents.log',
    )
    cmd = ['ssh', args.target_ssh_ip, cmd]
    log.debug('Executing: %s (with %s as input)', cmd, script)
    ret = subprocess.call(cmd, stdin=open(script, 'rt'))
    log.debug('ret: %s', ret)


def _stop_bwevents(args):
    script = 'stop-bwevents.sh'
    cmd = 'bash -ls'
    cmd = ['ssh', args.target_ssh_ip, cmd]
    log.debug('Executing: %s (with %s as input)', cmd, script)
    ret = subprocess.call(cmd, stdin=open(script, 'rt'))
    log.debug('ret: %s', ret)


def _start_phnew_tor_clients(args, params):
    procs = []
    extra_wait = 0
    hosts = copy.copy(params['hosts'])
    host_tor_bws = copy.copy(params['host_tor_bws'])
    if args.bg_host not in hosts:
        hosts += [args.bg_host]
        host_tor_bws += ['unlim']
    for host, bw_lim in zip(hosts, host_tor_bws):
        n_mproc = NUM_CPU_MAP[host]
        bg_client_n = 0 if host != args.bg_host else n_mproc + 1
        extra_wait += n_mproc / 2
        if bw_lim == 'unlim':
            bw_lim = 125000000
        else:
            # close enough to even distribution of bw lim across cores
            bw_lim = _bw_str_to_bytes(bw_lim)
            bw_lim = (bw_lim // n_mproc) + 1
            bw_lim = max(bw_lim, 76800)
        cmd = 'bash -ls {d} {tor_host} {tor_cache_dir} {bw} {n_mproc} {bg}'.format(
            d=args.measurer_ph_dir,
            tor_host=args.target_ssh_ip,
            tor_cache_dir=args.target_cache_dir,
            bw=bw_lim,
            n_mproc=n_mproc,
            bg=bg_client_n,
        )
        script = 'start-phnew-tor-client.sh'
        cmd = ['ssh', host, cmd]
        log.debug('Executing: %s (with %s as input)', cmd, script)
        procs.append(
            subprocess.Popen(cmd, stdin=open(script, 'rt')))
    rets = []
    for p in procs:
        rets.append(p.wait())
    log.debug('rets: %s', rets)
    log.debug('Sleeping an extra %f seconds' % extra_wait)
    time.sleep(extra_wait)


def _stop_phnew_tor_clients(args, params):
    return _stop_ph(args, params)


def _measure_phnew(args, out_dir, i, params):
    try:
        # _start_tor(args, params)
        _start_phnew_tor_clients(args, params)
        _start_bwevents(args, params)
        _start_dstat(args, params)
        os.makedirs(out_dir, exist_ok=True)
        hosts, host_bws, host_socks, host_ips, host_ports = [], [], [], [], []
        total_num_socks = params['num_c_overall']
        socks_per_host_iter = _split_x_by_y(total_num_socks, len(params['hosts']))
        for host, host_tor_bw in zip(params['hosts'], params['host_tor_bws']):
            num_socks_this_host = next(socks_per_host_iter)
            num_cpu = NUM_CPU_MAP[host]
            socks_per_cpu_iter = _split_x_by_y(num_socks_this_host, num_cpu)
            for cpu_num in range(num_cpu):
                bw = max(ceil(_bw_str_to_bytes(host_tor_bw)/num_cpu), 76800)
                hosts.append(host)
                host_bws.append(str(bw))
                host_socks.append(str(next(socks_per_cpu_iter)))
                host_ips.append(IP_MAP[host])
                host_ports.append(str(PHNEW_CTRL_PORT_MAP[host]+cpu_num))
        hosts.append('bg')
        host_bws.append('125000')
        host_socks.append('1')
        host_ips.append(IP_MAP[args.bg_host])
        host_ports.append(str(NUM_CPU_MAP[args.bg_host]+9000))
        hosts = ','.join(hosts)
        host_bws = ','.join(host_bws)
        host_socks = ','.join(host_socks)
        host_ips = ','.join(host_ips)
        host_ports = ','.join(host_ports)
        log.debug('%s %s %s %s %s', hosts, host_bws, host_socks, host_ips, host_ports)
        cmd = 'bash -ls {d} {fname} {fp} {dur} {pw} {h} {h_bw} {h_s} {h_ips} {h_ports}'.format(
            d=args.coord_ph_dir,
            fname='/tmp/phnew.test.txt.xz',
            fp=args.target_fp,
            dur=args.ph_dur,
            pw=args.ph_password,
            h=hosts,
            h_bw=host_bws,
            h_s=host_socks,
            h_ips=host_ips,
            h_ports=host_ports,
        )
        log.info('Sleeping for 60 seconds for baseline bg traffic data collection')
        time.sleep(60)
        script = 'measure-ph.sh'
        cmd = ['ssh', args.coord_ssh_ip, cmd]
        log.debug('Executing: %s (with %s as input)', cmd, script)
        ret = subprocess.call(cmd, stdin=open(script, 'rt'))
        log.debug('ret: %s', ret)
        _stop_phnew_tor_clients(args, params)
        if ret == 0:
            log.info('Sleeping for 60 seconds for after-measurement bg traffic data collection')
            time.sleep(60)
        _stop_dstat(args, params)
        _stop_bwevents(args)
        if ret != 0:
            return False
        bwevents_out_fname = _get_next_fname(out_dir, 'bwevents.{h}.ph.{i}.log', i, h=args.target_ssh_ip)
        cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
            host=args.target_ssh_ip,
            remote_path='/tmp/bwevents.log',
            local_path=bwevents_out_fname,
        ).split()
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)
        ph_out_fname = _get_next_fname(out_dir, 'ph.{i}.txt.xz', i)
        cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
            host=args.coord_ssh_ip,
            remote_path='/tmp/phnew.test.txt.xz',
            local_path=ph_out_fname,
        ).split()
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)
        for host in [args.target_ssh_ip] + params['hosts']:
            dstat_out_fname = _get_next_fname(out_dir, 'dstat.{h}.ph.{i}.csv', i, h=host)
            cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
                host=host,
                remote_path='/tmp/dstat.csv',
                local_path=dstat_out_fname,
            ).split()
            log.debug('Executing: %s', cmd)
            ret = subprocess.call(cmd)
            log.debug('ret: %s', ret)
        return True
    finally:
        pass
        _stop_dstat(args, params)
        _stop_bwevents(args)
        _stop_phnew_tor_clients(args, params)
        # _stop_tor(args)


def _start_dstat(args, params):
    cmd = 'bash -ls {fname}'.format(
        fname='/tmp/dstat.csv',
    )
    script = 'start-dstat.sh'
    procs = []
    for host in [args.target_ssh_ip] + params['hosts']:
        ssh_cmd = ['ssh', host, cmd]
        log.debug('Executing: %s (with %s as input)', ssh_cmd, script)
        procs.append(
            subprocess.Popen(ssh_cmd, stdin=open(script, 'rt')))
    rets = []
    for p in procs:
        rets.append(p.wait())
    log.debug('rets: %s', rets)


def _stop_dstat(args, params):
    script = 'stop-dstat.sh'
    for host in [args.target_ssh_ip] + params['hosts']:
        cmd = ['ssh', host, 'bash -ls']
        log.debug('Executing: %s (with %s as input)', cmd, script)
        ret = subprocess.call(cmd, stdin=open(script, 'rt'))
        log.debug('ret: %s', ret)


def _get_next_fname(parent_dir, basename_tmpl, starting_int, **other_args):
    i = starting_int
    fname = os.path.join(parent_dir, basename_tmpl.format(i=i, **other_args))
    while os.path.exists(fname):
        i += 1
        fname = os.path.join(parent_dir, basename_tmpl.format(i=i, **other_args))
    return fname


def _measure_iperf(args, out_dir, i, params):
    assert len(params['hosts']) == 1
    try:
        for proto, num_conns in [('tcp', 100), ('udp', 10)]:
            if proto == 'tcp' and not args.do_iperf_tcp: continue
            if proto == 'udp' and not args.do_iperf_udp: continue
            _start_iperf_server(args)
            _start_dstat(args, params)
            cmd = 'bash -ls {iperf} {ip} {port} {dur} {p} {udp} {fname}'.format(
                iperf=args.target_iperf_bin,
                ip=args.target_bind_ip,
                port=args.target_bind_port,
                dur=args.iperf_dur,
                p=num_conns,
                udp='n' if proto == 'tcp' else 'y',
                fname='/tmp/iperf.json.xz',
            )
            cmd = ['ssh', params['hosts'][0], cmd]
            script = 'measure-iperf.sh'
            log.debug('Executing: %s (with %s as input)', cmd, script)
            ret = subprocess.call(cmd, stdin=open(script, 'rt'))
            log.debug('ret: %s', ret)
            _stop_dstat(args, params)
            os.makedirs(out_dir, exist_ok=True)
            iperf_out_fname = _get_next_fname(out_dir, 'iperf.{p}.{i}.json.xz', i, p=proto)
            dstat_client_out_fname = _get_next_fname(out_dir, 'dstat.{h}.iperf.{p}.{i}.csv', i, h=params['hosts'][0], p=proto)
            dstat_server_out_fname = _get_next_fname(out_dir, 'dstat.{h}.iperf.{p}.{i}.csv', i, h=args.target_ssh_ip, p=proto)
            for host, rem_fname, loc_fname in [
                    (params['hosts'][0], '/tmp/iperf.json.xz', iperf_out_fname),
                    (params['hosts'][0], '/tmp/dstat.csv', dstat_client_out_fname),
                    (args.target_ssh_ip, '/tmp/dstat.csv', dstat_server_out_fname),
                    ]:
                cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
                    host=host,
                    remote_path=rem_fname,
                    local_path=loc_fname,
                ).split()
                log.debug('Executing: %s', cmd)
                ret = subprocess.call(cmd)
                log.debug('ret: %s', ret)
    finally:
        _stop_dstat(args, params)
        _stop_iperf_server(args)


def _start_iperf_server(args):
    script = 'start-iperf-server.sh'
    cmd = 'bash -ls {iperf} {ip} {port}'.format(
        iperf=args.target_iperf_bin,
        ip=args.target_bind_ip,
        port=args.target_bind_port,
    )
    cmd = ['ssh', args.target_ssh_ip, cmd]
    log.debug('Executing: %s (with %s as input)', cmd, script)
    ret = subprocess.call(cmd, stdin=open(script, 'rt'))
    log.debug('ret: %s', ret)


def _stop_iperf_server(args):
    cmd = 'ssh %s pkill iperf3' % args.target_ssh_ip
    cmd = cmd.split()
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def _stop_ph(args, params):
    procs, rets = [], []
    hosts = copy.copy(params['hosts'])
    hosts += [args.coord_ssh_ip, args.bg_host]
    if args.bg_host not in hosts:
        hosts += [args.bg_host]
    for host in hosts:
        cmd = ['ssh', host, 'pkill', 'ph']
        log.debug('Executing: %s', cmd)
        procs.append(subprocess.Popen(cmd))
    for p in procs:
        rets.append(p.wait())
    log.debug('rets: %s', rets)
    t = 3
    log.debug('Sleeping for %d seconds', t)
    time.sleep(t)
    procs, rets = [], []
    for host in [args.coord_ssh_ip, *params['hosts']]:
        cmd = ['ssh', host, 'pkill', '-9', 'tor']
        log.debug('Executing: %s', cmd)
        procs.append(subprocess.Popen(cmd))
    for p in procs:
        rets.append(p.wait())
    log.debug('rets: %s', rets)


def _start_tor(args, params):
    if params['tor_bw'] == 'unlim':
        tor_bw = 125000000
    else:
        tor_bw = max(_bw_str_to_bytes(params['tor_bw']), 76800)
    cmd = 'bash -ls {net_dir} {tor_bw}'.format(
        net_dir=args.target_tor_net_dir, tor_bw=tor_bw)
    cmd = ['ssh', args.target_ssh_ip, cmd]
    script = 'start-tor.sh'
    log.debug('Executing: %s (with %s as input)', cmd, script)
    ret = subprocess.call(cmd, stdin=open(script, 'rt'))
    log.debug('ret: %s', ret)


def _stop_tor(args):
    cmd = 'bash -ls {net_dir}'.format(net_dir=args.target_tor_net_dir)
    cmd = ['ssh', args.target_ssh_ip, cmd]
    script = 'stop-tor.sh'
    log.debug('Executing: %s (with %s as input)', cmd, script)
    ret = subprocess.call(cmd, stdin=open(script, 'rt'))
    log.debug('ret: %s', ret)


def _decompress_all(dname):
    log.error('--------------------------')
    log.error('Not safe to call decompress_all() when using _get_next_fname()')
    log.error('--------------------------')
    return
    script = './decompress-data.sh'
    cmd = [script, dname]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def main(args):
    try:
        for param_idx, params in enumerate(param_sets):
            out_dir_part = '{target}-{measurers}-{bg}-{t_bw}-{m_bw}-{mem_def}def{mem_max}max'.format(
                target=args.target_ssh_ip,
                measurers=','.join(params['hosts']),
                bg=params['bg_pcent'],
                t_bw=params['tor_bw'],
                m_bw=','.join(params['host_tor_bws']),
                mem_def=params['mem_def'],
                mem_max=params['mem_max'],
            )
            out_dir = os.path.join(args.out_dir, out_dir_part)
            #_set_sysctl(args, params)
            #_set_tc(args, params)
            # Begin measurements
            if len(params['hosts']) == 1:
                pass
                # log.debug(
                #     'Measuring ping and iperf from %s to %s',
                #     params['hosts'][0], args.target_ssh_ip)
                # _measure_ping(args, out_dir, 1, params)
                # _measure_iperf(args, out_dir, 1, params)
            for _ in range(args.ph_retries):
                sec = 5
                if not _measure_phnew(args, out_dir, 1, params):
                    log.error('Issue measuring phnew. Will try again in %d seconds' % sec)
                    time.sleep(sec)
                else:
                    break
            # End measurements
            #_unset_sysctl(args, params)
            #_unset_tc(args, params)
            # _decompress_all(out_dir)
    finally:
        #_unset_sysctl(args, params)
        #_unset_tc(args, params)
        # _decompress_all(out_dir)
        pass


if __name__ == '__main__':
    p = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)

    p.add_argument(
        '--target-iperf-bin', type=str, default='~/src/iperf3/src/iperf3')
    p.add_argument(
        '--target-tor-net-dir', type=str,
        default='~/testnets/purple-hurtz-network')
    p.add_argument(
        '--target-cache-dir', type=str, default='/run/user/1000/relay1')
    p.add_argument('--target-bind-ip', type=str, required=True)
    p.add_argument('--target-bind-port', type=int, default=10200)
    p.add_argument('--target-ssh-ip', type=str, required=True)
    p.add_argument(
        '--target-fp', type=str,
        default='859A5CE99951A3C42958AF88CE2761BD48525B16') # Tfinn3
        # default='2767A9DB46503D09FD0415BA1296B36318520F08') # TFinn1

    p.add_argument('--coord-ssh-ip', type=str, default='tityos')
    p.add_argument(
        '--coord-ph-dir', type=str, default='~/src/purple-hurtz-code')

    p.add_argument(
        '--measurer-ph-dir', type=str, default='~/src/purple-hurtz-code')

    p.add_argument('-o', '--out-dir', type=str, default=os.path.abspath('.'),
                   help='path to store results in')
    p.add_argument('--ph-retries', type=int, default=5)
    p.add_argument('--ph-password', type=str, default='password')
    p.add_argument('--ph-dur', type=int, default=30)
    p.add_argument('--iperf-dur', type=int, default=60)
    p.add_argument('--num-pings', type=int, default=60)
    p.add_argument('--do-iperf-tcp', action='store_true')
    p.add_argument('--do-iperf-udp', action='store_true')
    p.add_argument('--experiment-list', type=str, required=True)
    p.add_argument('--bg-host', type=str, default='amst.do')
    args = p.parse_args()
    args.out_dir = os.path.abspath(args.out_dir)
    # assert args.target_ssh_ip in INTERFACE_MAP
    assert os.path.isfile(args.experiment_list)
    assert args.bg_host in IP_MAP
    param_sets = [_ for _ in param_sets_from_file(args.experiment_list)]
    log.debug('Read %d params from %s', len(param_sets), args.experiment_list)
    for params in param_sets:
        assert len(params['hosts']) == len(params['host_bws'])
        assert len(params['hosts']) == len(params['host_tor_bws'])
        for host in params['hosts']:
            assert host in IP_MAP
            assert host in PHNEW_CTRL_PORT_MAP
            assert host in INTERFACE_MAP
            assert host in SYSCTL_TMPLS
            assert host in NUM_CPU_MAP
            assert host in TCP_BOMB_BW
            assert host in UDP_BOMB_BW
    main(args)
