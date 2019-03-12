#!/usr/bin/env bash
set -eu

HOSTNAME=$1
TOR_NET_DIR=$2
#TOR_DIR=/scratch/mtraudt/tor-networks/simple
ssh $HOSTNAME "
	cd $TOR_NET_DIR
	./04-stop-network.sh
	" || echo "Error stopping tor network"
echo ''
