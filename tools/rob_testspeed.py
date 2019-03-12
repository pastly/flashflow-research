#!/usr/bin/env python3
from stem.control import Controller
import sys
import time

CIRCS_PER_CLIENT = 1


def usage():
    s = 'Give fingerprint of target, duration in seconds, and one or more '\
        'paths to Tor client control sockets.\n'\
        '%s TARGET_FP DURATION CLIENT_CTRL_SOCKET ...' % sys.argv[0]
    print(s)


def connect(path):
    c = Controller.from_socket_file(path)
    c.authenticate()
    assert c.is_authenticated()
    return c


def main(fp, duration, paths):
    ctrls = [connect(p) for p in paths]
    print('All connected')
    t = duration
    for i, c in enumerate(ctrls):
        statuses = []
        for _ in range(CIRCS_PER_CLIENT):
            cmd = 'TESTSPEED %s' % fp
            ret = str(c.msg(cmd))
            assert ret.strip().split()[0] == 'SPEEDTESTING'
            cmd = 'TESTSPEED %d' % duration
            ret = str(c.msg(cmd))
            statuses.append(ret)
        print('%d/%d for %d:' % (i+1, len(ctrls), t), ','.join(statuses))
        #  t -= 10
        # time.sleep(10)
    print('Sleeping %ds until we assume the last one is done ...' % t)
    time.sleep(t)
    print('The last one should be done.')
    return


if __name__ == '__main__':
    if len(sys.argv) < 4:
        usage()
        exit(1)
    fp = sys.argv[1]
    duration = int(sys.argv[2])
    paths = sys.argv[3:]
    if len(fp) != 40:
        print('%s is not a valid relay fingerprint' % fp)
        exit(1)
    if not len(paths):
        print('Must supply 1 or more paths to tor control ports')
        exit(1)
    exit(main(fp, duration, paths))
