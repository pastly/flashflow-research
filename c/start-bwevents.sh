#!/usr/bin/env bash
set -eux

TOR_NET_DIR=$1
OUT_FNAME=$2

(ps aux | grep -v grep | grep python | grep bw-events | awk '{print $2}' | xargs kill) || true

cd $TOR_NET_DIR/tornet/main
rm -fv $OUT_FNAME
nohup ./bw-events.py -s relay1/control_socket > $OUT_FNAME 2>/dev/null </dev/null &

sleep 1
