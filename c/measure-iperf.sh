#!/usr/bin/env bash
set -eux

IPERF_BIN=$1
TARGET_IP=$2
TARGET_PORT=$3
DURATION=$4
P=$5
UDP=$6
OUT_FNAME=$7

CMD=("$IPERF_BIN" "--client" "$TARGET_IP" "--port" "$TARGET_PORT" "--time" "$DURATION" "--parallel" "$P" "--bidir" "--json" "--get-server-output")

if [[ "$UDP" == "y" ]]; then
	CMD+=("--udp" "--global-bitrate" "--bitrate" "1200M")
fi

${CMD[@]} | xz > $OUT_FNAME

#RUN_DIR=$1
#FP=$2
#NUM_M=$3
#OUT_FNAME=$4
#
#cd $RUN_DIR
## ph -c confs/controller.conf.ini controller --one -c status
#ph -c confs/controller.conf.ini controller --one \
#	-c "measure $OUT_FNAME $FP $NUM_M 1" >/dev/null </dev/null
#rm -fv ${OUT_FNAME}.xz
#xz -v $OUT_FNAME
