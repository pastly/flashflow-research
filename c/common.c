#include <stdlib.h>
#include <assert.h>

#include "common.h"

inline const char *
csm_st_str(const enum csm_state s) {
    switch (s) {
        case csm_st_invalid: return "INVALID"; break;
        case csm_st_connected: return "CONNECTED"; break;
        case csm_st_authing: return "AUTHING"; break;
        case csm_st_authed: return "AUTHED"; break;
        case csm_st_told_connect_target: return "TOLD_CONNECT_TARGET"; break;
        case csm_st_connected_target: return "CONNECTED_TARGET"; break;
        case csm_st_setting_bw: return "SETTING_BW"; break;
        case csm_st_bw_set: return "BW_SET"; break;
        case csm_st_measuring: return "MEASURING"; break;
        case csm_st_done: return "DONE"; break;
        case csm_st_failed: return "FAILED"; break;
        default: assert(0); break;
    }
}

void
free_ctrl_sock_meta(struct ctrl_sock_meta m) {
    free(m.class);
    free(m.host);
    free(m.port);
    free(m.pw);
}
