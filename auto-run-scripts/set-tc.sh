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
PACKET_LOSS="0.0%"

TB_RATE=10mbit
TB_BUCKET_SIZE=4mbit
TB_QUEUE_LIMIT=4mbit

COMMAND_LATENCY_AND_PACKETLOSS="dev $DEV root handle 1:0 netem delay ${LATENCY_MS}ms loss $PACKET_LOSS"
COMMAND_RATELIMIT="dev $DEV parent 1:1 handle 10: tbf rate $TB_RATE buffer $TB_BUCKET_SIZE limit $TB_QUEUE_LIMIT"

echo "Enabling tc changes"
ssh $HOSTNAME "
	sudo tc qdisc add $COMMAND_LATENCY_AND_PACKETLOSS
	sudo tc qdisc add $COMMAND_RATELIMIT
	sudo tc -p qdisc ls dev $DEV
"
