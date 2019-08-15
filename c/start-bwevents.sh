#!/usr/bin/env bash
set -eux

BW_RATE=$1
BG_PERCENT=$2
OUT_FNAME=$3

(ps aux | grep -v grep | grep python | grep bw-events | awk '{print $2}' | xargs kill) || true

# cd $TOR_NET_DIR/tornet/main
cd ~/run
rm -fv $OUT_FNAME
nohup ./bw-events.py \
    --percent-background $BG_PERCENT \
    --relay-bandwidth-rate $BW_RATE \
    -s tfinn3/control 2>bw-events.stderr.txt > $OUT_FNAME </dev/null &

sleep 1
