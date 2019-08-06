#include <sys/errno.h>
#include <string.h>
#include <stdlib.h>

#include "common.h"
#include "fpfile.h"

FILE *
fp_file_open(const char *fname) {
    return fopen(fname, "r");
}

/**
 * Read the next valid line from fp_file and fill params with it. Returns false
 * if error or ran out of lines, otherwise true.
 */
int
fp_file_next(FILE *fd, struct msm_params *params) {
    char *head, *line = NULL;
    size_t cap = 0;
    ssize_t bytes_read;
    while (1) {
        bytes_read = getline(&line, &cap, fd);
        char *line_copy = strdup(line);
        head = line;
        if (bytes_read < 0) {
            if (errno) {
                perror("Error getting next line from fp file");
            }
            return 0;
        }
        // ignore empty lines and comments
        if (!bytes_read || head[0] == '#')
            goto single_loop_end;
        char *id_str = strsep(&head, " \n");
        if (!id_str || !strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *fp = strsep(&head, " \n");
        if (!fp || !strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *dur_str = strsep(&head, "\n");
        if (!dur_str || strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        params->id = atoi(id_str);
        params->fp = fp;
        params->dur = atoi(dur_str);
        LOG("id=%u fp=%s dur=%u\n", params->id, params->fp, params->dur);
        free(line_copy);
        return 1;
single_loop_end:
        free(line_copy);
    }
}

int
fp_file_close(FILE *f) {
    return fclose(f);
}
