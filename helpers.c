#include "helpers.h"
#include <rte_malloc.h>
#include <stdio.h>
long read_file(char *file, char **buf) {
  FILE *fp;
  long buf_len = 0;
  size_t read_len;
  int res = 0;

  fp = fopen(file, "r");
  if (!fp)
    return -EIO;
  if (fseek(fp, 0L, SEEK_END) == 0) {
    buf_len = ftell(fp);
    if (buf_len == -1) {
      res = EIO;
      goto error;
    }
    *buf = rte_malloc(NULL, sizeof(char) * (buf_len + 1), 4096);
    if (!*buf) {
      res = ENOMEM;
      goto error;
    }
    if (fseek(fp, 0L, SEEK_SET) != 0) {
      res = EIO;
      goto error;
    }
    read_len = fread(*buf, sizeof(char), buf_len, fp);
    if (read_len != (unsigned long)buf_len) {
      res = EIO;
      goto error;
    }
  }
  fclose(fp);
  return buf_len;
error:
  printf("Error, can't open file %s\n, err = %d", file, res);
  if (fp)
    fclose(fp);
  rte_free(*buf);
  return -res;
}
