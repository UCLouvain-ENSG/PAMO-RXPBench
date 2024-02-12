#include "util-hs.h"
#include <inttypes.h>
#include <openssl/evp.h>
#include <rte_debug.h>
#include <rte_log.h>
#include <rte_malloc.h>
#include <string.h>
#include <unistd.h>

// Function to log set Hyperscan flags in one line
char *hs_log_expression_flags(uint32_t flags) {
  static char flag_str[512] = {0};
  int offset = 0;

  if (flags == 0)
    snprintf(flag_str, sizeof(flag_str), "NULL");

  if (flags & HS_FLAG_CASELESS)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_CASELESS", offset ? " | " : "");
  if (flags & HS_FLAG_DOTALL)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_DOTALL", offset ? " | " : "");
  if (flags & HS_FLAG_MULTILINE)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_MULTILINE", offset ? " | " : "");
  if (flags & HS_FLAG_SINGLEMATCH)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_SINGLEMATCH", offset ? " | " : "");
  if (flags & HS_FLAG_ALLOWEMPTY)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_ALLOWEMPTY", offset ? " | " : "");
  if (flags & HS_FLAG_UTF8)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_UTF8", offset ? " | " : "");
  if (flags & HS_FLAG_UCP)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_UCP", offset ? " | " : "");
  if (flags & HS_FLAG_PREFILTER)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_PREFILTER", offset ? " | " : "");
  if (flags & HS_FLAG_SOM_LEFTMOST)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_SOM_LEFTMOST", offset ? " | " : "");
  if (flags & HS_FLAG_COMBINATION)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_COMBINATION", offset ? " | " : "");
  if (flags & HS_FLAG_QUIET)
    offset += snprintf(flag_str + offset, sizeof(flag_str) - offset,
                       "%sHS_FLAG_QUIET", offset ? " | " : "");

  return flag_str;
}

static char *hs_read_stream(const char *filePath, size_t *bufferSize) {
  FILE *file = fopen(filePath, "rb");
  if (!file) {
    perror("Failed to open file");
    return NULL;
  }

  // Seek to the end of the file to determine its size
  fseek(file, 0, SEEK_END);
  long fileSize = ftell(file);
  if (fileSize == -1) {
    perror("Failed to determine file size");
    fclose(file);
    return NULL;
  }

  // Allocate a buffer to hold the entire file
  char *buffer = (char *)malloc(fileSize);
  if (!buffer) {
    perror("Failed to allocate memory");
    fclose(file);
    return NULL;
  }

  // Rewind file pointer and read the file into the buffer
  rewind(file);
  size_t bytesRead = fread(buffer, 1, fileSize, file);
  if (bytesRead != fileSize) {
    perror("Failed to read the entire file");
    free(buffer);
    fclose(file);
    return NULL;
  }

  *bufferSize = fileSize;
  fclose(file);
  return buffer;
}

static int file_to_md5(const char *filename, uint8_t **md5_digest_out,
                       uint32_t *md5_digest_len_out) {
  FILE *file;
  file = fopen(filename, "r");
  if (!file) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to open file: %s\n",
            filename);
    return -1;
  }

  EVP_MD_CTX *mdctx;
  uint8_t *md5_digest;
  uint32_t md5_digest_len = EVP_MD_size(EVP_md5());

  // MD5_Init
  mdctx = EVP_MD_CTX_new();
  EVP_DigestInit_ex(mdctx, EVP_md5(), NULL);

  // MD5_Update
  int32_t bytes;
  uint8_t data[1024];
  while ((bytes = fread(data, 1, 1024, file)) != 0)
    EVP_DigestUpdate(mdctx, data, bytes);

  // MD5_Final
  md5_digest = (uint8_t *)OPENSSL_malloc(md5_digest_len);
  EVP_DigestFinal_ex(mdctx, md5_digest, &md5_digest_len);
  EVP_MD_CTX_free(mdctx);

  *md5_digest_out = md5_digest;
  *md5_digest_len_out = md5_digest_len;

  fclose(file);
  return 0;
}

