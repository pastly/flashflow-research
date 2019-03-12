#!/usr/bin/env bash
set -eu

HOSTNAME=$1
CODE_DNAME=$2
VENV_DNAME=${CODE_DNAME}/venv-pypy-editable/bin/activate
IPERF_PORT=10002

echo "-- NOT -- starting ph echo server. Assuming Tor network is running on "\
	"$HOSTNAME"
#echo "Starting ph echo server"
#ssh $HOSTNAME "
#	cd $CODE_DNAME
#	source $VENV_DNAME
#	nohup ./echo_server.py &>/dev/null </dev/null &
#	" || echo "Error starting ph echo server"

echo "Starting iperf server"
ssh $HOSTNAME "
	PATH='.local/bin:$PATH' nohup iperf3 -sp $IPERF_PORT &>/dev/null </dev/null &
	" || echo "Error starting iperf server"
