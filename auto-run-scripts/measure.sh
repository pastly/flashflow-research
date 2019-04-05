#!/usr/bin/env bash
set -eu

if (( "$#" != "5" ))
then
	echo "$0 <host> <rep_num> <bwlim> <workdir> <outdir>"
	echo "$0 koios3 4          100M    foo       control/10Mbps/10m"
	echo ""
	echo "workdir contains ph-conf, which contains confs/ and keys/"
	echo "outdir is where to write results"
	exit 1
fi

set -v

export HOSTNAME=$1
export REP_NUM=$2
export BWLIM=$3
export WORK_DIR=$4
export OUT_DIR=$5

IPERF_FNAME=$OUT_DIR/iperf3.${REP_NUM}.json
PH_FNAME=$OUT_DIR/ph.${REP_NUM}.dat

ssh $HOSTNAME "
	cd $WORK_DIR
	mkdir -pv $OUT_DIR

	~/.pyenv/shims/ph -c ph-conf/confs/controller.config.ini controller --one -c \"measure $PH_FNAME 3D197F0006B11811AA8363A17C34182CF11E91A9 1 1\"
	xz -fzv $PH_FNAME
	sleep 10

	#PATH='.local/bin:$PATH' iperf3 -c koios2 -p 10002 -t 120 --bitrate $BWLIM --global-bitrate -P 1 --bidir --json > $IPERF_FNAME
	#xz -fzv $IPERF_FNAME
	#sleep 3
"
