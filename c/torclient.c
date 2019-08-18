#include<stdio.h>
#include<stdlib.h>
#include <sys/errno.h>
#include <string.h>
#include <sys/socket.h>
#include <netdb.h>
#include <unistd.h>
#include <assert.h>

#include "common.h"
#include "torclient.h"

/**
 * Change the state of the given meta, and assert on invalid state changes.
 */
#define tc_change_state(m, st) tc_change_state_((m), (st), __func__, __FILE__, __LINE__)
void
tc_change_state_(struct ctrl_sock_meta *meta, enum csm_state new_state, const char *func, const char *file, const int line) {
    enum csm_state old_state = meta->state;
    switch (old_state) {
        case csm_st_invalid:
            switch (new_state) {
                case csm_st_connected:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            }; break;
        case csm_st_connected:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_authing:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            }; break;
        case csm_st_authing:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_authed:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_authed:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_told_connect_target:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_told_connect_target:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_connected_target:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_connected_target:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_setting_bw:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_setting_bw:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_bw_set:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_bw_set:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_measuring:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_measuring:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_done:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            };
            break;
        case csm_st_done:
            switch (new_state) {
                case csm_st_failed:
                case csm_st_invalid:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            }
        case csm_st_failed:
            switch (new_state) {
                case csm_st_invalid:
                    goto tc_good_state_change; break;
                default:
                    goto tc_bad_state_change; break;
            }
        default:
            LOG("Invalid old_state=%s at %s@%s:%d\n", csm_st_str(old_state), func, file, line);
            assert(0);
            break;
    }
tc_good_state_change:
    LOG("Changing from %s to %s on %s at %s@%s:%d\n", csm_st_str(old_state), csm_st_str(new_state), desc_meta(meta), func, file, line);
    meta->state = new_state;
    return;
tc_bad_state_change:
    LOG("Invalid new_state=%s when old_state=%s on %s at %s@%s:%d\n", csm_st_str(new_state), csm_st_str(old_state), desc_meta(meta), func, file, line);
    assert(0);
    return;
}

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
        if (bytes_read < 0) {
            if (errno) {
                perror("Error getting line from client file");
            }
            return count;
        }
        if (!bytes_read || line[0] == '#')
            continue;
        char *token, *head, *tofree;
        char *class = NULL, *host = NULL, *port = NULL, *pw = NULL;
        int token_num = 0;
        tofree = head = strdup(line);
        while ((token = strsep(&head, " \n"))) {
            if (!strlen(token))
                continue;
            switch (token_num) {
                case 0: class = strdup(token); break;
                case 1: host = strdup(token); break;
                case 2: port = strdup(token); break;
                case 3: pw = strdup(token); break;
                default:
                    free(class);
                    free(host);
                    free(port);
                    free(pw);
                    break;
            }
            token_num++;
        }
        if (!class || !host || !port || !pw || token_num != 4)
            continue;
        free(tofree);
        int is_bg = !strncmp(class, "bg", 2);
        LOG("read client config class='%s' host='%s' port='%s' pw='%s' is_bg='%d'\n", class, host, port, pw, is_bg);
        metas[count].fd = -1;
        metas[count].state = csm_st_invalid;
        metas[count].class = class;
        metas[count].host = host;
        metas[count].port = port;
        metas[count].pw = pw;
        metas[count].is_bg = is_bg;
        metas[count].current_m_id = 0;
        count++;
    }
    free(line);
    return count;
}

/**
 * build a socket to tor's control port
 * returns -1 if error, otherwise socket
 */
int
tc_make_socket(struct ctrl_sock_meta *meta) {
    tc_assert_state(meta, csm_st_invalid);
    int s;
    struct addrinfo hints, *addr;
    s = socket(PF_INET, SOCK_STREAM, 0);
    if (s < 0) {
        perror("Error socket() control socket");
        return -1;
    }
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    //hints.ai_flags |= AI_NUMERICSERV;
    //if (getaddrinfo(meta->host, meta->port, &hints, &addr) != 0) {
    if (getaddrinfo(meta->host, NULL, &hints, &addr) != 0) {
        perror("Error getaddrinfo()");
        return -1;
    }
    ((struct sockaddr_in *)addr->ai_addr)->sin_port = htons(atoi(meta->port));
    if (connect(s, addr->ai_addr, addr->ai_addrlen) != 0) {
        LOG("Could not connect to %s:%s ... ", meta->host, meta->port);
        perror("Error connect() control socket");
        return -1;
    }
    meta->fd = s;
    tc_change_state(meta, csm_st_connected);
    return s;
}

/*
 * authenticate to tor. can auth with password or no auth.
 * give socket that's already connected. if no password, give NULL or empty
 * string, otherwise give the password.
 * returns false if error, otherwise true
 */