static char *hs_db_cache_construct_fpath(uint8_t *hash_arr,
                                         uint32_t hash_arr_len,
                                         const uint32_t expr_flags) {
  // todo: better to rework
  static char hash_file[2048];
  if (hash_arr_len * 2 + 255 > 2048)
    rte_panic("Hash array length too long\n");
  char hash_file_path_prefix_path[] = "/tmp/";
  char hash_file_path_suffix[] = "_v1.hsdb";
  uint16_t hash_file_bytes_written = 0;
  snprintf(hash_file, sizeof(hash_file), "%s", hash_file_path_prefix_path);
  hash_file_bytes_written += sizeof(hash_file_path_prefix_path) - 1;
  for (int32_t i = 0; i < hash_arr_len; i++) {
    snprintf(hash_file + hash_file_bytes_written,
             sizeof(hash_file) - hash_file_bytes_written, "%02x", hash_arr[i]);
    hash_file_bytes_written += 2;
  }
  snprintf(hash_file + hash_file_bytes_written,
           sizeof(hash_file) - hash_file_bytes_written, "_%02x%s", expr_flags,
           hash_file_path_suffix);
  hash_file_bytes_written += sizeof(hash_file_path_suffix) - 1;
  return hash_file;
}

static int hs_init_db_from_cache(const char *filename, hs_database_t **hs_db,
                                 const uint32_t expr_flags) {
  int ret = -1;
  uint8_t *md5_digest;
  uint32_t md5_digest_len;
  if (file_to_md5(filename, &md5_digest, &md5_digest_len) != 0) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to compute MD5 hash\n");
    return -1;
  }

  char *hash_file_static = hs_db_cache_construct_fpath(md5_digest, md5_digest_len, expr_flags);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Hyperscan cached DB file path: %s\n", hash_file_static);
  
  FILE *db_cache = fopen(hash_file_static, "r");
  char* buffer = NULL;
  if (db_cache) {
    size_t bufferSize;
    buffer = hs_read_stream(hash_file_static, &bufferSize);
    if (!buffer) {
        rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Hyperscan cached DB file %s cannot be read\n", hash_file_static);
        ret = -1;
        goto freeup;
    }

    hs_error_t error = hs_deserialize_database(buffer, bufferSize, hs_db);
    if (error != HS_SUCCESS) {
        rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to deserialize Hyperscan database: %d\n", error);
        ret = -1;
        goto freeup;
    }

    ret = 0;
    goto freeup;
  }

freeup:
  if (db_cache)
    fclose(db_cache);
  if (buffer)
    free(buffer);  
  return ret;
}

