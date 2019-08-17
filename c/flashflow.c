#include <stdio.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#include <assert.h>

#include "common.h"
#include "torclient.h"
#include "sched.h"

#define MAX_LOOPS_WITHOUT_PROGRESS 10

void
usage() {
    const char *s = \
    "arguments: <fingerprint_file> <client_file>\n"
    "\n"
    "fingerprint_file    place from which to read fingerprints to measure, one per line\n"
    "client_file         place from which to read tor client info, one per line, 'host port ctrl_port_pw'\n";
    LOG("%s", s);
}


int
fill_msm_params(struct msm_params *p, const unsigned m_id) {
    p->id = m_id;
    p->fp = sched_get_fp(p->id);
    p->dur = sched_get_dur(p->id);
    p->num_m = sched_get_hosts(p->id, &p->m, &p->m_bw, &p->m_nconn);
    p->m_assigned = calloc(p->num_m, sizeof(int8_t));
    if (!p->fp) {
        LOG("Should have gotten a relay fp\n");
        return 0;
    }
    if (!p->dur) {
        LOG("Should have gotten a duration\n");
        return 0;
    }
    if (!p->num_m) {
        LOG("Should have gotten a set of hosts\n");
        return 0;
    }
    return 1;
}
void
free_msm_params(struct msm_params *p) {
    if (!p) {
        return;
    }
    sched_free_hosts(p->m, p->m_bw, p->m_nconn, p->num_m);
    free(p->m_assigned);
}

int
find_and_connect_metas(unsigned m_id, struct ctrl_sock_meta metas[], const int num_metas) {
    struct msm_params p;
    if (!fill_msm_params(&p, m_id)) {
        return 0;
    }
    LOG("About to look for hosts with the following classes. Will eventually tell them the bw and nconn.\n")
    for (int i = 0; i < p.num_m; i++) {
        LOG("class=%s bw=%u nconn=%u\n", p.m[i], p.m_bw[i], p.m_nconn[i]);
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

int
send_auth_metas(unsigned m_id, struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id != m_id)
            continue;
        tc_assert_state(&metas[i], csm_st_connected);
        if (!tc_auth_socket(&metas[i])) {
            return 0;
        }
    }
    return 1;
}

/** 
 * Returns def if all items in array are less than def, else the max of array
 */
int
max_or(int array[], int array_len, int def) {
    int max = def;
    for (int i = 0; i < array_len; i++)
        if (array[i] > max)
            max = array[i];
    return max;
}

/**
 * Find the meta with the given fd
 */
struct ctrl_sock_meta *
meta_with_fd(const int fd, struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++)
        if (metas[i].fd == fd)
            return &metas[i];
    return NULL;
}

/**
 * Iterate through all metas. For those that are a part of the given
 * measurement id, if any are not authed, return false. Else return true. Note
 * how if you are dumb, this will return true even if there are no metas that
 * are a part of the m_id you gave. It will even return true if num_metas is
 * zero.
 */
int
is_totally_authed(unsigned m_id, const struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id != m_id)
            continue;
        if (metas[i].state != csm_st_authed)
            return 0;
    }
    return 1;
}

/**
 * Like is_totally_authed(), but for seeing if all metas with m_id as their
 * measurement are connected to the target relay.
 */
int
is_totally_connected_target(unsigned m_id, const struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id != m_id)
            continue;
        if (metas[i].state != csm_st_connected_target)
            return 0;
    }
    return 1;
}

/**
 * Like is_totally_authed(), but for seeing if all metas with m_id as their
 * measurement have limited their bw
 */
int
is_totally_bw_set(unsigned m_id, const struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id != m_id)
            continue;
        if (metas[i].state != csm_st_bw_set)
            return 0;
    }
    return 1;
}

/**
 * Like is_totally_authed(), but for seeing if all metas with m_id as their
 * measurement have finished
 */
int
is_totally_done(unsigned m_id, const struct ctrl_sock_meta metas[], const int num_metas) {
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id != m_id)
            continue;
        if (metas[i].state != csm_st_done)
            return 0;
    }
    return 1;
}

/**
 * A measurement failed. Give its id. Tell the sched that the measurement is
 * done. This will remove it from the given m_ids array. Set all the metas with
 * the given m_id as failed and mark them as finished. Returns the new number
 * of m_ids (note if it was 1, then now it's 0, which invalidates the m_id in
 * the m_ids array without replacing it).
 *
 * This will close fds for the metas that were a part of this experiment, so if
 * you were in the middle of checking fds, you will want to go back to the
 * start of the main loop and let select() tell you again what fds are reading.
 */
