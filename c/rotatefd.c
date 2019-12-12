#include <string.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include "rotatefd.h"

static
struct rotate_fd*
rfd_init(const char *fname_req, const char *fname, FILE *fd) {
    struct rotate_fd *rfd = malloc(sizeof(struct rotate_fd));
    rfd->fname_req = strdup(fname_req);
    rfd->fname = strdup(fname);
    rfd->fd = fd;
    return rfd;
}

static
void
rfd_free(struct rotate_fd *rfd) {
    if (!rfd) return;
    if (fileno(rfd->fd) >= 0)
        LOG("Warning: freeing rotate_fd with seemingly open fd %d\n", fileno(rfd->fd));
    free(rfd->fname_req);
    free(rfd->fname);
    free(rfd);
    return;
}

struct rotate_fd*
rfd_open(const char *fname_in) {
    // 5 extra: 1 for \0, 1 for '.', and 3 for ints up to 999
    // exåmple fname_in = /path/to/file.txt
    // could need to store /path/to/file.txt.123 in fname_buf
    const size_t len = strlen(fname_in) + 5;
    char *fname_buf = malloc(len);
    unsigned next = 0;
    FILE *fd;
    struct rotate_fd *rfd;
    do {
        assert(snprintf(fname_buf, len, "%s.%u", fname_in, next) > 0);
        if (access(fname_buf, F_OK) < 0) {
            //LOG("Will open %s for %s\n", fname_buf, fname_in);
            if (!(fd = fopen(fname_buf, "w"))) {
                perror("Unable to open file in rfd_open");
            }
            rfd = rfd_init(fname_in, fname_buf, fd);
            free(fname_buf);
            return rfd;
        }
    } while (++next < 1000);
    LOG("Unable to open %s because too many exist already\n", fname_in);
    free(fname_buf);
    return NULL;
}

void
rfd_close(struct rotate_fd *rfd) {
    if (!rfd) return;
    if (rfd->fd >= 0) {
        // not going to be atomic, sorry
        if (unlink(rfd->fname_req) < 0) {
            perror("Unable to unlink old rotate_fd symlink");
            // but continue on anyway and hope for the best
        }
        if (symlink(rfd->fname, rfd->fname_req) < 0) {
            perror("Unable to create new rotate_fd symlink");
            // whelp. shit's fucked yo. keeeep going
        }
    }
    if (fclose(rfd->fd) < 0) {
        perror("Trouble closing rotate_fd fd");
    }
    rfd_free(rfd);
    return;
}
