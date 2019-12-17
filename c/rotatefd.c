#include <string.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <libgen.h>
#include <errno.h>
#include "rotatefd.h"

/* wrapper around libgen.h's basename because it's stupid. hur dur maybe we
 * modify the given path char *, but maybe we don't. hur dur maybe the returned
 * char * is within the given char *, but maybe it isn't.
 *
 * This will not touch the given char *path. The returned char * will be its
 * own buffer on the heap that you must free. Easy. Simple.
 */
static char *
my_basename(const char *path) {
    // so we don't clobber the  user's path
    char *copy = strdup(path);
    // ret_1 may be in static memory or to somewhere within char *copy. So it's
    // never correct to free it.
    char *ret_1 = basename(copy);
    // Now let's make a copy in the heap for the user
    char *ret_2 = strdup(ret_1);
    // free the copy of the full path that we got from the user (this might
    // fuck up ret_1, but it's fine because we got what we need in ret_2)
    free(copy);
    // and finally give the user ret_2. SO EASY
    return ret_2;
}

static struct rotate_fd*
rfd_init(const char *fname_req, const char *fname, FILE *fd) {
    struct rotate_fd *rfd = malloc(sizeof(struct rotate_fd));
    rfd->fname_req = strdup(fname_req);
    rfd->fname = strdup(fname);
    rfd->fd = fd;
    return rfd;
}

static void
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
                LOG("Unable to open file in rfd_open: %s\n", strerror(errno));
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
    // there's a few file names in play here. let's clear some things up.
    //
    // * rfd->fname_req is the original fname the user requested.
    //   e.g. path/to/some/file.txt
    // * rfd->fname is the filename we actually used.
    //   e.g. path/to/some.file.txt.1
    // * target_basename is the basename of fname_req. The symlink points to
    //   the target actual file using its basename because
    //   - they're in the same dir, so it's fine
    //   - if the path given originally isn't absolute, we can't use the
    //     relative path (easily)
    if (!rfd) return;
    char *target_basename = my_basename(rfd->fname); // must free
    if (rfd->fd >= 0) {
        // not going to be atomic, sorry
        if (unlink(rfd->fname_req) < 0) {
            LOG("Unable to unlink old rotate_fd symlink: %s\n", strerror(errno));
            // but continue on anyway and hope for the best
        }
        if (symlink(target_basename, rfd->fname_req) < 0) {
            LOG("Unable to create new rotate_fd symlink: %s\n", strerror(errno));
            // whelp. shit's fucked yo. keeeep going
        }
    }
    if (fclose(rfd->fd) < 0) {
        LOG("Trouble closing rotate_fd fd: %s\n", strerror(errno));
    }
    rfd_free(rfd);
    free(target_basename);
    return;
}
