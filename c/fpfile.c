#include <sys/errno.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>

#include "common.h"
#include "fpfile.h"

static char **
fp_file_fill_m(const char *s, unsigned *count) {
    char *token, *head, *tofree;
    tofree = head = strdup(s);
    *count = 0;
    char **out = NULL;
    while ((token = strsep(&head, ","))) {
        if (!strlen(token))
            continue;
        out = realloc(out, (++*count) * sizeof(char *));
        out[*count-1] = strdup(token);
    }
    free(tofree);
    return out;
}

static unsigned *
fp_file_fill_m_bw(const char *s, unsigned expected_count) {
    char *token, *head, *tofree;
    unsigned count = 0;
    tofree = head = strdup(s);
    unsigned *out = NULL;
    while ((token = strsep(&head, ","))) {
        if (!strlen(token))
            continue;
        out = realloc(out, (++count) * sizeof(unsigned *));
        out[count-1] = atoi(token) * MBITS_TO_BYTES;
    }
    free(tofree);
    assert(count == expected_count);
    return out;
}

static unsigned *
fp_file_fill_m_nconn(const char *s, unsigned expected_count) {
    char *token, *head, *tofree;
    unsigned count = 0;
    tofree = head = strdup(s);
    unsigned *out = NULL;
    while ((token = strsep(&head, ","))) {
        if (!strlen(token))
            continue;
        out = realloc(out, (++count) * sizeof(unsigned *));
        out[count-1] = atoi(token);
    }
    free(tofree);
    assert(count == expected_count);
    return out;
}

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
        char *dur_str = strsep(&head, " \n");
        if (!dur_str || !strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *m_str = strsep(&head, " \n");
        if (!m_str || !strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *m_bw_str = strsep(&head, " \n");
        if (!m_bw_str || !strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *m_nconn_str = strsep(&head, "\n");
        if (!m_nconn_str || strlen(head)) {
            LOG("Ignoring invalid fp line '%s'\n", line_copy);
            goto single_loop_end;
        }
        params->id = atoi(id_str);
        params->fp = fp;
        params->dur = atoi(dur_str);
        params->m = fp_file_fill_m(m_str, &params->num_m);
        params->m_bw = fp_file_fill_m_bw(m_bw_str, params->num_m);
        params->m_nconn = fp_file_fill_m_nconn(m_nconn_str, params->num_m);
        LOG("id=%u fp=%s dur=%u m=%s m_bw=%s (Mbps) m_nconn=%s\n",
            params->id, params->fp, params->dur, m_str,
            m_bw_str, m_nconn_str);
        //for (int i =0; i < params->num_m; i++) {
        //    LOG("    %s %u\n", params->m[i], params->m_bw[i]);
        //}
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
