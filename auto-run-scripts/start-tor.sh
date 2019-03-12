#!/usr/bin/env bash
set -eu
HOSTNAME=$1
TOR_NET_DIR=$2
#TOR_DIR=/scratch/mtraudt/tor-networks/simple
ssh $HOSTNAME "
	export PATH=$HOME/.local/bin:$PATH
	cd $TOR_NET_DIR
	./02-start-network.sh
	sleep 3
	time ./03-network-in-ready-state.py auth* relay*
	" || echo "Error starting tor network"
echo ''
