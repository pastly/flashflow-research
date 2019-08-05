#ifndef FF_CLIENTFILE_H
#define FF_CLIENTFILE_H
#include "common.h"
#define MAX_NUM_CTRL_SOCKS 64
int client_file_read(const char *fname, struct ctrl_sock_meta metas[]);
#endif /* !defined(FF_CLIENTFILE_H) */