#ifndef FF_COMMON_H
#define FF_COMMON_H

#include <sys/time.h>

#define READ_BUF_LEN 1024*8
#define MBITS_TO_BYTES 1000*1000/8

#ifdef __APPLE__
#define TS_FMT "%ld.%06d"
#else
#define TS_FMT "%ld.%06ld"
#endif
#define LOG(fmt, ...) \
    do { \
        struct timeval t; \
        gettimeofday(&t, NULL); \
        fprintf(stderr, "[" TS_FMT "] [%s@%s:%d] " fmt, t.tv_sec, t.tv_usec, __func__, __FILE__, __LINE__, ##__VA_ARGS__); \
    } while (0);

enum csm_state {
    csm_st_invalid = 0,
    csm_st_connected,
    csm_st_authing,
    csm_st_authed,
    csm_st_told_connect_target,
    csm_st_connected_target,
    csm_st_setting_bw,
    csm_st_bw_set,
    csm_st_measuring,
    csm_st_done,
};

struct ctrl_sock_meta {
    int fd;
    enum csm_state state;
    char *class;
    char *host;
    char *port;
    char *pw;
    int is_bg;
    unsigned current_m_id;
};

struct msm_params {
    unsigned id;
    const char *fp;
    unsigned dur;
    unsigned num_m;
    char **m;
    unsigned *m_bw;
    unsigned *m_nconn;
};

const char *csm_st_str(const enum csm_state s);
void free_ctrl_sock_meta(struct ctrl_sock_meta m);

#endif /* !defined(FF_COMMON_H) */
