#!/usr/bin/env bash
set -eu

if (( "$#" != "4" ))
then
	echo "$0 <host> <dev> <latency_ms> <packet_loss>"
	echo "$0 koios2 p2p1  12           \"0.0001%\""
	exit 1
fi
HOSTNAME=$1
DEV=$2
LATENCY_MS=$3
PACKET_LOSS=$4

COMMAND_LATENCY_AND_PACKETLOSS="dev $DEV root handle 1:0 netem delay ${LATENCY_MS}ms loss $PACKET_LOSS"
echo "Enabling tc changes"
ssh $HOSTNAME "
	sudo tc qdisc add $COMMAND_LATENCY_AND_PACKETLOSS
	sudo tc -p qdisc ls dev $DEV
"

# if (( "$#" != "7" ))
# then
# 	echo "$0 <host> <dev> <latency_ms> <tb_rate> <tb_size> <tb_q_limit> <packet_loss>"
# 	echo "$0 koios2 p2p1  12           10mbit    4mbit     4mbit        \"0.0001%\""
# 	exit 1
# fi
# 
# HOSTNAME=$1
# DEV=$2
# LATENCY_MS=$3
# TB_RATE=$4
# TB_BUCKET_SIZE=$5
# TB_QUEUE_LIMIT=$6
# PACKET_LOSS=$7
# 
# COMMAND_LATENCY_AND_PACKETLOSS="dev $DEV root handle 1:0 netem delay ${LATENCY_MS}ms loss $PACKET_LOSS"
# COMMAND_RATELIMIT="dev $DEV parent 1:1 handle 10: tbf rate $TB_RATE buffer $TB_BUCKET_SIZE limit $TB_QUEUE_LIMIT"
# 
# function enableStuff {
# 	echo "Enabling changes"
# 	ssh $HOSTNAME "
# 		sudo tc qdisc add $COMMAND_LATENCY_AND_PACKETLOSS
# 		sudo tc qdisc add $COMMAND_RATELIMIT
# 		sudo tc -p qdisc ls dev $DEV
# 		"
# }
# 
# enableStuff
