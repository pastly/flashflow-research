.PHONY: all clean

GCC_FLAGS := -Wall -O2 -ggdb
GCC := gcc

all: toy

clean:
	rm -fv toy

toy: toy.c
	$(GCC) $(GCC_FLAGS) $^ -o $@
