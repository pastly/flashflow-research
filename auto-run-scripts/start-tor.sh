#!/usr/bin/env bash
set -eu
HOSTNAME_MAIN=$1
TOR_NET_DIR=$2
BW_LIM_BYTES=$3

ssh $HOSTNAME_MAIN "
	# rm -rfv /run/tmp/{auth,relay,client,exit}*
	cd $TOR_NET_DIR/tornet/main
	nohup ./02-start-network.sh $BW_LIM_BYTES </dev/null &>/dev/null &
	sleep 5
	./03-network-in-ready-state.py --debug --size 10 auth1/ relay1/
	" || echo "Error starting tor network (main)"

echo 'Done starting main tor network'

#ssh $HOSTNAME_EXTRA "
#	# rm -rfv /run/tmp/{auth,relay,client,exit}*
#	cd $TOR_NET_DIR/tornet/extra
#	nohup ./02-start-network.sh </dev/null &>/dev/null &
#	cd $TOR_NET_DIR/tornet/clients
#	nohup ./02-start-tors.sh </dev/null &>/dev/null &
#	sleep 2
#	./network-in-ready-state.py -s 100 -t 120 client103*
#	" || echo "Error starting tor network (extra)"
#
#echo 'Done starting extra and client'
