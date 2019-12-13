#include <assert.h>
#include <stdlib.h>
#include <glib.h>
#include "common.h"
#include "v3bw.h"
#include "rotatefd.h"

#define NUM_MSMS_IN_MSM_INFO 60
#define SECS_REQUIRED 25
#define MIN_BW 20

static int
compare_longs(const void *a, const void *b) {
    long aa = *(long *)a;
    long bb = *(long *)b;
    if (aa < bb) return -1;
    else if (aa == bb) return 0;
    return 1;
}

static long
calc_median(const long *array_in, size_t len) {
    if (len == 0) return 0; // uhhh ... I guess 0?
    if (len == 1) return array_in[0]; // let's just get this out of the way
    // make a copy of the array so we can sort it without fucking it up for them.
    long *array = malloc(len * sizeof(long));
    memcpy(array, array_in, len * sizeof(long));
    qsort(array, len, sizeof(long), compare_longs);
    long ret = array[len/2];
    free(array);
    return ret;
}

struct msm_info {
    char *fp;
    long first;
    long msms[NUM_MSMS_IN_MSM_INFO];
    size_t used;
};

static struct msm_info *
msm_info_init(const char *fp, long first, long bw) {
    // it's important that the memory is zero-initialized: the msms array needs
    // to start at zero.
    struct msm_info *msm = calloc(1, sizeof(struct msm_info));
    msm->fp = strdup(fp);
    msm->first = first;
    msm->msms[0] = bw;
    msm->used = 1;
    return msm;
}

static void
msm_info_free(struct msm_info *msm) {
    if (!msm) return;
    free(msm->fp);
    free(msm);
}

static void
msm_info_add(struct msm_info *msm, long ts, long bw) {
    assert(msm);
    if (ts < msm->first) {
        LOG("Got ts %ld which is less than first %ld. Fuck. Bailing out "
                "because I'm hoping this doesn't happen to make "
                "implementation easier.\n", ts, msm->first);
        abort();
        // got a new first. Ffffuuuu
        if (ts < msm->first - NUM_MSMS_IN_MSM_INFO) {
            // it's so much smaller that we need to throw away all existing data
        } else {
            // we can save some existing data with a memmove
        }
    } else {
        // new ts after our first one. make sure it fits in our list of msms
        assert(ts < msm->first + NUM_MSMS_IN_MSM_INFO);
        // ts is equal or larger than msm->first, so non-negative
        // ts is no more than NUM_MSMS_IN_MSM_INFO, so fits in size_t even if
        // size_t is smaller than long
        size_t offset = ts - msm->first;
        long new = msm->msms[offset] + bw;
        LOG("At t=%lu adding %ld to existing %ld to get %ld\n",
                offset, bw, msm->msms[offset], new);
        msm->msms[offset] = new;
        // if we've inserted farther into the msms array than ever before,
        // update used
        if (offset >= msm->used) {
            msm->used = offset + 1;
            assert(msm->used <= NUM_MSMS_IN_MSM_INFO);
        }
    }
}

static int
is_fp(const char *word) {
    if (!(strlen(word) == 40)) return 0;
    for (int i = 0; i < strlen(word); i++) {
        const char c = word[i];
        if (c < '0' || (c > '9' && c < 'A') || c > 'F')
            return 0;
    }
    return 1;
}

static long int
as_nonnegative_long(const char *word) {
    long i;
    char *end;
    // don't even try if word is empty
    if (word[0] == '\0') return -1;
    i = strtol(word, &end, 10);
    // only went perfectly if end points to a 0x0 byte
    if (*end != '\0') return -1;
    return i;
}

static void
trim_newlines(char *line) {
    size_t len = strlen(line);
    while (line[len-1] == '\n') {
        line[len-1] = '\0';
        len--;
    }
}

