#!/usr/bin/env python3
import sys
from subprocess import Popen, PIPE


def log(*a, **kw):
    return print(*a, file=sys.stderr, **kw)


def data_iter(fd):
    for line in fd:
        line = line.strip()
        words = line.split()
        if len(words) != 9:
            log('Ignoring short/long line: "%s"' % line)
            continue
        try:
            t = float(words[6])
        except Exception:
            log('Bad timestsamp:', words[0])
            continue
        hostport = words[3].split(';')[1]
        if words[4] != '650':
            # first line will be 250, don't log if so
            if words[4] != '250':
                log('words[4] should be 650')
            continue
        if words[5] != 'SPEEDTESTING':
            log('words[5] should be SPEEDTESTING')
            continue
        try:
            bw_down = int(words[7])
        except Exception:
            log('Bad bw:', words[7])
            continue
        try:
            bw_up = int(words[8])
        except Exception:
            log('Bad bw:', words[8])
            continue
        yield t, hostport, bw_down, bw_up


def do(fd):
    out_data = {}
    for t, _, bw_down, bw_up in data_iter(fd):
        if int(t) not in out_data:
            out_data[int(t)] = []
        out_data[int(t)].append({'d': bw_down, 'u': bw_up})
    for t in sorted(out_data):
        down = sum(item['d'] for item in out_data[t])
        up = sum(item['u'] for item in out_data[t])
        print(t, down, up)


def main():
    for fname in sys.argv[1:]:
        if fname.endswith('.xz'):
            fd = Popen(['xzcat', fname], stdout=PIPE, universal_newlines=True).stdout
        else:
            fd = open(fname, 'rt')
        do(fd)


if __name__ == '__main__':
    main()
