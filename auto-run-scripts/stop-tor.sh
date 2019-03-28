#!/usr/bin/env bash
set -eu

HOSTNAME_MAIN=$1
TOR_NET_DIR=$2
ssh $HOSTNAME_MAIN "
	cd $TOR_NET_DIR/tornet/main
	cat */tor.pid | xargs kill
	" || echo "Error stopping tor network (main)"

echo 'Done stopping main tor network'

#ssh $HOSTNAME_EXTRA "
#	cd $TOR_NET_DIR/tornet/extra
#	cat */tor.pid | xargs kill
#	cd $TOR_NET_DIR/tornet/clients
#	cat */tor.pid | xargs kill
#	" || echo "Error stopping tor network (extra)"
#
#echo 'Done stopping extra and client'

sleep 3
