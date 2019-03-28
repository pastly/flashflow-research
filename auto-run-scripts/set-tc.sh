#!/usr/bin/env bash
set -eu

if (( "$#" != "3" ))
then
	echo "$0 <host> <dev> <latency_ms>"
	echo "$0 koios2 p2p1  12          "
	exit 1
fi
HOSTNAME=$1
DEV=$2
LATENCY_MS=$3

COMMAND_LATENCY="dev $DEV root handle 1:0 netem delay ${LATENCY_MS}ms"
echo "Enabling tc changes"
ssh $HOSTNAME "
	sudo tc qdisc add $COMMAND_LATENCY
	sudo tc -p qdisc ls dev $DEV
"
