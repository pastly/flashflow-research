#!/usr/bin/env bash
set -eux

D=$1
FNAME=$2
FP=$3
DURATION=$4
PASSWORD=$5
HOSTS=$6
HOST_BWS=$7
HOST_SOCKS=$8
HOST_IPS=$9
HOST_PORTS=${10}
shift; shift; shift; shift; shift;
shift; shift; shift; shift; shift;

FP_FILE=.fps.txt
CLIENT_FILE=.clients.txt

cd $D/c
rm -fv $FNAME $FP_FILE $CLIENT_FILE

IFS=',' read -r -a HOSTS_ARRAY <<< "$HOSTS"
IFS=',' read -r -a HOST_IPS_ARRAY <<< "$HOST_IPS"
IFS=',' read -r -a HOST_PORTS_ARRAY <<< "$HOST_PORTS"
for I in "${!HOSTS_ARRAY[@]}"; do
    echo ${HOSTS_ARRAY[I]} ${HOST_IPS_ARRAY[I]} ${HOST_PORTS_ARRAY[I]} $PASSWORD >> $CLIENT_FILE
done

echo "1 $FP $DURATION $HOSTS $HOST_BWS $HOST_SOCKS 0" > $FP_FILE


date
./flashflow $FP_FILE $CLIENT_FILE | xz -T 2 > $FNAME
RET="${PIPESTATUS[0]}"
echo flashflow returned $RET
if [[ "$RET" != "0" ]]; then
    exit $RET    
fi
date
