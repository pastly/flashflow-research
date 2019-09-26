.PHONY: all clean

PLATFORM := $(shell uname)

CC := gcc


CFLAGS := $(CFLAGS) -Wall -pipe -ggdb -O0 -DPIC -fPIC -std=gnu99 \
	-U_FORTIFY_SOURCE -fno-inline -fno-strict-aliasing \
	-fno-omit-frame-pointer
# CFLAGS commented out because macOS (clang) warns that they are unused/unknown
# -Wl,--no-as-needed -rdynamic

LDFLAGS := -lpthread -ldl

RS_SRC := sched/src/*.rs
RS_LIB := sched/target/debug/libsched.a

ifeq ($(PLATFORM),Darwin)
all: flashflow
else
all: libflashflow.so flashflow
endif

OBJ := flashflow.o torclient.o common.o

flashflow: sched.h $(OBJ) $(RS_LIB)
	$(CC) -o $@ $(CFLAGS) $(OBJ) $(RS_LIB) $(LDFLAGS) -lm

libflashflow.so: sched.h $(OBJ) $(RS_LIB)
	$(CC) -o $@ $(CFLAGS) -shared $(OBJ) $(RS_LIB) $(LDFLAGS)

$(RS_LIB): $(RS_SRC) sched/Cargo.*
	cd sched && cargo build

sched.h: $(RS_SRC) sched/Cargo.*
	cd sched && cbindgen --lang C --crate sched --output ../$@

%.o: %.c
	$(CC) $(CFLAGS) -o $@ -c $<

clean:
	rm -rfv flashflow *.o *.d *.dSYM sched.h sched/target/*/libsched.*
	cd sched && cargo clean
