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
        fprintf(stderr, "[" TS_FMT "] " fmt, t.tv_sec, t.tv_usec, ##__VA_ARGS__); \
    } while (0);

enum csm_state {
    csm_st_invalid = 0,
    csm_st_connected,
    csm_st_authing,
    csm_st_authed,
    csm_st_told_connect,
    csm_st_measuring,
};

struct ctrl_sock_meta {
    int fd;
    enum csm_state state;
    char *class;
    char *host;
    char *port;
    char *pw;
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
