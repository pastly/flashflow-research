#ifndef FF_COMMON_H
#define FF_COMMON_H

#include <sys/time.h>

#define READ_BUF_LEN 1024*8

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

struct ctrl_sock_meta {
    int fd;
    const char *class;
    const char *host;
    const char *port;
    const char *pw;
    int nconns;
    int current_measurement;
};

struct msm_params {
    unsigned id;
    const char *fp;
    unsigned dur;
};

#endif /* !defined(FF_COMMON_H) */
