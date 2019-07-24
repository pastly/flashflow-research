#!/usr/bin/env python3
import sys
tmpl = 'flashflow-torrc.tmpl'
out_fname_tmpl = 'flashflow-torrc-%d'
first_ctrl_port = 9000
num_torrcs = int(sys.argv[1])


def gen_torrc(i):
    assert i > 0
    with open(tmpl, 'rt') as fd:
        text = fd.read()
        text = text.format(
            i=i,
            ctrl_port=first_ctrl_port+i-1,
        )
        return text


def main():
    for i in range(1, num_torrcs+1):
        with open(out_fname_tmpl % i, 'wt') as fd:
            fd.write(gen_torrc(i))

if __name__ == '__main__':
    main()
