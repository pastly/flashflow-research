#!/usr/bin/env bash
set -eu

HOSTNAME=$1
CODE_DNAME=$2
NUM_MEASURERS=10

echo "Starting coordinator"
ssh $HOSTNAME "
	cd $CODE_DNAME
	mkdir -pv /run/tmp/ph-tor-coord
	cp /run/tmp/relayextra1/cached-* /run/tmp/ph-tor-coord/
	nohup ~/.pyenv/shims/ph -c labdeployment/confs/coordinator.config.ini coordinator >/tmp/coord.stdout.txt 2>/tmp/coord.stderr.txt </dev/null &
	" || echo "Error starting ph coordinator"

sleep 5

echo "Starting measurers"
for A in $(seq 1 $NUM_MEASURERS); do
echo -n "$A "
ssh $HOSTNAME "
	cd $CODE_DNAME
	mkdir -pv /run/tmp/ph-tor-${A}
	cp /run/tmp/relayextra1/cached-* /run/tmp/ph-tor-${A}/
	nohup ~/.pyenv/shims/ph -c labdeployment/confs/measurer_foo${A}.conf.ini measurer \
		>/tmp/measurer_foo${A}.stdout.txt \
		2>/tmp/measurer_foo${A}.stderr.txt \
		</dev/null &
	" || echo "Error starting ph measurers"
done

sleep 5
