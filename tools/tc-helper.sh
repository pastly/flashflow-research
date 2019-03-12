#!/usr/bin/env bash
set -eu
#set -x

# Webpages used to figure this shit out
# https://linux.die.net/man/8/tc
# https://linux.die.net/man/8/tc-tbf
# https://wiki.linuxfoundation.org/networking/netem

if (( "$#" != "5" ))
then
	echo "$0 <dev> <latency_ms> <tb_rate> <tb_size_and_limit> <packet_loss>"
	echo "$0 p2p1  12           10mbit    4mbit               \"0.0001%\""
	exit 1
fi

DEV=$1
LATENCY_MS=$2
TB_RATE=$3
TB_BUCKET_SIZE=$4
TB_QUEUE_LIMIT=$4
PACKET_LOSS=$5

COMMAND_LATENCY_AND_PACKETLOSS="dev $DEV root handle 1:0 netem delay ${LATENCY_MS}ms loss $PACKET_LOSS"
COMMAND_RATELIMIT="dev $DEV parent 1:1 handle 10: tbf rate $TB_RATE buffer $TB_BUCKET_SIZE limit $TB_QUEUE_LIMIT"

function disableStuff {
	echo "Disabling changes"
	sudo tc qdisc del dev $DEV root
}
trap disableStuff EXIT

function enableStuff {
	echo "Enabling changes"
	sudo tc qdisc add $COMMAND_LATENCY_AND_PACKETLOSS
	sudo tc qdisc add $COMMAND_RATELIMIT
}

enableStuff
tc -p qdisc ls dev $DEV
read -p "Press enter to disable changes ..." FOO
