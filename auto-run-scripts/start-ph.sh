#!/usr/bin/env bash
set -eu

HOSTNAME=$1
CODE_DNAME=$2
#VENV_DNAME=${CODE_DNAME}/venv-pypy-editable/bin/activate
VENV_DNAME=$HOME/.pyenv/versions/purple-hurtz-pypy3.5/bin/activate
NUM_MEASURERS=10

echo "Starting coordinator"
ssh $HOSTNAME "
	cd $CODE_DNAME
	source $VENV_DNAME
	nohup ph -c labdeployment/confs/coordinator.config.ini coordinator >/tmp/coord.stdout.txt 2>/tmp/coord.stderr.txt </dev/null &
	" || echo "Error starting ph coordinator"

sleep 3

echo "Starting measurers"
for A in $(seq 1 $NUM_MEASURERS); do
echo -n "$A "
ssh $HOSTNAME "
	cd $CODE_DNAME
	source $VENV_DNAME
	nohup ph -c labdeployment/confs/measurer_foo${A}.conf.ini measurer \
		>/tmp/measurer_foo${A}.stdout.txt \
		2>/tmp/measurer_foo${A}.stderr.txt \
		</dev/null &
	" || echo "Error starting ph measurers"
done
echo ''
