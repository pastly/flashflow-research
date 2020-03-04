#ifndef FF_ROTATEFD_H
#define FF_ROTATEFD_H
#include "common.h"
struct rotate_fd {
	char *fname_req;
	char *fname;
	FILE *fd;
};
struct rotate_fd *rfd_open(const char *fname_in);
void rfd_close(struct rotate_fd *rfd);
#endif /* !defined(FF_ROTATEFD_H) */
