#include<stdio.h>
#include<stdlib.h>
#include <sys/errno.h>
#include <string.h>

#include "common.h"
#include "clientfile.h"

int
client_file_read(const char *fname, struct ctrl_sock_meta metas[]) {
    FILE *fd = fopen(fname, "r");
    if (!fd) {
        perror("Error opening client file");
        return -1;
    }
    char *line = NULL;
    size_t cap = 0;
    ssize_t bytes_read;
    int count = 0;
    while (count < MAX_NUM_CTRL_SOCKS) {
        bytes_read = getline(&line, &cap, fd);
        char *line_copy = strdup(line);
        if (bytes_read < 0) {
            if (errno) {
                perror("Error getting line from client file");
            }
            return count;
        }
        if (!bytes_read || line[0] == '#')
            goto single_loop_end;
        char *host = strsep(&line, " ");
        if (!host || !strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *port = strsep(&line, " ");
        if (!port || !strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *pw = strsep(&line, " \n");
        if (!pw || strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        LOG("read client config host='%s' port='%s' pw='%s'\n", host, port, pw);
        metas[count].fd = -1;
        metas[count].host = host;
        metas[count].port = port;
        metas[count].pw = pw;
        metas[count].nconns = 1;
        count++;
single_loop_end:
        free(line_copy);
    }
    return count;
}