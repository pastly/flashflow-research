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
orig = copy.deepcopy(param_sets)
param_sets = []
for params in orig:
    for bw in ['750Mbps', '500Mbps', 'unlim', '250Mbps']:
        for hostset in chain(
                combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 4),
                combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 3),
                combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 2),
                combinations(['nrl', 'ddns', 'india.do', 'amst.do'], 1)):
            if len(hostset) != 2:
                continue
            if bw != '250Mbps':
                continue
            # measurer-limited
            new = copy.deepcopy(params)
            new['hosts'] = list(hostset)
            new['host_bws'] = ['unlim'] * len(hostset)
            new['host_tor_bws'] = [bw] * len(hostset)
            new['tor_bw'] = 'unlim'
            param_sets.append(new)
            # target-limited
            # if bw == 'unlim': continue
            # new = copy.deepcopy(params)
            # new['hosts'] = list(hostset)
            # new['host_bws'] = ['unlim'] * len(hostset)
            # new['host_tor_bws'] = ['unlim'] * len(hostset)
            # new['tor_bw'] = bw
            # param_sets.append(new)

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
    num = int(bw_str[:-4])
    tail = bw_str[-4:]
    assert tail in ('Mbps', 'Gbps')
    if tail == 'Mbps':
        return int(num * 1000 * 1000 / 8)
    return int(num * 1000 * 1000 * 1000 / 8)


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
    out_fname = os.path.join(out_dir, 'ping.%d.txt' % i)
    with open(out_fname, 'wt') as fd:
        fd.write('#\n# %s\n#\n' % str(datetime.datetime.now()))
    log.debug('Executing: %s (with %s getting output)', cmd, out_fname)
    ret = subprocess.call(cmd, stdout=open(out_fname, 'at'))
    log.debug('ret: %s', ret)


def _start_bwevents(args):
    script = 'start-bwevents.sh'
    cmd = 'bash -ls {net_dir} {fname}'.format(
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
    for host, bw_lim in zip(params['hosts'], params['host_tor_bws']):
        n_mproc = NUM_CPU_MAP[host]
        if bw_lim == 'unlim':
            bw_lim = 125000000
        else:
            # close enough to even distribution of bw lim across cores
            bw_lim = _bw_str_to_bytes(bw_lim)
            bw_lim = (bw_lim // n_mproc) + 1
        cmd = 'bash -ls {d} {tor_host} {tor_cache_dir} {bw} {n_mproc}'.format(
            d=args.measurer_ph_dir,
            tor_host=args.target_ssh_ip,
            tor_cache_dir=args.target_cache_dir,
            bw=bw_lim,
            n_mproc=n_mproc,
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


def _stop_phnew_tor_clients(args, params):
    return _stop_ph(args, params)


def _measure_phnew(args, out_dir, i, params):
    try:
        _start_tor(args, params)
        _start_phnew_tor_clients(args, params)
        _start_bwevents(args)
        _start_dstat(args, params)
        os.makedirs(out_dir, exist_ok=True)
        hostports = []
        total_num_socks = 160
        socks_per_host_iter = _split_x_by_y(total_num_socks, len(params['hosts']))
        for host in params['hosts']:
            num_socks_this_host = next(socks_per_host_iter)
            num_cpu = NUM_CPU_MAP[host]
            socks_per_cpu_iter = _split_x_by_y(num_socks_this_host, num_cpu)
            for i in range(num_cpu):
                hostports.append(IP_MAP[host])
                hostports.append(PHNEW_CTRL_PORT_MAP[host]+i)
                hostports.append(next(socks_per_cpu_iter))
        cmd = 'bash -ls {d} {fname} {fp} {hp_pairs}'.format(
            d=args.coord_ph_dir,
            fname='/tmp/phnew.test.txt.xz',
            fp=args.target_fp,
            hp_pairs=' '.join('%s' % hp for hp in hostports),
        )
        script = 'measure-ph.sh'
        cmd = ['ssh', args.coord_ssh_ip, cmd]
        log.debug('Executing: %s (with %s as input)', cmd, script)
        ret = subprocess.call(cmd, stdin=open(script, 'rt'))
        log.debug('ret: %s', ret)
        _stop_dstat(args, params)
        _stop_bwevents(args)
        out_fname = os.path.join(out_dir, 'bwevents.%s.ph.%d.log' % (args.target_ssh_ip, i))
        cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
            host=args.target_ssh_ip,
            remote_path='/tmp/bwevents.log',
            local_path=out_fname,
        ).split()
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)
        out_fname = os.path.join(out_dir, 'ph.%d.txt.xz' % i)
        cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
            host=args.coord_ssh_ip,
            remote_path='/tmp/phnew.test.txt.xz',
            local_path=out_fname,
        ).split()
        log.debug('Executing: %s', cmd)
        ret = subprocess.call(cmd)
        log.debug('ret: %s', ret)
        for host in [args.target_ssh_ip] + params['hosts']:
            out_fname = os.path.join(out_dir, 'dstat.%s.ph.%d.csv' % (host, i))
            cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
                host=host,
                remote_path='/tmp/dstat.csv',
                local_path=out_fname,
            ).split()
            log.debug('Executing: %s', cmd)
            ret = subprocess.call(cmd)
            log.debug('ret: %s', ret)
    finally:
        _stop_dstat(args, params)
        _stop_bwevents(args)
        _stop_phnew_tor_clients(args, params)
        _stop_tor(args)


