#include<stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/select.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <limits.h>

#define READ_BUF_LEN 1024*8
#define MAX_NUM_CTRL_SOCKS 64

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
    const char *host;
    const char *port;
    int nconns;
};

void
usage() {
    const char *s = \
    "arguments: <fingerprint_file> <duration> "
    "<ctrl_pw> <host> <port> <n_socks> [host port n_socks [host port n_socks ...]]\n"
    "\n"
    "fingerprint_file    place from which to read fingerprints to measure, one per line\n"
    "duration            duration of each measurement\n"
    "ctrl_pw             password used to auth to tor client, can be empty string\n"
    "host port n_socks   hostname and port of a tor client, and number of socks it should\n"
    "                    open to target. specify this 1 or more times\n";
    LOG("%s", s);
}

/*
 * build a socket to tor's control port at the given host and port
 * returns -1 if error, otherwise socket
 */
int
get_ctrl_sock(const char *host, const char *port) {
    int s;
    struct addrinfo hints, *addr;
    s = socket(PF_INET, SOCK_STREAM, 0);
    if (s < 0) {
        perror("Error socket() control socket");
        return -1;
    }
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = PF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(host, port, &hints, &addr) != 0) {
        perror("Error getaddrinfo()");
        return -1;
    }
    if (connect(s, addr->ai_addr, addr->ai_addrlen) != 0) {
        LOG("Could not connect to %s:%s ... ", host, port);
        perror("Error connect() control socket");
        return -1;
    }
    return s;
}

/*
 * authenticate to tor. can auth with password or no auth.
 * give socket that's already connected. if no password, give NULL or empty
 * string, otherwise give the password.
 * returns false if error, otherwise true
 */
