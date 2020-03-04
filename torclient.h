#ifndef FF_CLIENTFILE_H
#define FF_CLIENTFILE_H
#include "common.h"
#define MAX_NUM_CTRL_SOCKS 4096
int tc_client_file_read(const char *fname, struct ctrl_sock_meta metas[]);
int tc_auth_socket(struct ctrl_sock_meta *meta);
int tc_authed_socket(struct ctrl_sock_meta *meta);
int tc_tell_connect(struct ctrl_sock_meta *meta, const char *fp, const unsigned conns);
int tc_connected_socket(struct ctrl_sock_meta *meta);
int tc_set_bw_rate(struct ctrl_sock_meta *meta, const unsigned bw);
int tc_did_set_bw_rate(struct ctrl_sock_meta *meta);
int tc_start_measurement(struct ctrl_sock_meta *meta, const unsigned dur);
int tc_output_result(struct ctrl_sock_meta *meta, const unsigned m_id, const char *fp, FILE *out_fd);
int tc_next_available(const int num_metas, struct ctrl_sock_meta metas[], const char *class);
int tc_finished_with_meta(struct ctrl_sock_meta *meta);
void tc_mark_failed(struct ctrl_sock_meta *meta);
void tc_assert_state_(const struct ctrl_sock_meta *meta, const enum csm_state state, const char *func, const char *file, const int line);
#define tc_assert_state(m, s) tc_assert_state_((m), (s), __func__, __FILE__, __LINE__)
#endif /* !defined(FF_CLIENTFILE_H) */
