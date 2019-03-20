#!/usr/bin/env bash
set -eu

if (( "$#" != "6" ))
then
	echo "$0 <host> <rep_times> <num_measurers> <num_conns_per_measurer> <bwlim> <outdir>"
	echo "$0 koios3 10          2               1                        100M     control/10Mbps/10m"
	exit 1
fi

set -v

export HOSTNAME=$1
export REP_TIMES=$2
export NUM_MEASURERS=$3
export CONNS_PER_MEASURER=$4
export BWLIM=$5
export OUT_DIR=$6

for REP in $(seq 1 $REP_TIMES); do
	IPERF_FNAME=$OUT_DIR/iperf3.${REP}.json
	PH_FNAME=$OUT_DIR/ph.${REP}.dat

	ssh $HOSTNAME "
		mkdir -pv $OUT_DIR

		#~/.pyenv/shims/ph -c ~/src/purple-hurtz-code/labdeployment/confs/controller.config.ini controller --one -c \"measure $PH_FNAME 17E02F26EA746FA14FFC1B570959904C16339825 ${NUM_MEASURERS} ${CONNS_PER_MEASURER}\"
		#xz -fzv $PH_FNAME
		#sleep 10

		PATH='.local/bin:$PATH' iperf3 -c koios2 -p 10002 -t 120 --bitrate $BWLIM --global-bitrate -P $((NUM_MEASURERS*CONNS_PER_MEASURER)) --bidir --json > $IPERF_FNAME
		xz -fzv $IPERF_FNAME
		sleep 3
	"
done