int
auth_ctrl_sock(const int s, const char *ctrl_pw) {
    char buf[READ_BUF_LEN];
    char msg[80];
    int len;
    if (!ctrl_pw)
        ctrl_pw = "";
    if (snprintf(msg, 80, "AUTHENTICATE \"%s\"\n", ctrl_pw) < 0) {
        perror("Error snprintf auth message");
        return 0;
    }
    const char *good_resp = "250 OK";
    if (send(s, msg, strlen(msg), 0) < 0) {
        perror("Error sending auth message");
        return 0;
    }
    if ((len = recv(s, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error receiving auth response");
        return 0;
    }
    if (strncmp(buf, good_resp, strlen(good_resp))) {
        buf[len] = '\0';
        LOG("Unknown auth response: %s\n", buf);
        return 0;
    }
    //printf("Auth response: %d %s\n", len, buf);
    return 1;
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
    if (snprintf(msg, buf_size, "TESTSPEED %s %d\n", fp, num_conns) < 0) {
        LOG("Error making msg in connect_taget()\n");
        return 0;
    }
    if (send(s, msg, strlen(msg), 0) < 0) {
        perror("Error sending connect_taget() message");
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
 * open many sockets to tor control ports. hostports[] should be twice the
 * length of num_hostports. it's contents should alternate between hostnames
 * and port numbers.
 * the created sockets will be put into ctrl_socks. make sure it has a capactiy
 * of at least num_hostports.
 * when everything goes well, return the number of sockets created (will equal
 * num_hostports) and put the sockets in ctrl_socks. if something goes wrong,
 * return the number of sockets we successfully made before the issue, fill up
 * ctrl_socks with the good socks, and return early.
 */
int
get_ctrl_socks(const unsigned num_hostports, const char *hostports[], struct ctrl_sock_meta ctrl_sock_metas[]) {
    int i;
    for (i = 0; i < num_hostports; i++) {
        int host_idx = i * 3;
        int port_idx = host_idx + 1;
        int nconns_idx = host_idx + 2;
        int ctrl_sock;
        const char *host = hostports[host_idx];
        const char *port = hostports[port_idx];
        int nconns = atoi(hostports[nconns_idx]);
        if ((ctrl_sock = get_ctrl_sock(host, port)) < 0) {
            return i;
        }
        LOG("connected to %s:%s\n", host, port);
        ctrl_sock_metas[i].fd = ctrl_sock;
        ctrl_sock_metas[i].host = host;
        ctrl_sock_metas[i].port = port;
        ctrl_sock_metas[i].nconns = nconns;
    }
    return num_hostports;
}

/*
 * provide an array of ctrl_socks and its length. authenticate to each one.
 * returns false if we fail to auth to any tor, otherwise true.
 */
int
auth_ctrl_socks(const int num_ctrl_socks, const struct ctrl_sock_meta ctrl_sock_metas[], const char *ctrl_pw) {
    int i;
    for (i = 0; i < num_ctrl_socks; i++) {
        if (!auth_ctrl_sock(ctrl_sock_metas[i].fd, ctrl_pw)) {
            return 0;
        }
    }
    return 1;
}

/*
 * provide an array of ctrl_socks and its length. provide a relay fingerprint
 * and the number of connections each tor client should open to it. instruct
 * each tor client to connect to this relay (but not start measuring). returns
 * false if any failure, otherwise true.
 */
int
connect_target_all(const int num_ctrl_socks, const struct ctrl_sock_meta ctrl_sock_metas[], const char *fp) {
    int i;
    for (i = 0; i < num_ctrl_socks; i++) {
        int fd = ctrl_sock_metas[i].fd;
        int nconns = ctrl_sock_metas[i].nconns;
        if (!connect_target(fd, fp, nconns)) {
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
    // stores result of getline() on fp_file
    char *fp_file_line = NULL;
    size_t fp_file_line_cap = 0;
    ssize_t fp_file_bytes_read;
    if (argc < 7 || (argc - 4) % 3 != 0) {
        LOG("argc=%d\n", argc);
        usage();
        ret = -1;
        goto end;
    }
    // how long the clients should measure for, in seconds
    const unsigned dur = atoi(argv[2]);
    // password to use to auth to tor clients
    const char *ctrl_pw = argv[3];
    // first host/port/nconn arg, all following args are also host/port/nconn
    const char **hostport_argv = &argv[4];
    // numer of host+port+nconn sets that are specified on the cmd line
    unsigned num_hostports = (argc - 4) / 3;
    if (num_hostports > MAX_NUM_CTRL_SOCKS) {
        LOG("%u is too many tor clients, sorry.\n", num_hostports);
        ret = -1;
        goto end;
    }
    if ((fp_file = fopen(fp_filename, "r")) == NULL) {
        LOG("Unable to open %s\n", fp_filename);
        ret = -1;
        goto end;
    }
    // make all the socks to tor clients
    if ((num_ctrl_socks = get_ctrl_socks(num_hostports, hostport_argv, ctrl_sock_metas)) != num_hostports) {
        LOG("Unable to open all sockets\n");
        ret = -1;
        goto cleanup;
    }
    // print out useful info about each ctrl conn we have
    for (i = 0; i < num_ctrl_socks; i++) {
        struct ctrl_sock_meta meta = ctrl_sock_metas[i];
        LOG("using %s:%s fd=%d nconns=%d\n", meta.host, meta.port, meta.fd, meta.nconns);
    }
    // to tell select() the max fd we care about
    const int the_max_ctrl_sock = max_ctrl_sock(ctrl_sock_metas, num_ctrl_socks);
    if (!auth_ctrl_socks(num_ctrl_socks, ctrl_sock_metas, ctrl_pw)) {
        ret = -1;
        goto cleanup;
    }
    while ((fp_file_bytes_read = getline(&fp_file_line, &fp_file_line_cap, fp_file)) >= 0) {
        // ignore empty lines
        if (!fp_file_bytes_read)
            continue;
        // ignore comments
        if (fp_file_line[0] == '#')
            continue;
        // ignore lines that probably aren't fingerprints
        if ((fp_file_line[fp_file_bytes_read-1] == '\n' && fp_file_bytes_read != 41) ||
                (fp_file_line[fp_file_bytes_read-1] != '\n' && fp_file_bytes_read == 40)) {
            LOG("Ignoring line that doesn't look like fingerprint: \"%s\"\n", fp_file_line);
            continue;
        }
        // replace newline with null
        if (fp_file_line[fp_file_bytes_read-1] == '\n')
            fp_file_line[fp_file_bytes_read-1] = '\0';
        // we most likely have a fingerprint. assume we do.
        const char *fp = fp_file_line;
        LOG("Now measuring %s\n", fp);
        // tell everyone to connect to the given fingerprint
        LOG("Telling everyone to connect to %s\n", fp);
        if (!connect_target_all(num_ctrl_socks, ctrl_sock_metas, fp)) {
            ret = -1;
            goto cleanup;
        }
        LOG("Everyone connected to %s\n", fp);
        // tell everyone to start measuring
        LOG("Telling everyone to measure for %d\n", dur);
        if (!start_measurements(num_ctrl_socks, ctrl_sock_metas, dur)) {
            LOG("Error starting all measurements\n");
            ret = -1;
            goto cleanup;
        }
        LOG("Everyone got the message to measure for %d\n", dur);
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
                        TS_FMT " %s %s:%s %s\n",
                        resp_time.tv_sec, resp_time.tv_usec,
                        fp,
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
        LOG("Ended with %d total results", total_results);
        sleep(1);
    }

cleanup:
    fclose(fp_file);
    for (i = 0; i < num_ctrl_socks; i++) {
        LOG("Closing sock=%d\n", ctrl_sock_metas[i].fd);
        close(ctrl_sock_metas[i].fd);
    }
end:
    return ret;
}