int
measurement_failed(
        unsigned m_id,
        unsigned m_ids[], int num_m,
        struct ctrl_sock_meta metas[], const int num_metas) {
    LOG("FAILED measurement id=%u. Cleaning up.\n", m_id);
    sched_mark_done(m_id);
    if (num_m <= 0) {
        LOG("WARN: called measurement_failed() with %d measurements. "
            "Expected at least 1.\n", num_m);
        return num_m;
    }
    // replace the given measurement id with whatever is the last one in the
    // list of all measurement ids
    for (int i = 0; i < num_m; i++) {
        if (m_ids[i] == m_id) {
            LOG("Replacing m_id=%u (idx=%d) with m_id=%u (idx=%d)\n", m_ids[i], i, m_ids[num_m-1], num_m-1);
            m_ids[i] = m_ids[--num_m];
            break;
        }
    }
    // cleanup all tor client metas that were a part of thie measurement
    for (int i = 0; i < num_metas; i++) {
        if (metas[i].current_m_id == m_id) {
            tc_mark_failed(&metas[i]);
            tc_finished_with_meta(&metas[i]);
        }
    }
    return num_m;
}

int main(int argc, const char *argv[]) {
    int count_success = 0, count_failure = 0, count_total = 0;
    struct ctrl_sock_meta metas[MAX_NUM_CTRL_SOCKS];
    unsigned known_m_ids[MAX_NUM_CTRL_SOCKS];
    int num_known_m_ids = 0;
    int authing_fds[MAX_NUM_CTRL_SOCKS];
    int connecting_fds[MAX_NUM_CTRL_SOCKS];
    int setting_bw_fds[MAX_NUM_CTRL_SOCKS];
    int measuring_fds[MAX_NUM_CTRL_SOCKS];
    unsigned loops_without_progress = 0;
    if (argc != 3) {
        //LOG("argc=%d\n", argc);
        usage();
        return -1;
    }
    const char *fp_fname = argv[1];
    const char *client_fname = argv[2];
    // number of tor clients read from file
    int num_tor_clients;
    LOG("Reading clients from %s\n", client_fname);
    if ((num_tor_clients = tc_client_file_read(client_fname, metas)) < 1) {
        LOG("Error reading %s or it was empty\n", client_fname);
        return -1;
    }
    LOG("We know about the following Tor clients. They may not exist, haven't checked.\n");
    for (int i = 0; i < num_tor_clients; i++) {
        LOG("%s at %s:%s\n", metas[i].class, metas[i].host, metas[i].port);
    }
    LOG("Reading experiments from %s\n", fp_fname);
    if (!(count_total = sched_new(fp_fname))) {
        LOG("Empty sched from %s or error\n", fp_fname);
        return -1;
    }
    // Main loop
    while (!sched_finished()) {
        if (loops_without_progress > MAX_LOOPS_WITHOUT_PROGRESS) {
            // TODO: The right thing to do is to fail on the current
            // measurements and start new ones. Not recovering gracefully is a
            // big problem in this currently.
            LOG("Went %u main loops without any forward progress. Giving up on life.\n", loops_without_progress);
            return -1;
        }
        unsigned new_m_id;
        while ((new_m_id = sched_next())) {
            // We are allowed to start a new measurement. Get the ball rolling
            // on that by finding and connecting to the needed tor clients.
            LOG("Starting new measurement id=%u\n", new_m_id);
            if (!find_and_connect_metas(new_m_id, metas, num_tor_clients)) {
                LOG("Cannot start measurement id=%u. Skipping.\n", new_m_id);
                sched_mark_done(new_m_id);
                continue;
            }
            known_m_ids[num_known_m_ids++] = new_m_id;
            if (!send_auth_metas(new_m_id, metas, num_tor_clients)) {
                measurement_failed(new_m_id, known_m_ids, num_known_m_ids, metas, num_tor_clients);
                count_failure++;
            }
        }
        // for each known measurement, do things for them if any of them need
        // things done. (wow such shitty comment)
        for (int i = 0; i < num_known_m_ids; i++) {
            struct msm_params p;
            assert(fill_msm_params(&p, known_m_ids[i]));
            // for authed -> tell connect to target
            if (is_totally_authed(known_m_ids[i], metas, num_tor_clients)) {
                // loop through all known tor clients and look for ones that can
                // help
                for (int j = 0; j < num_tor_clients; j++) {
                    if (metas[j].current_m_id == known_m_ids[i]) {
                        // this tor client J is for the current measurement I.
                        // Loop over the msm params and see if the K'th one is
                        // unassigned and matches tor client J's class.
                        for (int k = 0; k < p.num_m; k++) {
                            if (!strcmp(p.m[k], metas[j].class) && !p.m_assigned[k]) {
                                assert(tc_tell_connect(&metas[j], p.fp, p.m_nconn[k]));
                                tc_assert_state(&metas[j], csm_st_told_connect_target);
                                p.m_assigned[k] = 1;
                                break;
                            }
                        }
                    }
                }
                for (int j = 0; j < p.num_m; j++) {
                    assert(p.m_assigned[j]);
                }
            }
            // for connected to target -> set bw
            if (is_totally_connected_target(known_m_ids[i], metas, num_tor_clients)) {
                unsigned next_bw = 0;
                for (int j = 0; j < num_tor_clients; j++) {
                    if (metas[j].current_m_id == known_m_ids[i]) {
                        assert(tc_set_bw_rate(&metas[j], p.m_bw[next_bw++]));
                        tc_assert_state(&metas[j], csm_st_setting_bw);
                    }
                }
                assert(next_bw == p.num_m);
            }
            // for bw is set -> start measurement
            if (is_totally_bw_set(known_m_ids[i], metas, num_tor_clients)) {
                LOG("YAY ITS TIME TO START MEAUREMENT %u FINALLY\n", known_m_ids[i]);
                int num_told = 0;
                for (int j = 0; j < num_tor_clients; j++) {
                    if (metas[j].current_m_id == known_m_ids[i]) {
                        assert(tc_start_measurement(&metas[j], p.dur));
                        tc_assert_state(&metas[j], csm_st_measuring);
                        num_told++;
                    }
                }
                assert(num_told == p.num_m);
            }
            // for when done measuring
            if (is_totally_done(known_m_ids[i], metas, num_tor_clients)) {
                LOG("WOOHOO MEASUREMENT %u IS DONE\n", known_m_ids[i]);
                for (int j = 0; j < num_tor_clients; j++) {
                    if (metas[j].current_m_id == known_m_ids[i]) {
                        tc_assert_state(&metas[j], csm_st_done);
                        tc_finished_with_meta(&metas[j]);
                    }
                }
                sched_mark_done(known_m_ids[i]);
                known_m_ids[i--] = known_m_ids[--num_known_m_ids];
                count_success++;
            }
            free_msm_params(&p);
        }
        fd_set read_set;
        FD_ZERO(&read_set);
        int num_authing_fds = 0;
        int num_connecting_fds = 0;
        int num_setting_bw_fds = 0;
        int num_measuring_fds = 0;
        for (int i = 0; i < num_tor_clients; i++) {
            if (metas[i].state == csm_st_authing) {
                // Build up the list of tor client fds that we are currently waiting
                // on auth success message from
                LOG("Adding fd=%d to list of fds needed auth response\n", metas[i].fd);
                authing_fds[num_authing_fds++] = metas[i].fd;
                FD_SET(metas[i].fd, &read_set);
            } else if (metas[i].state == csm_st_told_connect_target) {
                // Build up the list of tor client fds that we are currently waiting on
                // a connect-to-target success message from
                LOG("Adding fd=%d to list of fds needed connect-to-target response\n", metas[i].fd);
                connecting_fds[num_connecting_fds++] = metas[i].fd;
                FD_SET(metas[i].fd, &read_set);
            } else if (metas[i].state == csm_st_setting_bw) {
                // Build up the list of tor client fds that we are currently waiting on
                // for a success msg about setting bw
                LOG("Adding fd=%d to list of fds needed did-set-bw response\n", metas[i].fd);
                setting_bw_fds[num_setting_bw_fds++] = metas[i].fd;
                FD_SET(metas[i].fd, &read_set);
            } else if (metas[i].state == csm_st_measuring) {
                // Build up the list of tor client fds that we are currently waiting on
                // for a per-second measurement result from
                LOG("Adding fd=%d to list of ongoing measurement fds\n", metas[i].fd);
                measuring_fds[num_measuring_fds++] = metas[i].fd;
                FD_SET(metas[i].fd, &read_set);
            }
        }
        assert(num_authing_fds >= 0);
        assert(num_connecting_fds >= 0);
        assert(num_setting_bw_fds >= 0);
        assert(num_measuring_fds >= 0);
        int num_interesting_fds = num_authing_fds + num_connecting_fds + num_setting_bw_fds + num_measuring_fds;
        if (!num_interesting_fds) {
            LOG("%d interesting fds. skipping select()\n", num_interesting_fds);
            continue;
        }
        LOG("Going in to select() with %d interesting fds\n", num_interesting_fds);
        // how long we are willing to wait on select()
        struct timeval select_timeout = { .tv_sec = 3, .tv_usec = 0 };
        struct timeval select_timeout_remaining = select_timeout;
        // for select()
        int max_fd = max_or(
            measuring_fds, num_measuring_fds, max_or(
                setting_bw_fds, num_setting_bw_fds, max_or(
                    connecting_fds, num_connecting_fds, max_or(
                        authing_fds, num_authing_fds, 0))));
        int select_result = select(max_fd+1, &read_set, NULL, NULL, &select_timeout_remaining);
        if (select_result < 0) {
            perror("Error on select()");
            loops_without_progress++;
            continue;
        } else if (select_result == 0) {
            LOG(TS_FMT " sec timeout on select().\n", select_timeout.tv_sec, select_timeout.tv_usec);
            loops_without_progress++;
            continue;
        } else {
            loops_without_progress = 0;
        }
        struct ctrl_sock_meta *meta;
        // Check for authed sockets
        for (int i = 0; i < num_authing_fds; i++) {
            if (FD_ISSET(authing_fds[i], &read_set)) {
                if (!(meta = meta_with_fd(authing_fds[i], metas, num_tor_clients))) {
                    LOG("Could not find fd=%d in metas\n", authing_fds[i]);
                    return -1;
                }
                if (!tc_authed_socket(meta)) {
                    LOG("Unable to auth to fd=%d\n", authing_fds[i]);
                    return -1;
                }
                tc_assert_state(meta, csm_st_authed);
            }
        }
        // Check for connected-to-target sockets
        for (int i = 0; i < num_connecting_fds; i++) {
            if (FD_ISSET(connecting_fds[i], &read_set)) {
                if (!(meta = meta_with_fd(connecting_fds[i], metas, num_tor_clients))) {
                    LOG("Could not find fd=%d in metas\n", connecting_fds[i]);
                    return -1;
                }
                if (!tc_connected_socket(meta)) {
                    LOG("Unable to to tell fd=%d to connect to target\n", connecting_fds[i]);
                    num_known_m_ids = measurement_failed(
                        meta->current_m_id, known_m_ids, num_known_m_ids, metas, num_tor_clients);
                    count_failure++;
                    // jump to the end of the main loop. Yes, select() will have
                    // to tell us again about and fds we didn't get around to
                    // handling this time (in connecting_fds, setting_bw_fds, or
                    // any other array). But we just marked a bunch of metas as
                    // finished, which inclides closing fds, which means those
                    // arrays of fds may have stale fds in them.
                    goto main_loop_end;
                }
                tc_assert_state(meta, csm_st_connected_target);
            }
        }
        // Check for did-set-bw sockets
        for (int i = 0; i < num_setting_bw_fds; i++) {
            if (FD_ISSET(setting_bw_fds[i], &read_set)) {
                if (!(meta = meta_with_fd(setting_bw_fds[i], metas, num_tor_clients))) {
                    LOG("Could not find fd=%d in metas\n", setting_bw_fds[i]);
                    return -1;
                }
                if (!tc_did_set_bw_rate(meta)) {
                    LOG("Unable to tell fd=%d to set its bw\n", setting_bw_fds[i]);
                    num_known_m_ids = measurement_failed(
                        meta->current_m_id, known_m_ids, num_known_m_ids, metas, num_tor_clients);
                    count_failure++;
                    // jump to the end of the main loop. Yes, select() will have
                    // to tell us again about and fds we didn't get around to
                    // handling this time (in connecting_fds, setting_bw_fds, or
                    // any other array). But we just marked a bunch of metas as
                    // finished, which inclides closing fds, which means those
                    // arrays of fds may have stale fds in them.
                    goto main_loop_end;
                }
                tc_assert_state(meta, csm_st_bw_set);
            }
        }
        // Check for socks with results
        for (int i = 0; i < num_measuring_fds; i++) {
            if (FD_ISSET(measuring_fds[i], &read_set)) {
                if (!(meta = meta_with_fd(measuring_fds[i], metas, num_tor_clients))) {
                    LOG("Could not find fd=%d in metas\n", measuring_fds[i]);
                    return -1;
                }
                struct msm_params p;
                assert(fill_msm_params(&p, meta->current_m_id));
                if (!tc_output_result(meta, p.id, p.fp)) {
                    LOG("Error while outputting some results of measurement id=%u\n", meta->current_m_id);
                    num_known_m_ids = measurement_failed(
                        meta->current_m_id, known_m_ids, num_known_m_ids, metas, num_tor_clients);
                    count_failure++;
                    // jump to the end of the main loop. Yes, select() will have
                    // to tell us again about and fds we didn't get around to
                    // handling this time (in connecting_fds, setting_bw_fds, or
                    // any other array). But we just marked a bunch of metas as
                    // finished, which inclides closing fds, which means those
                    // arrays of fds may have stale fds in them.
                    goto main_loop_end;
                }
            }
        }
        //LOG("Would do stuff now\n");
main_loop_end:
        (int)1;
    }
    LOG("ALLLLLLLL DOOOONNEEEEE\n");
    LOG("%d success, %d failed, %d total\n", count_success, count_failure, count_total);
    return 0;
}
