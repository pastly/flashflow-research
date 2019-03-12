#!/usr/bin/env bash
set -eu

HOSTNAME=$1

echo "Stopping ph echo server"
ssh $HOSTNAME "pkill python3" || echo "Error stopping ph echo server"
echo "Stopping iperf server"
ssh $HOSTNAME "pkill iperf3" || echo "Error stopping iperf server"