#  def _measure_ph(args, out_dir, i, params):
#      try:
#          _start_tor(args, params)
#          _start_ph_coord(args, params)
#          _start_ph_measurer(args, params)
#          _start_bwevents(args)
#          _start_dstat(args, params)
#          os.makedirs(out_dir, exist_ok=True)
#          script = 'measure-ph.sh'
#          cmd = 'bash -ls {d} {fname} {fp} {num_mproc} {num_c_per_mpc}'.format(
#              d=args.coord_ph_dir,
#              fname='/media/f6b6/x76slv/test.dat',
#              fp=args.target_fp,
#              num_mproc=sum(NUM_CPU_MAP[h] for h in params['hosts']),
#              num_c_per_mpc=params['num_c_overall'],
#              #num_c_per_mpc=params['num_c_overall'] // len(params['hosts']),
#          )
#          cmd = ['ssh', args.coord_ssh_ip, cmd]
#          log.debug('Executing: %s (with %s as input)', cmd, script)
#          ret = subprocess.call(cmd, stdin=open(script, 'rt'))
#          log.debug('ret: %s', ret)
#          _stop_dstat(args, params)
#          _stop_bwevents(args)
#          out_fname = os.path.join(out_dir, 'ph.%d.dat.xz' % i)
#          cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
#              host=args.coord_ssh_ip,
#              remote_path='/media/f6b6/x76slv/test.dat.xz',
#              local_path=out_fname,
#          ).split()
#          log.debug('Executing: %s', cmd)
#          ret = subprocess.call(cmd)
#          log.debug('ret: %s', ret)
#          out_fname = os.path.join(out_dir, 'bwevents.%s.ph.%d.log' % (args.target_ssh_ip, i))
#          cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
#              host=args.target_ssh_ip,
#              remote_path='/tmp/bwevents.log',
#              local_path=out_fname,
#          ).split()
#          log.debug('Executing: %s', cmd)
#          ret = subprocess.call(cmd)
#          log.debug('ret: %s', ret)
#          for host in [args.target_ssh_ip] + params['hosts']:
#              out_fname = os.path.join(out_dir, 'dstat.%s.ph.%d.csv' % (host, i))
#              cmd = 'rsync -air {host}:{remote_path} {local_path}'.format(
#                  host=host,
#                  remote_path='/tmp/dstat.csv',
#                  local_path=out_fname,
#              ).split()
#              log.debug('Executing: %s', cmd)
#              ret = subprocess.call(cmd)
#              log.debug('ret: %s', ret)
#      finally:
#          _stop_dstat(args, params)
#          _stop_bwevents(args)
#          _stop_ph(args, params)
#          _stop_tor(args)


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


# def _start_ph_coord(args, params):
#     script = 'start-ph-coord.sh'
#     cmd = 'bash -ls {d} {tor_host} {tor_cache_dir}'.format(
#         d=args.coord_ph_dir,
#         tor_host=args.target_ssh_ip,
#         tor_cache_dir=args.target_cache_dir,
#     )
#     cmd = ['ssh', args.coord_ssh_ip, cmd]
#     log.debug('Executing: %s (with %s as input)', cmd, script)
#     ret = subprocess.call(cmd, stdin=open(script, 'rt'))
#     log.debug('ret: %s', ret)
#     t = 10
#     log.debug('Sleeping for %d seconds', t)
#     time.sleep(t)


