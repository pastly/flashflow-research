#include<stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <limits.h>

#include "common.h"
#include "fpfile.h"
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
main(const int argc, const char *argv[]) {
    rust_hello();
    return 0;
    FILE *fp_file;
    // all the socks we have to tor client ctrl ports
    struct ctrl_sock_meta ctrl_sock_metas[MAX_NUM_CTRL_SOCKS];
    // to tell select() all the sockets we care about reading from
    fd_set read_set;
    // the number of ctrl socks we make successfully
    int num_ctrl_socks = 0;
    // stores the return value from select()
    int select_result = 0;
    // tells select() how long to wait before timing out
    const struct timeval select_timeout = { .tv_sec = 3, .tv_usec = 0 };
    struct timeval select_timeout_remaining;
    // the return value of this func
    int ret = 0;
    // loop iter counter
    int i, j;
    // buffer to store responses from tor clients
    char resp_buf[READ_BUF_LEN];
    // stores number of bytes read from read_response()
    int bytes_read_this_time;
    // used repeatedly to store the current time for printing
    struct timeval resp_time;
    // filename containing relay fingerprints
    const char *fp_filename = argv[1];
    const char *client_filename = argv[2];
    if (argc != 3) {
        LOG("argc=%d\n", argc);
        usage();
        ret = -1;
        goto end;
    }
    // numer of tor clients read from client_filename. Later we'll see how many
    // we can actually connect to
    unsigned num_tor_clients;
    if ((num_tor_clients = tc_client_file_read(client_filename, ctrl_sock_metas)) < 1) {
        ret = -1;
        goto end;
    }
    if ((fp_file = fp_file_open(fp_filename)) == NULL) {
        LOG("Unable to open %s\n", fp_filename);
        ret = -1;
        goto end;
    }
    // make all the socks to tor clients
    if ((num_ctrl_socks = tc_make_sockets(num_tor_clients, ctrl_sock_metas)) != num_tor_clients) {
        LOG("Unable to open all sockets\n");
        ret = -1;
        goto cleanup;
    }
    // print out useful info about each ctrl conn we have
    for (i = 0; i < num_ctrl_socks; i++) {
        struct ctrl_sock_meta meta = ctrl_sock_metas[i];
        LOG("using %s:%s fd=%d\n", meta.host, meta.port, meta.fd);
    }
    // to tell select() the max fd we care about
    const int the_max_ctrl_sock = max_ctrl_sock(ctrl_sock_metas, num_ctrl_socks);
    if (!tc_auth_sockets(num_ctrl_socks, ctrl_sock_metas)) {
        ret = -1;
        goto cleanup;
    }
    struct msm_params msm_params;
    while (fp_file_next(fp_file, &msm_params)) {
        LOG("Now measuring %s\n", msm_params.fp);
        // tell everyone to connect to the given fingerprint
        LOG("Telling everyone to connect to %s\n", msm_params.fp);
        if (!connect_target_all(num_ctrl_socks, ctrl_sock_metas, msm_params.m_nconn, msm_params.fp)) {
            ret = -1;
            goto cleanup;
        }
        LOG("Everyone connected to %s\n", msm_params.fp);
        if (!tc_set_bw_rates(num_ctrl_socks, ctrl_sock_metas, msm_params.m_bw)) {
            LOG("Error telling all measurers to set their bw rates\n");
            ret = -1;
            goto cleanup;
        }
        // tell everyone to start measuring
        LOG("Telling everyone to measure for %u seconds\n", msm_params.dur);
        if (!start_measurements(num_ctrl_socks, ctrl_sock_metas, msm_params.dur)) {
            LOG("Error starting all measurements\n");
            ret = -1;
            goto cleanup;
        }
        LOG("Everyone got the message to measure for %u seconds\n", msm_params.dur);
        // "main loop" of receiving results from the measurers
        LOG("Entering read loop\n");
        struct timeval now;
        gettimeofday(&now, NULL);
        long last_logged_second = now.tv_sec;
        int results_since_last_logged = 0;
        int total_results = 0;
        while (1) {
            FD_ZERO(&read_set);
            for (i = 0; i < num_ctrl_socks; i++) {
                FD_SET(ctrl_sock_metas[i].fd, &read_set);
            }
            // some *nix OSes will use the timeout arg to indicate how much
            // time was left when it returns successfully. Since we aren't
            // necessarily interested in that, but we will be interested in the
            // original timeout later for logging, copy it.
            select_timeout_remaining = select_timeout;
            // blocks until timeout or 1 (or more) socket can read
            select_result = select(the_max_ctrl_sock+1, &read_set, NULL, NULL, &select_timeout_remaining);
            if (select_result < 0) {
                perror("Error on select()");
                ret = -1;
                goto cleanup;
            } else if (select_result == 0) {
                LOG(TS_FMT " sec timeout on select().\n", select_timeout.tv_sec, select_timeout.tv_usec);
                goto end_of_single_fp_loop;
            }
            // check each socket and see if it can read
            for (i = 0; i< num_ctrl_socks; i++) {
                if (FD_ISSET(ctrl_sock_metas[i].fd, &read_set)) {
                    // read in the response
                    bytes_read_this_time = read_response(ctrl_sock_metas[i].fd, resp_buf, READ_BUF_LEN, &resp_time);
                    if (bytes_read_this_time < 0) {
                        LOG("select() said there was something to read on %d, but had error.\n", ctrl_sock_metas[i].fd);
                        ret = -1;
                        goto cleanup;
                    } else if (bytes_read_this_time == 0) {
                        LOG("read 0 bytes when select() said there was something to read on %d\n", ctrl_sock_metas[i].fd);
                        goto end_of_single_fp_loop;
                    }
                    // make sure the end is clean, and remove any trailing newlines
                    resp_buf[bytes_read_this_time] = '\0';
                    for (j = bytes_read_this_time-1; resp_buf[j] == '\r' || resp_buf[j] == '\n'; j--) {
                        resp_buf[j] = '\0';
                    }
                    // output the result on stdout
                    printf(
                        TS_FMT " %u %s %s;%s:%s %s\n",
                        resp_time.tv_sec, resp_time.tv_usec,
                        msm_params.id, msm_params.fp,
                        ctrl_sock_metas[i].class,
                        ctrl_sock_metas[i].host, ctrl_sock_metas[i].port,
                        resp_buf);
                    results_since_last_logged++;
                    total_results++;
                    gettimeofday(&now, NULL);
                    if (now.tv_sec > last_logged_second) {
                        LOG("Have %d results (%d total)\n", results_since_last_logged, total_results);
                        results_since_last_logged = 0;
                        last_logged_second = now.tv_sec;
                    }
                }
            }
        }
end_of_single_fp_loop:
        free_msm_params(msm_params);
        LOG("Ended with %d total results\n", total_results);
        sleep(1);
    }

cleanup:
    fp_file_close(fp_file);
    for (i = 0; i < num_ctrl_socks; i++) {
        LOG("Closing fd=%d\n", ctrl_sock_metas[i].fd);
        close(ctrl_sock_metas[i].fd);
        free_ctrl_sock_meta(ctrl_sock_metas[i]);
    }
end:
    return ret;
}
