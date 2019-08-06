.PHONY: all clean

CFLAGS := -Wall -O2 -ggdb
CC := gcc

SRC := \
	flashflow.c \
	fpfile.c \
	torclient.c \
	common.c \

OBJ := \
	fpfile.o \
	torclient.o \
	common.o \

all: flashflow

include $(SRC:.c=.d)

%.d: %.c
	set -e; rm -f $@; \
	$(CC) -MM $(CPPFLAGS) $< > $@.$$$$; \
	sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' < $@.$$$$ > $@; \
	rm -f $@.$$$$

clean:
	rm -rf flashflow *.d *.o *.dSYM

flashflow: flashflow.c $(OBJ)
	$(CC) $(CFLAGS) $^ -o $@