# def _start_ph_measurer(args, params):
#     script = 'start-ph-measurer.sh'
#     wait_time = 0
#     procs = []
#     for host, bw_lim in zip(params['hosts'], params['host_tor_bws']):
#         num_m = NUM_CPU_MAP[host]
#         wait_time += num_m / 4
#         if bw_lim == 'unlim':
#             bw_lim = 125000000
#             # if unlimited, might as well give all procs a ton instead of
#             # "just" a a ton dividied by the number of cores
#             bw_lim = iter([bw_lim] * num_m)
#         else:
#             bw_lim = _bw_str_to_bytes(bw_lim)
#             # split the bw limit up evenly across the cpus
#             bw_lim = _split_x_by_y(bw_lim, num_m)
#         cmd = 'bash -ls {d} {tor_host} {tor_cache_dir} {n} {bw_lim}'.format(
#             d=args.measurer_ph_dir,
#             tor_host=args.target_ssh_ip,
#             tor_cache_dir=args.target_cache_dir,
#             n=num_m,
#             bw_lim=next(bw_lim),
#         )
#         cmd = ['ssh', host, cmd]
#         log.debug('Executing: %s (with %s as input)', cmd, script)
#         procs.append(
#             subprocess.Popen(cmd, stdin=open(script, 'rt')))
#     rets = []
#     for p in procs:
#         rets.append(p.wait())
#     log.debug('rets: %s', rets)
#     if wait_time > 1:
#         log.debug('Sleeping an extra %0.2fs to let measurers connect', wait_time)
#         time.sleep(wait_time)


def _stop_ph(args, params):
    procs, rets = [], []
    for host in [args.coord_ssh_ip, *params['hosts']]:
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
        tor_bw = _bw_str_to_bytes(params['tor_bw'])
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
    script = './decompress-data.sh'
    cmd = [script, dname]
    log.debug('Executing: %s', cmd)
    ret = subprocess.call(cmd)
    log.debug('ret: %s', ret)


def main(args):
    try:
        for param_idx, params in enumerate(param_sets):
            out_dir_part = '{target}-{measurers}-{s}s-{t_bw}-{m_bw}-{mem_def}def{mem_max}max'.format(
                target=args.target_ssh_ip,
                measurers=','.join(params['hosts']),
                s=params['num_c_overall'],
                t_bw=params['tor_bw'],
                m_bw=','.join(params['host_tor_bws']),
                mem_def=params['mem_def'],
                mem_max=params['mem_max'],
            )
            out_dir = os.path.join(args.out_dir, out_dir_part)
            #_set_sysctl(args, params)
            #_set_tc(args, params)
            # Begin measurements
            # if len(params['hosts']) == 1:
            #     log.debug(
            #         'Measuring ping and iperf from %s to %s',
            #         params['hosts'][0], args.target_ssh_ip)
            #     _measure_ping(args, out_dir, 1, params)
            #     _measure_iperf(args, out_dir, 1, params)
            _measure_phnew(args, out_dir, 1, params)
            # End measurements
            #_unset_sysctl(args, params)
            #_unset_tc(args, params)
            _decompress_all(out_dir)
            break
    finally:
        #_unset_sysctl(args, params)
        #_unset_tc(args, params)
        _decompress_all(out_dir)
        pass

#for p in param_sets:
#    n_socks = []
#    for host in p['hosts']:
#        others = [h for h in p['hosts'] if h != host]
#        n_socks.append(_num_socks_for_host(host, others, p['num_c_overall']))
#    if sum(n_socks) != 160:
#        print(p['hosts'], sum(n_socks), n_socks)
#exit(0)


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
        default='65622D2CEB1746755988FBC2068F04DCD34AE7A8')

    p.add_argument('--coord-ssh-ip', type=str, default='tityos')
    p.add_argument(
        '--coord-ph-dir', type=str, default='~/src/purple-hurtz-code')

    p.add_argument(
        '--measurer-ph-dir', type=str, default='~/src/purple-hurtz-code')

    p.add_argument('-o', '--out-dir', type=str, default=os.path.abspath('.'),
                   help='path to store results in')
    p.add_argument('--iperf-dur', type=int, default=60)
    p.add_argument('--num-pings', type=int, default=60)
    p.add_argument('--do-iperf-tcp', action='store_true')
    p.add_argument('--do-iperf-udp', action='store_true')
    args = p.parse_args()
    args.out_dir = os.path.abspath(args.out_dir)
    assert args.target_ssh_ip in INTERFACE_MAP
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
