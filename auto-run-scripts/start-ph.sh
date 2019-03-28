#!/usr/bin/env bash
set -eu

HOSTNAME=$1
HOSTNAME_TOR=$2
RUN_DNAME=$3
NUM_MEASURERS=1

echo "Starting coordinator"
ssh $HOSTNAME "
	cd $RUN_DNAME
	mkdir -pv ph-tor-coord
	chmod 700 ph-tor-coord
	cp -v /mnt/scratch/$HOSTNAME_TOR/mtraudt/run/tornet/main/relay1/cached-* ph-tor-coord/
	nohup ~/.pyenv/shims/ph -c ph-conf/confs/coordinator.config.ini coordinator >coord.stdout.txt 2>coord.stderr.txt </dev/null &
	" || echo "Error starting ph coordinator"

sleep 5

echo "Starting measurers"
for A in $(seq 1 $NUM_MEASURERS); do
echo -n "$A "
ssh $HOSTNAME "
	cd $RUN_DNAME
	mkdir -pv ph-tor-${A}
	chmod 700 ph-tor-${A}
	cp -v /mnt/scratch/$HOSTNAME_TOR/mtraudt/run/tornet/main/relay1/cached-* ph-tor-${A}/
	nohup ~/.pyenv/shims/ph -c ph-conf/confs/measurer_foo${A}.conf.ini measurer \
		>measurer_foo${A}.stdout.txt \
		2>measurer_foo${A}.stderr.txt \
		</dev/null &
	" || echo "Error starting ph measurers"
done

sleep 5
