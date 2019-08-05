#ifndef FF_FPFILE_H
#define FF_FPFILE_H
#include<stdio.h>
FILE *fp_file_open(const char *fname);
char *fp_file_next(FILE *fd);
int fp_file_close(FILE *fd);
#endif /* !defined(FF_FPFILE_H) */