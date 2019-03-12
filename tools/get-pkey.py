#!/usr/bin/env python3
from nacl.public import PublicKey, PrivateKey
import base64
import sys


def get_skey(fname):
    with open(fname, 'rb') as fd:
        return PrivateKey(fd.read())

def main():
    for fname in sys.argv[1:]:
        skey = get_skey(fname)
        pkey_text = base64.b64encode(bytes(skey.public_key))
        # remove leading b' and trailing '
        pkey_text = str(pkey_text)[2:-1]
        print(pkey_text)

if __name__ == '__main__':
    main()
