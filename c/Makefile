.PHONY: all clean

PLATFORM := $(shell uname)

#CFLAGS := -Wall -O2 -ggdb -std=gnu99 -fPIC
CC := gcc


CFLAGS := $(CFLAGS) -Wall -pipe -ggdb -O2 -DPIC -fPIC -std=gnu99 -rdynamic \
	-U_FORTIFY_SOURCE -fno-inline -fno-strict-aliasing \
	-Wl,--no-as-needed -fno-omit-frame-pointer
LDFLAGS := -lpthread -ldl

RS_SRC := sched/src/*.rs
RS_LIB := sched/target/debug/libsched.a

all: libflashflow.so flashflow

flashflow: sched.h flashflow.o torclient.o common.o $(RS_LIB)
	$(CC) -o $@ $(CFLAGS) $^ $(LDFLAGS) -lm

libflashflow.so: sched.h flashflow.o torclient.o common.o $(RS_LIB)
	$(CC) -o $@ $(CFLAGS) -shared $^ $(LDFLAGS)

$(RS_LIB): $(RS_SRC) sched/Cargo.*
	cd sched && cargo build

sched.h: $(RS_SRC) sched/Cargo.*
	cd sched && cbindgen --lang C --crate sched --output ../$@

%.o: %.c
	$(CC) $(CFLAGS) -o $@ -c $<

clean:
	rm -fv flashflow *.o sched/target/*/libsched.*

#.PHONY: all clean
#
#PLATFORM := $(shell uname)
#
##CFLAGS := -Wall -O2 -ggdb -std=gnu99 -fPIC
#CC := gcc
#
#
#CFLAGS := $(CFLAGS) -Wall -pipe -ggdb -O2 -DPIC -fPIC -std=gnu99 -rdynamic \
#	-U_FORTIFY_SOURCE -fno-inline -fno-strict-aliasing \
#	-Wl,--no-as-needed -fno-omit-frame-pointer
#LDFLAGS := -lpthread -ldl
#
#RS_SRC := sched/src/*.rs \
#RS_LIB := sched/target/debug/libsched.so
#
#all: flashflow
#
#flashflow: flashflow.o torclient.o common.o sched/target/debug/libsched.a
#	$(CC) -o $@ $(CFLAGS) -pie -fPIE $^ $(LDFLAGS)
#
#sched/target/debug/libsched.a: sched/src/*.rs sched/Cargo.*
#	cd sched && cargo build
#
#%.o: %.c
#	$(CC) $(CFLAGS) -o $@ -c $<
#
#clean:
#	rm -fv flashflow *.o sched/target/*/libsched.*
