.PHONY: all clean

GCC_FLAGS := -Wall -O2 -ggdb

all: toy

clean:
	rm -fv toy

toy: toy.c
	gcc $(GCC_FLAGS) $^ -o $@
