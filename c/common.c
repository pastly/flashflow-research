#include <stdlib.h>

#include "common.h"

inline const char *
csm_st_str(const enum csm_state s) {
    switch (s) {
        case csm_st_invalid: return "INVALID"; break;
        case csm_st_connected: return "CONNECTED"; break;
        case csm_st_authing: return "AUTHING"; break;
        case csm_st_authed: return "AUTHED"; break;
        case csm_st_told_connect: return "TOLD_CONNECT"; break;
        case csm_st_measuring: return "MEASURING"; break;
    }
}

void
free_ctrl_sock_meta(struct ctrl_sock_meta m) {
    free(m.class);
    free(m.host);
    free(m.port);
    free(m.pw);
}