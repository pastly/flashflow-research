#include <stdlib.h>

#include "common.h"

void
free_ctrl_sock_meta(struct ctrl_sock_meta m) {
    free(m.class);
    free(m.host);
    free(m.port);
    free(m.pw);
}