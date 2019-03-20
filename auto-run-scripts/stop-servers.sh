#!/usr/bin/env bash
set -eu

HOSTNAME_MAIN=$1
HOSTNAME_EXTRA=$2

echo "Stopping iperf server"
ssh $HOSTNAME_MAIN "pkill iperf3" || echo "Error stopping iperf server"

echo "Stopping nginx server"
ssh $HOSTNAME_EXTRA "pkill nginx" || echo "Error stopping nginx server"
