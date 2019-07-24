#!/usr/bin/env bash
set -eux

TOR_NET_DIR=$1

cd $TOR_NET_DIR/tornet/main
cat */tor.pid | xargs kill
echo 'Done stopping main tor network'
