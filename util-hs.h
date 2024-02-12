#pragma once

#include <hs.h>
#include <inttypes.h>
typedef struct HSCallBackCtx_ {
  uint32_t match_count;
} HSCallBackCtx;

struct hs_stats {
  uint64_t total_scans;
  uint64_t total_scans_us;
  uint64_t total_scans_cycles;
  uint64_t total_matches;
};

char *hs_log_expression_flags(unsigned int flags);

int hs_init_db(const char *filename, hs_database_t **hs_db,
               const unsigned int expr_flags);

int hs_match_cb(unsigned int id, unsigned long long from, unsigned long long to,
                unsigned int flags, void *ctx);
