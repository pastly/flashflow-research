#!/usr/bin/env bash
set -eu

HOSTNAME_MAIN=$1
HOSTNAME_EXTRA=$2
IPERF_PORT=10002

echo "Starting iperf server"
ssh $HOSTNAME_MAIN "
	PATH='.local/bin:$PATH' nohup iperf3 --global-bitrate -sp $IPERF_PORT &>/dev/null </dev/null &
" || echo "Error starting iperf server"

ssh $HOSTNAME_EXTRA "
	nohup /run/tmp/nginx/sbin/nginx </dev/null &>/dev/null &
" || echo "Error starting nginx"
