#include <stdio.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#include <assert.h>

#include "common.h"
#include "torclient.h"
#include "sched.h"

#define MBITS_TO_BYTES 1000*1000/8

void
usage() {
    const char *s = \
    "arguments: <fingerprint_file> <client_file>\n"
    "\n"
    "fingerprint_file    place from which to read fingerprints to measure, one per line\n"
    "client_file         place from which to read tor client info, one per line, 'host port ctrl_port_pw'\n";
    LOG("%s", s);
}

/*
 * calls select() on the given socket, waiting for read. Returns negative if
 * error, 0 if timeout occurs, and 1 if readable before timeout.
 */
int
wait_till_readable(const int s, const struct timeval timeout) {
    struct timeval timeout_remaining = timeout;
    int result;
    fd_set set;
    FD_ZERO(&set);
    FD_SET(s, &set);
    result = select(s+1, &set, NULL, NULL, &timeout_remaining);
    if (result < 0) {
        perror("error on select() waiting for readable");
        return result;
    } else if (result == 0) {
        return 0;
    }
    return FD_ISSET(s, &set) ? 1 : 0;
}

/*
 * tell tor via the given socket to connect to the target relay by the given
 * fingerprint with the given number of conns.
 * returns false if error, otherwise true
 */
int
connect_target(const int s, const  char *fp, const unsigned num_conns) {
    char buf[READ_BUF_LEN];
    const char *good_resp = "250 SPEEDTESTING";
    const int buf_size = 1024;
    char msg[buf_size];
    int len;
    int wait_result;
    struct timeval read_timeout = {.tv_sec = 10, .tv_usec = 0};
    if (snprintf(msg, buf_size, "TESTSPEED %s %d\n", fp, num_conns) < 0) {
        LOG("Error making msg in connect_taget()\n");
        return 0;
    }
    if (send(s, msg, strlen(msg), 0) < 0) {
        perror("Error sending connect_taget() message");
        return 0;
    }
    wait_result = wait_till_readable(s, read_timeout);
    if (wait_result < 0) {
        return 0;
    } else if (wait_result == 0) {
        LOG("Timed out waiting for %d to be readable\n", s);
        return 0;
    }
    if ((len = recv(s, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error reading response to connect_target() message");
        return 0;
    }
    if (strncmp(buf, good_resp, strlen(good_resp))) {
        buf[len] = '\0';
        LOG("Unknown connect_target() response: %s\n", buf);
        return 0;
    }
    LOG("fd=%d connected to %s with %u conns\n", s, fp, num_conns);
    return 1;
}

/*
 * tell tor the duration of the measurement, which should start it.
 * returns false if error, otherwise true
 */
int
start_measurement(const int s, const unsigned dur) {
    const int buf_size = 1024;
    char msg[buf_size];
    if (snprintf(msg, buf_size, "TESTSPEED %d\n", dur) < 0) {
        LOG("Error making msg in start_measurement()\n");
        return 0;
    }
    if (send(s, msg, strlen(msg), 0) < 0) {
        perror("Error sending start_measurement() message");
        return 0;
    }
    return 1;
}

/* read at most max_len bytes from socket s into buf, and store the time this
 * is done in t. returns negative value if error, returns 0 if no bytes read,
 * otherwise returns number of bytes read.
 */
int
read_response(const int s, char *buf, const size_t max_len, struct timeval *t) {
    int len;
    if ((len = recv(s, buf, max_len, 0)) < 0) {
        perror("Error reading responses");
        return -1;
    }
    if (!len) {
        return 0;
    }
    if (gettimeofday(t, NULL) < 0) {
        perror("Error getting the time");
        return -1;
    }
    //buf[len] = '\0';
    return len;
}

/*
 * provide an array of ctrl_socks and its length. provide a relay fingerprint
 * and the number of connections each tor client should open to it. instruct
 * each tor client to connect to this relay (but not start measuring). returns
 * false if any failure, otherwise true.
 */
int
connect_target_all(const int num_ctrl_socks, const struct ctrl_sock_meta ctrl_sock_metas[], const unsigned m_nconn[], const char *fp) {
    int i;
    for (i = 0; i < num_ctrl_socks; i++) {
        int fd = ctrl_sock_metas[i].fd;
        if (!connect_target(fd, fp, m_nconn[i])) {
            return 0;
        }
    }
    return 1;
}

/*
 * provide an array of ctrl_socks and its length. provide a measurement
 * duration, in seconds. tell each tor client to measure for that long. return
 * false if any falure, otherwise true
 */
int
start_measurements(const int num_ctrl_socks, const struct ctrl_sock_meta ctrl_sock_metas[], const unsigned duration) {
    int i;
    for (i = 0; i < num_ctrl_socks; i++) {
        if (!(start_measurement(ctrl_sock_metas[i].fd, duration))) {
            return 0;
        }
    }
    return 1;
}

int
max_ctrl_sock(const struct ctrl_sock_meta array[], const int array_len) {
    int the_max = INT_MIN;
    int i;
    for (i = 0; i < array_len; i++) {
        the_max = array[i].fd > the_max ? array[i].fd : the_max;
    }
    return the_max;
}

int
find_and_connect_metas(unsigned m_id, struct ctrl_sock_meta metas[], const int num_metas) {
    struct msm_params p;
    p.id = m_id;
    p.fp = sched_get_fp(p.id);
    p.dur = sched_get_dur(p.id);
    p.num_m = sched_get_hosts(p.id, &p.m, &p.m_bw, &p.m_nconn);
    if (!p.fp) {
        LOG("Should have gotten a relay fp\n");
        return 0;
    }
    if (!p.dur) {
        LOG("Should have gotten a duration\n");
        return 0;
    }
    if (!p.num_m) {
        LOG("Should have gotten a set of hosts\n");
        return 0;
    }
    LOG("About to look for hosts with the following classes. Will eventually tell them the bw and nconn.\n")
    for (int i = 0; i < p.num_m; i++) {
        LOG("    class=%s bw=%u nconn=%u\n", p.m[i], p.m_bw[i], p.m_nconn[i]);
    }
    int next_meta;
    for (int i = 0; i < p.num_m; i++) {
        const char *class = p.m[i];
        if ((next_meta = tc_next_available(num_metas, metas, class)) < 0) {
            LOG("Unable to find available meta with class %s\n", class);
            return 0;
        }
        metas[next_meta].current_m_id = m_id;
    }
    return 1;
}

int send_auth_metas(unsigned m_id, struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id != m_id)
            continue;
        assert(metas[i].state == csm_st_connected);
        tc_auth_socket(&metas[i]);
    }
    return 1;
}

