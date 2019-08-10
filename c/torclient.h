#ifndef FF_CLIENTFILE_H
#define FF_CLIENTFILE_H
#include "common.h"
#define MAX_NUM_CTRL_SOCKS 128
int tc_client_file_read(const char *fname, struct ctrl_sock_meta metas[]);
int tc_make_sockets(const unsigned num_metas, struct ctrl_sock_meta metas[]);
int tc_auth_socket(struct ctrl_sock_meta *meta);
int tc_set_bw_rates(const int num_metas, const struct ctrl_sock_meta metas[], const unsigned bws[]);
int tc_next_available(const int num_metas, struct ctrl_sock_meta metas[], const char *class);
#endif /* !defined(FF_CLIENTFILE_H) */