int
tc_auth_socket(struct ctrl_sock_meta *meta) {
    tc_assert_state(meta, csm_st_connected);
    char msg[80];
    int s = meta->fd;
    const char *ctrl_pw = meta->pw;
    tc_assert_state(meta, csm_st_connected);
    if (!ctrl_pw)
        ctrl_pw = "";
    if (snprintf(msg, 80, "AUTHENTICATE \"%s\"\n", ctrl_pw) < 0) {
        perror("Error snprintf auth message");
        return 0;
    }
    if (send(s, msg, strlen(msg), 0) < 0) {
        perror("Error sending auth message");
        return 0;
    }
    //LOG("Sent auth message '%s' to %d\n", msg, s);
    tc_change_state(meta, csm_st_authing);
    return 1;
}

/**
 * read auth response from tor. returns true if good response, else false.
 */
int
tc_authed_socket(struct ctrl_sock_meta *meta) {
    tc_assert_state(meta, csm_st_authing);
    char buf[READ_BUF_LEN];
    int len;
    const char *good_resp = "250 OK";
    if ((len = recv(meta->fd, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error receiving auth response");
        return 0;
    }
    if (strncmp(buf, good_resp, strlen(good_resp))) {
        buf[len] = '\0';
        LOG("Unknown auth response: %s\n", buf);
        return 0;
    }
    tc_change_state(meta, csm_st_authed);
    return 1;
}

/**
 * tell an authed tor client to connect to the given relay fp
 */
int
tc_tell_connect(struct ctrl_sock_meta *meta, const char *fp, const unsigned conns) {
    LOG("Telling %s to connect to %s with %u conns\n", desc_meta(meta), fp, conns);
    tc_assert_state(meta, csm_st_authed);
    const int buf_size = 1024;
    char msg[buf_size];
    const char *bg_str = meta->is_bg ? " BG" : "";
    assert(!meta->is_bg || (meta->is_bg && conns == 1));
    if (snprintf(msg, buf_size, "TESTSPEED %s %u%s\n", fp, conns, bg_str) < 0) {
        LOG("Error making msg in tc_tell_connect()");
        return 0;
    }
    if (send(meta->fd, msg, strlen(msg), 0) < 0) {
        perror("Error sending msg in tc_tell_connect()");
        return 0;
    }
    tc_change_state(meta, csm_st_told_connect_target);
    return 1;
}

/**
 * read connected-to-target response from tor. returns true if good, else false
 */
int
tc_connected_socket(struct ctrl_sock_meta *meta) {
    tc_assert_state(meta, csm_st_told_connect_target);
    char buf[READ_BUF_LEN];
    int len;
    const char *good_resp = "250 SPEEDTESTING";
    if ((len = recv(meta->fd, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error receiving connect-to-target response");
        return 0;
    }
    if (strncmp(buf, good_resp, strlen(good_resp))) {
        buf[len] = '\0';
        LOG("Unknown connect-to-target response: %s\n", buf);
        return 0;
    }
    tc_change_state(meta, csm_st_connected_target);
    return 1;
}

int
tc_set_bw_rate(struct ctrl_sock_meta *meta, const unsigned bw) {
    LOG("Telling %s to set its rate/burst to %u\n", desc_meta(meta), bw);
    tc_assert_state(meta, csm_st_connected_target);
    const int buf_size = 1024;
    char msg[buf_size];
    unsigned acc = meta->is_bg ? 1 : 32;
    if (snprintf(msg, buf_size, "RESETCONF BandwidthRate=%u BandwidthBurst=%u "
            "SchedulerEchoCellMustAccumulate=%u\n", bw, bw, acc) < 0) {
        perror("Error snprintf RESETCONF bw rate/burst");
        return 0;
    }
    if (send(meta->fd, msg, strlen(msg), 0) < 0) {
        perror("Error sending RESETCONF bw rate/burst message");
        return 0;
    }
    tc_change_state(meta, csm_st_setting_bw);
    return 1;
}

int
tc_did_set_bw_rate(struct ctrl_sock_meta *meta) {
    tc_assert_state(meta, csm_st_setting_bw);
    char buf[READ_BUF_LEN];
    int len;
    const char *good_resp = "250 OK";
    if ((len = recv(meta->fd, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error receiving did-set-bw response");
        return 0;
    }
    if (strncmp(buf, good_resp, strlen(good_resp))) {
        buf[len] = '\0';
        LOG("Unknown did-set-bw response: %s\n", buf);
        return 0;
    }
    tc_change_state(meta, csm_st_bw_set);
    return 1;
}

int
tc_start_measurement(struct ctrl_sock_meta *meta, const unsigned dur) {
    LOG("Telling %s to measure for %u secs\n", desc_meta(meta), dur);
    const int buf_size = 80;
    char msg[buf_size];
    if (snprintf(msg, buf_size, "TESTSPEED %d\n", dur) < 0) {
        LOG("Error making msg in tc_start_measurement()\n");
        return 0;
    }
    if (send(meta->fd, msg, strlen(msg), 0) < 0) {
        perror("Error sending tc_start_measurement() message");
        return 0;
    }
    tc_change_state(meta, csm_st_measuring);
    return 1;
}

int
tc_output_result(struct ctrl_sock_meta *meta, unsigned m_id, const char *fp) {
    char buf[READ_BUF_LEN];
    int len;
    struct timeval t;
    if (gettimeofday(&t, NULL) < 0) {
        perror("Error getting the time");
        return 0;
    }
    if ((len = recv(meta->fd, buf, READ_BUF_LEN, 0)) < 0) {
        perror("Error reading result response");
        return 0;
    }
    if (!len) {
        LOG("Read empty result response. Assuming %s is done\n", desc_meta(meta));
        tc_change_state(meta, csm_st_done);
        return 1;
    }
    buf[len] = '\0';
    for (int j = len-1; buf[j] == '\r' || buf[j] == '\n'; j--) {
        buf[j] = '\0';
    }
    char *token, *head, *tofree;
    tofree = head = strdup(buf);
    while ((token = strsep(&head, "\r\n"))) {
        if (!strlen(token))
            continue;
        printf(
            TS_FMT " %u %s %s;%s:%s %s\n",
            t.tv_sec, t.tv_usec,
            m_id, fp,
            meta->class, meta->host, meta->port,
            token);
    }
    free(tofree);
    const char *done_resp = "650 SPEEDTESTING END";
    if (strstr(buf, done_resp)) {
        tc_change_state(meta, csm_st_done);
    }
    return 1;
}

/** 
 * Finds and returns the index of the next available meta with the given class.
 * "Available" means it isn't used in a measurement, we just now tried
 * connecting to it successfully, and we were able to auth to it. We leave it
 * in the authed and ready-to-go state.
 * 
 * If none is available, returns -1.
 */
int
tc_next_available(const int num_metas, struct ctrl_sock_meta metas[], const char *class) {
    for (int i = 0; i < num_metas; i++) {
        if (!strcmp(metas[i].class, class) && !metas[i].current_m_id) {
            LOG("Trying to make socket for %s\n", desc_meta(&metas[i]));
            if (tc_make_socket(&metas[i]) < 0) {
                //LOG("Unable to open socket to %s:%s\n", metas[i].host, metas[i].port);
                continue;
            }
            LOG("Connected to %s\n", desc_meta(&metas[i]));
            return i;
        }
    }
    return -1;
}

void
tc_mark_failed(struct ctrl_sock_meta *meta) {
    tc_change_state(meta, csm_st_failed);
}

int
tc_finished_with_meta(struct ctrl_sock_meta *meta) {
    LOG("Finished with %s\n", desc_meta(meta));
    tc_change_state(meta, csm_st_invalid);
    if (meta->fd >= 0) {
        LOG("closing fd for %s\n", desc_meta(meta));
        // https://stackoverflow.com/questions/4160347/close-vs-shutdown-socket
        //shutdown(meta->fd, SHUT_RDWR);
        close(meta->fd);
        meta->fd = -1;
    }
    //if (meta->class) {
    //    LOG("freeing class=%s\n", meta->class);
    //    free(meta->class);
    //    meta->class = NULL;
    //}
    //if (meta->host) {
    //    LOG("freeing host=%s\n", meta->host);
    //    free(meta->host);
    //    meta->host = NULL;
    //}
    //if (meta->port) {
    //    LOG("freeing port=%s\n", meta->port);
    //    free(meta->port);
    //    meta->port = NULL;
    //}
    //if (meta->pw) {
    //    LOG("freeing pw=%s\n", meta->pw);
    //    free(meta->pw);
    //    meta->pw = NULL;
    //}
    if (meta->current_m_id) {
        LOG("clearing current_m_id=%u for %s\n", meta->current_m_id, desc_meta(meta));
        meta->current_m_id = 0;
    }
    return 1;
}

void
tc_assert_state_(const struct ctrl_sock_meta *meta, const enum csm_state state, const char *func, const char *file, const int line) {
    if (meta->state != state) {
        LOG("Assert in %s@%s:%d! %s in state %s but expected to be in %s\n",
            func, file, line,
            desc_meta(meta),
            csm_st_str(meta->state), csm_st_str(state));
            assert(meta->state == state);
    }
}
