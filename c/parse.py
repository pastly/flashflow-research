#!/usr/bin/env python3
import sys


def log(*a, **kw):
    return print(*a, file=sys.stderr, **kw)


def data_iter(fd):
    for line in fd:
        words = line.split()
        if len(words) != 7:
            log('Ignoring short line: "%s"' % line)
            continue
        try:
            t = float(words[0])
        except Exception:
            log('Bad timestsamp:', words[0])
            continue
        hostport = words[2]
        if words[3] != '650':
            # first line will be 250, don't log if so
            if words[3] != '250':
                log('words[3] should be 650')
            continue
        if words[4] != 'SPEEDTESTING':
            log('words[4] should be SPEEDTESTING')
            continue
        try:
            bw_down = int(words[5])
        except Exception:
            log('Bad bw:', words[5])
            continue
        try:
            bw_up = int(words[6])
        except Exception:
            log('Bad bw:', words[6])
            continue
        yield t, hostport, bw_down, bw_up


def do(fd):
    start = None
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
        with open(fname, 'rt') as fd:
            do(fd)


if __name__ == '__main__':
    main()