static GHashTable *
read_input_to_ht(FILE *in) {
    char *line = NULL;
    size_t cap = 0;
    ssize_t bytes_read;
    GHashTable *ht = g_hash_table_new_full(
        g_str_hash,
        g_str_equal,
        free,
        (GDestroyNotify)msm_info_free
    );
    while (1) {
        bytes_read = getline(&line, &cap, in);
        if (bytes_read < 0) {
            LOG("Didn't read any more bytes from input. Hope we're done.\n");
            //perror("Error reading line from input file");
            break;
        }
        if (!bytes_read) {
            LOG("Read empty line. Trying to loop again.\n");
            continue;
        }
        trim_newlines(line);
        gchar **words = g_strsplit(line, " ", 9);
        char *fp = NULL;;
        long ts;
        long bwdown;
        for (int i = 0; words[i] != NULL; i++) {
            const char *word = words[i];
            if  (i == 2) {
                if (!is_fp(word)) {
                    LOG("Expected fp, got '%s', so ignoring line '%s'\n", word, line);
                    break;
                }
                fp = (char *)word;
                //LOG("fp is %s\n", fp);
            } else if (i == 6) {
                if ((ts = as_nonnegative_long(word)) < 0) {
                    // We expect it to fail on BEGIN and END lines, so refrain for logging about that.
                    if (strncmp(word, "BEGIN", strlen("BEGIN")) != 0
                            && strncmp(word, "END", strlen("END")) != 0)
                        LOG("Unexpected timestamp, got '%s', so ignoring line '%s'\n", word, line);
                    break;
                }
                //LOG("ts is %ld\n", ts);
            } else if (i == 7) {
                if ((bwdown = as_nonnegative_long(word)) < 0) {
                    LOG("Unexpected bwdown, got '%s', so ignoring line '%s'\n", word, line);
                    break;
                }
                //LOG("bwdown is %ld\n", bwdown);
            }
        }
        if (fp == NULL || ts < 0 || bwdown < 0) {
            g_strfreev(words);
            continue;
        }
        LOG("Read line with fp=%s ts=%ld bwdown=%ld\n", fp, ts, bwdown);
        if (!g_hash_table_contains(ht, fp)) {
            LOG("Inserting %s into ht\n", fp);
            g_hash_table_insert(ht, strdup(fp), msm_info_init(fp, ts, bwdown));
        } else {
            struct msm_info *m = g_hash_table_lookup(ht, fp);
            assert(m);
            msm_info_add(m, ts, bwdown);
        }
        g_strfreev(words);
        //break;
    }
    free(line);
    return ht;
}

static int
_v3bw_generate(FILE *in, FILE *out) {
    GHashTableIter iter;
    gpointer k, v;
    GHashTable *ht = read_input_to_ht(in);
    if (!ht) return -1;
    fprintf(out, "%lu\n", time(NULL));
    g_hash_table_iter_init(&iter, ht);
    while (g_hash_table_iter_next(&iter, &k, &v)) {
        char *fp = (char *)k;
        struct msm_info *msm = (struct msm_info *)v;
        long med = calc_median(msm->msms, msm->used);
        if (msm->used < SECS_REQUIRED) {
            LOG("%s saw only %lus of data, so outputting min bw %d\n", fp, msm->used, MIN_BW);
            med = MIN_BW;
        }
        fprintf(out, "node_id=$%s\tbw=%ld\n", fp, med);
        LOG("%s saw %lu Mbit/s\n", fp, med * 8 / 1000 / 1000);
    }
    g_hash_table_destroy(ht);
    return 0;
}

int
v3bw_generate(const char *in_fname, const char *out_fname) {
    FILE *in_fd;
    struct rotate_fd *out_rfd;
    if (!(in_fd = fopen(in_fname, "r"))) {
        perror("Unable to open in file for v3bw generate");
        return -1;
    }
    if (!(out_rfd = rfd_open(out_fname))) {
        perror("Unable to open out file for v3bw generate");
        fclose(in_fd);
        return -2;
    }
    int ret = _v3bw_generate(in_fd, out_rfd->fd);
    fclose(in_fd);
    rfd_close(out_rfd);
    return ret;
}