int new_main(int argc, const char *argv[]) {
    struct ctrl_sock_meta metas[MAX_NUM_CTRL_SOCKS];
    int authing_fds[MAX_NUM_CTRL_SOCKS];
    if (argc != 3) {
        //LOG("argc=%d\n", argc);
        usage();
        return -1;
    }
    const char *fp_fname = argv[1];
    const char *client_fname = argv[2];
    // number of tor clients read from file
    int num_tor_clients;
    if ((num_tor_clients = tc_client_file_read(client_fname, metas)) < 1) {
        LOG("Error reading %s or it was empty\n", client_fname);
        return -1;
    }
    LOG("We know about the following Tor clients. They may not exist, haven't checked.\n");
    for (int i = 0; i < num_tor_clients; i++) {
        LOG("    %s at %s:%s\n", metas[i].class, metas[i].host, metas[i].port);
    }
    if (!sched_new(fp_fname)) {
        LOG("Empty sched from %s or error\n", fp_fname);
        return -1;
    }
    // Main loop
    while (!sched_finished()) {
        unsigned new_m_id = sched_next();
        if (new_m_id) {
            LOG("Starting new measurement id=%u\n", new_m_id);
            assert(find_and_connect_metas(new_m_id, metas, num_tor_clients));
            assert(send_auth_metas(new_m_id, metas, num_tor_clients));
        }
        int num_authing_fds = 0;
        for (int i = 0; i < num_tor_clients; i++) {
            if (metas[i].state == csm_st_authing) {
                LOG("Adding fd=%d to list of fds needed auth response\n", metas[i].fd);
                authing_fds[num_authing_fds++] = metas[i].fd;
            }
        }
        LOG("Would do stuff now\n");
        break;
    }
    return 0;
}

int
main(const int argc, const char *argv[]) {
    return new_main(argc, argv);
}
