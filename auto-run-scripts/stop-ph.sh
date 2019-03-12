#!/usr/bin/env bash
set -eu

HOSTNAME=$1

echo "Stopping all ph processes"
ssh $HOSTNAME "
	pkill ph
	" || echo "Error stopping ph processes"
