.PHONY: all clean

GCC_FLAGS := -Wall -O2 -ggdb
GCC := gcc

all: flashflow

clean:
	rm -fv flashflow

flashflow: flashflow.c
	$(GCC) $(GCC_FLAGS) $^ -o $@
