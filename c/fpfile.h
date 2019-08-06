#ifndef FF_FPFILE_H
#define FF_FPFILE_H
#include<stdio.h>
#include "common.h"
FILE *fp_file_open(const char *fname);
int fp_file_next(FILE *fd, struct msm_params *params);
int fp_file_close(FILE *fd);
#endif /* !defined(FF_FPFILE_H) */
