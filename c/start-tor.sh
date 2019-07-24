#!/usr/bin/env bash
set -eux

TOR_NET_DIR=$1
BW_LIM_BYTES=$2

cd $TOR_NET_DIR/tornet/main
nohup ./02-start-network.sh $BW_LIM_BYTES </dev/null &>"02-start-network.sh.log"
sleep 5
which python3
./03-network-in-ready-state.py --debug --size 10 auth1/ relay1/
echo 'Done starting main tor network'
