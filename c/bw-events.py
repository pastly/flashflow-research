#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
import time
import sys

from stem.control import Controller


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


def get_controller(args):
    if not args.ctrl_port and not args.ctrl_socket:
        exit(1)
    c = None
    if args.ctrl_port:
        c = Controller.from_port(port=args.ctrl_port)
    elif args.ctrl_socket:
        c = Controller.from_socket_file(path=args.ctrl_socket)
    c.authenticate()
    assert c.is_authenticated()
    return c


def set_relay_bandwidth(c, rbr):
    if rbr is None:
        return
    eprint('Setting RBR and RBB to', str(rbr))
    c.set_options({
        'RelayBandwidthRate': str(rbr),
        'RelayBandwidthBurst': str(rbr),
    })


def set_relay_split_sched(c, sspb):
    if sspb is None:
        return
    eprint('Setting SSPB to', str(sspb))
    c.set_options({
        'SplitScheduler': '1',
        'SplitSchedulerPercentBackground': str(sspb),
    })

def main(args):
    cont = get_controller(args)
    set_relay_bandwidth(cont, args.relay_bandwidth_rate)
    set_relay_split_sched(cont, args.percent_background)
    cont.add_event_listener(lambda ev: print('%0.4f' % time.time(), ev, flush=True), 'BW', 'CONN_BW')
    while True: time.sleep(100)


if __name__ == '__main__':
    parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter,
        description='Connect to a Tor client and log CONN_BW events')
    parser.add_argument(
        '-s', '--ctrl-socket', type=str, help='Path to a Tor ControlSocket. If '
        'both this and --ctrl-port are given, this wins')
    parser.add_argument(
        '-p', '--ctrl-port', type=str, help='A Tor ControlPort')
    parser.add_argument(
        '--relay-bandwidth-rate', type=int,
        help='If given, set Tor\'s RBR to this. Will not clear when '
        'disconnecting. Specify in bytes/second.')
    parser.add_argument(
        '--percent-background', type=int,
        help='If given, set Tor\'s SplitSchedulerPercentBackground '
        'option to this. Will not clear when disconnecting. '
        '"30" is 30%%')
    args = parser.parse_args()
    assert args.ctrl_socket or args.ctrl_port
    try:
        main(args)
    except KeyboardInterrupt:
        print()
