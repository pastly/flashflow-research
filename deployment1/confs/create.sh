#!/usr/bin/env bash

for A in $(seq 1 10); do
	echo measurer$A
	sed "s|NUM|$A|g" measurer_foo.tmpl > measurer_foo$A.conf.ini
done
cp -v coordinator.tmpl coordinator.conf.ini
