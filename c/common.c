#include <stdlib.h>

#include "common.h"

void free_msm_params(struct msm_params p) {
    //free(p.fp);
    free(p.m_bw);
    free(p.m_nconn);
    for (int i = 0; i < p.num_m; i++) {
        free(p.m[i]);
    }
    p.num_m = 0;
}
void
free_ctrl_sock_meta(struct ctrl_sock_meta m) {
    free(m.class);
    free(m.host);
    free(m.port);
    free(m.pw);
}