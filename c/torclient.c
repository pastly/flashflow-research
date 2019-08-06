#include<stdio.h>
#include<stdlib.h>
#include <sys/errno.h>
#include <string.h>
#include <sys/socket.h>
#include <netdb.h>

#include "common.h"
#include "torclient.h"

/**
 * Read all the lines from fname and store tor client info in the given
 * ctrl_sock_meta array, which should be MAX_NUM_CTRL_SOCKS in size. Returns
 * the number of lines with data parsed successfully (no empty lines, no
 * comments). The fd in each struct is not valid yet. Returns -1 on error.
 */
int
tc_client_file_read(const char *fname, struct ctrl_sock_meta metas[]) {
    FILE *fd = fopen(fname, "r");
    if (!fd) {
        perror("Error opening client file");
        return -1;
    }
    char *line = NULL;
    size_t cap = 0;
    ssize_t bytes_read;
    int count = 0;
    while (count < MAX_NUM_CTRL_SOCKS) {
        bytes_read = getline(&line, &cap, fd);
        char *line_copy = strdup(line);
        if (bytes_read < 0) {
            if (errno) {
                perror("Error getting line from client file");
            }
            return count;
        }
        if (!bytes_read || line[0] == '#')
            goto single_loop_end;
        char *class = strsep(&line, " ");
        if (!class || !strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *host = strsep(&line, " ");
        if (!host || !strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *port = strsep(&line, " ");
        if (!port || !strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        char *pw = strsep(&line, " \n");
        if (!pw || strlen(line)) {
            LOG("Ignoring invalid client file line: '%s'\n", line_copy);
            goto single_loop_end;
        }
        LOG("read client config class='%s' host='%s' port='%s' pw='%s'\n", class, host, port, pw);
        metas[count].fd = -1;
        metas[count].class = class;
        metas[count].host = host;
        metas[count].port = port;
        metas[count].pw = pw;
        metas[count].nconns = 1;
        metas[count].current_measurement = -1;
        count++;
single_loop_end:
        free(line_copy);
    }
    return count;
}

/**
 * build a socket to tor's control port
 * returns -1 if error, otherwise socket
 */
int
tc_make_socket(const struct ctrl_sock_meta meta) {
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
    if (getaddrinfo(meta.host, meta.port, &hints, &addr) != 0) {
        perror("Error getaddrinfo()");
        return -1;
    }
    if (connect(s, addr->ai_addr, addr->ai_addrlen) != 0) {
        LOG("Could not connect to %s:%s ... ", meta.host, meta.port);
        perror("Error connect() control socket");
        return -1;
    }
    return s;
}

/**
 * open many sockets to tor control ports. the created sockets will be stored
 * in the corresponding struct in metas. when everything goes well, return the
 * number of sockets created (will equal num_metas) and fill up metas. if
 * something goes wrong, return the number of sockets we successfully made
 * before the issue, fill up metas with the good socks, and return early.
 */
int
tc_make_sockets(const unsigned num_metas, struct ctrl_sock_meta metas[]) {
    int i;
    for (i = 0; i < num_metas; i++) {
        int ctrl_sock;
        if ((ctrl_sock = tc_make_socket(metas[i])) < 0) {
            return i;
        }
        LOG("connected to %s:%s\n", metas[i].host, metas[i].port);
        metas[i].fd = ctrl_sock;
    }
    return num_metas;
}

/*
 * authenticate to tor. can auth with password or no auth.
 * give socket that's already connected. if no password, give NULL or empty
 * string, otherwise give the password.
 * returns false if error, otherwise true
 */
int
tc_auth_socket(const int s, const char *ctrl_pw) {
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

/**
 * provide an array of metas and its length. authenticate to each one.
 * returns false if we fail to auth to any tor, otherwise true.
 */
int
tc_auth_sockets(const unsigned num_metas, const struct ctrl_sock_meta metas[]) {
    int i;
    for (i = 0; i < num_metas; i++) {
        if (!tc_auth_socket(metas[i].fd, metas[i].pw)) {
            return 0;
        }
    }
    return 1;
}

int
tc_set_bw_rate(const int s, const unsigned bw) {
    char buf[READ_BUF_LEN];
    char msg[80];
    int len;
    if (snprintf(msg, 80, "RESETCONF BandwidthRate=%u BandwidthBurst=%u\n", bw, bw) < 0) {
        perror("Error snprintf RESETCONF bw rate/burst");
        return 0;
    }
    const char *good_resp = "250 OK";
    if (send(s, msg, strlen(msg), 0) < 0) {
        perror("Error sending RESETCONF bw rate/burst message");
        return 0;
    }
    if ((len = recv(s, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error receiving bw rate/burst response");
        return 0;
    }
    if (strncmp(buf, good_resp, strlen(good_resp))) {
        buf[len] = '\0';
        LOG("Unknown bw rate/burst response: %s\n", buf);
        return 0;
    }
    LOG("Set rate/burst to %u on fd=%d\n", bw, s);
    return 1;
}

/**
 * Tell each tor client over its ctrl sock to limit itself to the given number
 * of BYTES per second. returns false if any failure, otherwise true
 */
int
tc_set_bw_rates(const int num_ctrl_socks, const struct ctrl_sock_meta ctrl_sock_metas[], const unsigned bws[]) {
    int i;
    for (i = 0; i < num_ctrl_socks; i++) {
        if (!tc_set_bw_rate(ctrl_sock_metas[i].fd, bws[i])) {
            return 0;
        }
    }
    return 1;
}