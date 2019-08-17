#!/usr/bin/env python3
import socket
import time
import sys

HOST = ''
PORT = int(sys.argv[1])


def line_iter(conn):
    buf = ''
    old_len, new_len = 0, 0
    while True:
        buf += conn.recv(8).decode('utf-8')
        new_len = len(buf)
        if new_len == old_len:
            if len(buf):
                yield buf
            break
        while '\n' in buf:
            yield buf[:buf.index('\n')]
            buf = buf[buf.index('\n')+1:]
        old_len = len(buf)


def get_authenticate(lines):
    line = next(lines)
    return line.upper().startswith('AUTHENTICATE')


def get_connect_target(lines):
    line = next(lines)
    words = line.split()
    if not words[0].upper() == 'TESTSPEED':
        print('expected testspeed connect')
        return False
    if len(words[1]) != 40:
        print('expected fingerprint, not', words[1])
        return False
    try:
        int(words[2])
    except Exception:
        print(words[2], 'does not seem to be a number of conns')
        return False
    return True


def get_set_bw(lines):
    line = next(lines)
    print(line)
    return True


def get_start_measurement(lines):
    line = next(lines)
    words = line.split()
    if not words[0].upper() == 'TESTSPEED':
        print('expected testspeed start')
        return False
    try:
        int(words[1])
    except Exception:
        print(words[1], 'does not seem to be a duration')
        return False
    return int(words[1])


def output_iter(lines):
    if not get_authenticate(lines):
        print('failed to auth')
        return
    print('did auth')
    yield '250 OK\n'
    if not get_connect_target(lines):
        print('failed to get connect command')
        return
    print('did connect cmd')
    yield '250 SPEEDTESTING\n'
    if not get_set_bw(lines):
        print('failed to get set bw command')
        return
    yield '250 OK\n'
    dur = get_start_measurement(lines)
    if not dur:
        print('failed to get measurement start')
        return
    print('did measure cmd')
    counter = 0
    for _ in range(dur):
        counter += 1
        yield '650 SPEEDTESTING %d %d\n' % (counter, counter*2)
        time.sleep(1)
    print('all good, all done')


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        while True:
            conn, addr = s.accept()
            print('conn from', addr)
            with conn:
                lines = line_iter(conn)
                for out_line in output_iter(lines):
                    conn.sendall(out_line.encode('utf-8'))
                print('done with conn from', addr)


if __name__ == '__main__':
    exit(main())
