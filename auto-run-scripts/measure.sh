#!/usr/bin/env bash
set -eu

if (( "$#" != "5" ))
then
	echo "$0 <rtt_ms> <link_bw> <num_measurers> <num_conns_per_measurer> <outdir>"
	echo "$0 300      100Mbps   2               1                        control"
	exit 1
fi

set -v

export RTT=$1
export BW=$2
export NUM_MEASURERS=$3
export CONNS_PER_MEASURER=$4
export OUT_DIR=$5
DNAME=${OUT_DIR}/${BW}/${NUM_MEASURERS}measurers${CONNS_PER_MEASURER}conns
IPERF_FNAME=$DNAME/iperf3-${RTT}ms.json
PH_FNAME=$DNAME/ph-${RTT}ms.dat

mkdir -pv $DNAME
ph -c labdeployment/confs/controller.config.ini controller --one -c "measure $PH_FNAME koios2:10001 ${NUM_MEASURERS} ${CONNS_PER_MEASURER}"
xz -fzv $PH_FNAME
#sleep 5
#iperf3 -c koios2 -p 10002 -t 120 -P $((NUM_MEASURERS*CONNS_PER_MEASURER)) --bidir --json > $IPERF_FNAME
#xz -fzv $IPERF_FNAME
