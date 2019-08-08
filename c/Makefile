.PHONY: all clean

PLATFORM := $(shell uname)

CFLAGS := -Wall -O2 -ggdb -std=gnu99
CC := gcc

RS_SRC := \
	sched/src/*.rs \

ifeq ($(PLATFORM),Darwin)
RS_LIB := \
	sched/target/release/libsched.dylib
else
RS_LIB := \
	sched/target/release/libsched.so
endif

SRC := \
	torclient.c \
	common.c \
	#flashflow.c \

OBJ := \
	torclient.o \
	common.o \

all: flashflow

include $(SRC:.c=.d)

sched.h: sched/src/*.rs
	cd sched && \
	cbindgen --lang C --crate sched --output ../$@ || \
	rustc -Z parse-only ../$^

%.d: %.c
	set -e; rm -f $@; \
	$(CC) -MM $(CPPFLAGS) $< > $@.$$$$; \
	sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' < $@.$$$$ > $@; \
	rm -f $@.$$$$

clean:
	rm -rf flashflow *.d *.d.* *.o *.dSYM sched.h $(RS_LIB)

$(RS_LIB): $(RS_SRC)
	cd sched && \
	cargo build --release

flashflow: flashflow.c $(OBJ) sched.h $(RS_LIB)
	$(CC) $(CFLAGS) flashflow.c $(OBJ) -o $@ -lsched -L./sched/target/release