int hs_init_db(const char *filename, hs_database_t **hs_db,
               const uint32_t expr_flags) {
  if (hs_init_db_from_cache(filename, hs_db, expr_flags) == 0) {
    rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Loaded db from cache !\n");
    return 0;
  }

  FILE *file;
  file = fopen(filename, "r");
  if (!file) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to open file: %s\n",
            filename);
    return -1;
  }
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Preparing first pass...\n");
  // First pass: Count the number of patterns
  ssize_t read;
  size_t line_capa = 0;
  char *line = NULL;
  uint32_t expression_count = 0;
  while ((read = getline(&line, &line_capa, file)) != -1) {
    expression_count++;
  }
  free(line);               // Free the buffer allocated by getline
  line = NULL;              // Reset line pointer
  fseek(file, 0, SEEK_SET); // Rewind file for second pass
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1,
          "Done. Preparing for second pass...\n");

  const char **expressions = (const char **)rte_malloc(
      "expressions", sizeof(char *) * expression_count, 0);
  uint32_t *flags =
      (uint32_t *)rte_malloc("flags", sizeof(uint32_t) * expression_count, 0);
  uint32_t *ids =
      (uint32_t *)rte_malloc("ids", sizeof(uint32_t) * expression_count, 0);
  if (!expressions || !flags || !ids) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Memory allocation failed\n");
    if (expressions)
      rte_free(expressions);
    if (flags)
      rte_free(flags);
    if (ids)
      rte_free(ids);
    fclose(file);
    return -1;
  }

  uint32_t i = 0;
  while ((read = getline(&line, &line_capa, file)) != -1 &&
         i < expression_count) {
    if (line[read - 1] == '\n') {
      line[read - 1] = '\0'; // Remove the newline character
    } else {
      rte_panic("Line not terminated by newline character - \"%s\"\n", line);
    }
    if (strnlen(line, read) == 0) {
      expression_count--;
      continue;
    }

    expressions[i] = strdup(line); // Copy the pattern
    flags[i] = expr_flags;
    ids[i] = 1; //i + 1; // singleid to make use of the single match flag
    i++;
  }
  free(line); // Free the buffer allocated by getline after the final read
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Done. Preparing compilation...\n");

  hs_compile_error_t *hs_compile_err = NULL;
  // if (hs_compile(expressions[i], flags[i], HS_MODE_BLOCK, NULL, hs_db,
  //                  &hs_compile_err) != HS_SUCCESS) {
  if (hs_compile_multi(expressions, flags, ids, expression_count, HS_MODE_BLOCK,
                       NULL, hs_db, &hs_compile_err) != HS_SUCCESS) {
    if (hs_compile_err->expression < 0) {
      // The error does not refer to a particular expression.
      rte_log(
          RTE_LOG_ERR, RTE_LOGTYPE_USER1,
          "HS Pattern compilation failed with pattern-unrelated error: %s\n",
          hs_compile_err->message);
    } else {
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1,
              "HS Pattern %s compilation failed: %s\n",
              expressions[hs_compile_err->expression], hs_compile_err->message);
    }
    hs_free_compile_error(hs_compile_err);
    rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Done.\n");

    for (i = 0; i < expression_count; i++) {
      free((void *)expressions[i]);
    }
    rte_free(expressions);
    rte_free(flags);
    rte_free(ids);
    fclose(file);
    return -1;
  }

  // Clean up
  for (i = 0; i < expression_count; i++) {
    free((void *)expressions[i]);
  }
  rte_free(expressions);
  rte_free(flags);
  rte_free(ids);
  fclose(file);

  // Serialize the database
  char *db_stream;
  size_t db_size;
  hs_error_t error = hs_serialize_database(*hs_db, &db_stream, &db_size);
  if (error != HS_SUCCESS) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1,
            "Failed to serialize Hyperscan database: %d\n", error);
    return -1;
  }

  uint8_t *md5_digest;
  uint32_t md5_digest_len;
  file_to_md5(filename, &md5_digest, &md5_digest_len);
  char *hash_file_static = hs_db_cache_construct_fpath(md5_digest, md5_digest_len, expr_flags);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Hyperscan caching DB to: %s\n", hash_file_static);
  FILE *db_cache_out = fopen(hash_file_static, "w");
  if (!db_cache_out) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to open file: %s\n",
            hash_file_static);
    return -1;
  }
  int ret = fwrite(db_stream, sizeof(db_stream[0]), db_size, db_cache_out);
  if (ret != db_size) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to write to file: %s\n",
            hash_file_static);
    return -1;
  }
  ret = fclose(db_cache_out);
  if (ret != 0) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1, "Failed to close file: %s\n",
            hash_file_static);
    return -1;
  }
  free(db_stream);

  return 0;
}

int hs_match_cb(uint32_t id, unsigned long long from, unsigned long long to,
                uint32_t flags, void *ctx) {
  HSCallBackCtx *cctx = ctx;
  // PrefilterRuleStore *pmq = cctx->pmq;
  // const PatternDatabase *pd = cctx->ctx->pattern_db;
  // const SCHSPattern *pat = pd->parray[id];

  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER2,
          "Hyperscan Matched %" PRIu32 ": id=%" PRIu32 "\n", cctx->match_count,
          (uint32_t)id);
  cctx->match_count++;
  return 0;
}
