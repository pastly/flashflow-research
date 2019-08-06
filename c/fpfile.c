#include <sys/errno.h>

#include "common.h"
#include "fpfile.h"

FILE *
fp_file_open(const char *fname) {
    return fopen(fname, "r");
}

/**
 * Read the next fingerprint from the fp_file and return it. NULL if error or
 * EOF. Caller must free the returned string when finished with it.
 */
char *
fp_file_next(FILE *fd) {
    char *line = NULL;
    size_t cap = 0;
    ssize_t bytes_read;
    while (1) {
        bytes_read = getline(&line, &cap, fd);
        if (bytes_read < 0) {
            if (errno) {
                perror("Error getting next line from fp file");
            }
            return NULL;
        }
        // ignore empty lines and comments
        if (!bytes_read || line[0] == '#')
            continue;
        // ignore lines that probably aren't fingerprints
        if ((line[bytes_read-1] == '\n' && bytes_read != 41) || (line[bytes_read-1] != '\n' && bytes_read == 40)) {
            LOG("Ignoring line that doesn't look like fingerprint: \"%s\"\n", line);
            continue;
        }
        // replace newline with null
        if (line[bytes_read-1] == '\n')
            line[bytes_read-1] = '\0';
        return line;
    }
}

int
fp_file_close(FILE *f) {
    return fclose(f);
}
