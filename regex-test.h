
/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright(c) 2010-2014 Intel Corporation
 */

// Simple proxy that listens to two ports and forwards packets from one port to
// another

#include "util-hs.h"
#include <assert.h>
#include <errno.h>
#include <getopt.h>
#include <inttypes.h>
#include <netinet/if_ether.h>
#include <pthread.h>
#include <rte_arp.h>
#include <rte_atomic.h>
#include <rte_branch_prediction.h>
#include <rte_common.h>
#include <rte_cycles.h>
#include <rte_debug.h>
#include <rte_devargs.h>
#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_ether.h>
#include <rte_flow.h>
#include <rte_hash.h>
#include <rte_interrupts.h>
#include <rte_ip.h>
#include <rte_launch.h>
#include <rte_lcore.h>
#include <rte_log.h>
#include <rte_malloc.h>
#include <rte_mbuf.h>
#include <rte_memcpy.h>
#include <rte_memory.h>
#include <rte_mempool.h>
#include <rte_per_lcore.h>
#include <rte_prefetch.h>
#include <rte_random.h>
#include <rte_regexdev.h>
#include <rte_ring_core.h>
#include <rte_ring_elem.h>
#include <rte_spinlock.h>
#include <rte_string_fns.h>
#include <rte_tcp.h>
#include <rte_version.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/queue.h>
#include <sys/socket.h>
#include <termios.h>
#include <unistd.h>

#define ETHERNET_PORTID 0
struct rte_mempool *mbuf_pool;

#define EXPLIB_OUTPUT true
#define MAX_WORKER_THREADS 32
#define MAX_PKT_BURST 64
#define MEMPOOL_CACHE_SIZE 511
#define NB_MBUF 2047
#define RTE_TEST_RX_DESC_DEFAULT 256
#define RTE_TEST_TX_DESC_DEFAULT 256
#define PORT_MTU 1500

// Hyperscan
#define HS_ENABLED 0
#define HS_RULES_CACHE_PATH "/tmp/"
#define HS_RULES_FILES_PATH "/tmp/regex-test/rules.hs"
#define HS_EXPRESSION_FLAGS                                                    \
  HS_FLAG_PREFILTER | HS_FLAG_DOTALL | HS_FLAG_SINGLEMATCH
// PKT FORWARDING
#define FORWARDING_MODE_DEFAULT 0
#define FORCE_FULL_RGX_DQ_DEFAULT 0
// REGEX
#define RGX_ENABLED 1
#define RGX_RULES_FILES_PATH "/tmp/regex-test/rules.rof2.binary"
#define RGX_MATCH_MODE                                                         \
  RTE_REGEX_OPS_REQ_STOP_ON_MATCH_F // regex stops scanning and returns the
                                    // first match (alt. 0 or
                                    // RTE_REGEX_OPS_REQ_MATCH_HIGH_PRIORITY_F)
#define RGX_SUBSET_CNT 1
#define RGX_SUBSET_EXAMPLE_ARG "0.1:0.9"
#define RGX_NB_DESC 256
// REGEX stats
#define RGX_STATS_BUCKET_SIZE 4

// Application arguments structure
struct app_args {
  bool help;
  bool explib_out;
  bool hs_enabled;
  char hs_rules_path[256];
  uint32_t hs_flags;
  bool rgx_enabled;
  uint32_t rgx_num_of_match_mode;
  char rgx_rules_path[256];
  uint32_t rgx_descriptors;
  uint32_t rgx_stats_histogram_bucket_size;
  uint32_t rgx_stats_histogram_bucket_cnt; // derived property
  uint32_t rgx_subset_cnt; // derived property
  uint32_t port_mtu;
  uint32_t port_mp_size;
  uint32_t port_mp_cache_size;
  uint32_t port_rx_descriptors;
  uint32_t port_tx_descriptors;
  uint32_t port_burst_size;
  uint32_t forwarding_mode;
};

// Global structure to hold the parsed/default values
struct app_args g_app_args = {
    .help = false,
    .explib_out = EXPLIB_OUTPUT,
    .hs_enabled = HS_ENABLED,
    .hs_rules_path = HS_RULES_FILES_PATH,
    .hs_flags = HS_EXPRESSION_FLAGS,
    .rgx_enabled = RGX_ENABLED,
    .rgx_num_of_match_mode = RGX_MATCH_MODE,
    .rgx_rules_path = RGX_RULES_FILES_PATH,
    .rgx_descriptors = RGX_NB_DESC,
    .rgx_stats_histogram_bucket_size = RGX_STATS_BUCKET_SIZE,
    .rgx_stats_histogram_bucket_cnt = 0,
    .rgx_subset_cnt = RGX_SUBSET_CNT,
    .port_mtu = PORT_MTU,
    .port_mp_size = NB_MBUF,
    .port_mp_cache_size = MEMPOOL_CACHE_SIZE,
    .port_rx_descriptors = RTE_TEST_RX_DESC_DEFAULT,
    .port_tx_descriptors = RTE_TEST_TX_DESC_DEFAULT,
    .port_burst_size = MAX_PKT_BURST,
    .forwarding_mode = FORWARDING_MODE_DEFAULT,
};

// Enum for argument parsing
enum app_args_enum {
  ARG_HELP,
  ARG_EXPLIB_OUTPUT_DISABLED,
  ARG_HS_ENABLED,
  ARG_HS_RULES_PATH,
  ARG_HS_FLAG_CASELESS,
  ARG_HS_FLAG_DOTALL,
  ARG_HS_FLAG_MULTILINE,
  ARG_HS_FLAG_SINGLEMATCH,
  ARG_HS_FLAG_ALLOWEMPTY,
  ARG_HS_FLAG_UTF8,
  ARG_HS_FLAG_UCP,
  ARG_HS_FLAG_PREFILTER,
  ARG_HS_FLAG_SOM_LEFTMOST,
  ARG_HS_FLAG_COMBINATION,
  ARG_HS_FLAG_QUIET,
  ARG_RGX_ENABLED,
  ARG_RGX_NUM_OF_MATCH_MODE,
  ARG_RGX_RULES_PATH,
  ARG_RGX_DESCRIPTORS,
  ARG_RGX_STATS_HISTOGRAM_BUCKET_SIZE,
  ARG_RGX_RULE_SUBSET_RATIO,
  ARG_PORT_MTU,
  ARG_PORT_MP_SIZE,
  ARG_PORT_MP_CACHE_SIZE,
  ARG_PORT_RX_DESCRIPTORS,
  ARG_PORT_TX_DESCRIPTORS,
  ARG_PORT_BURST_SIZE,
  ARG_FORWARDING_MODE,
  ARG_FORCE_FULL_RGX_DQ
};

// Usage function to display help
static void usage(const char *prog_name);

// Function to parse arguments
static void args_parse(int argc, char **argv);

// Function to print current application arguments
static void print_app_args();

struct qp_params {
  uint32_t total_enqueue;
  uint32_t total_dequeue;
  uint32_t total_matches;
  struct rte_regex_ops **ops;
  char *buf;
  uint64_t start;
  uint64_t cycles;
};

struct qps_per_lcore {
  unsigned int lcore_id;
  int socket;
  uint16_t qp_id_base;
  uint16_t nb_qps;
};

struct regex_stats_burst {
  uint32_t burst_size; // e.g. histogram of burst sizes, covers less than this
                       // burst size but more than the previous burst size
  uint64_t enq_burst_cnt;
  uint64_t enq_burst_pkts_cnt;
  uint64_t deq_burst_cnt;
  uint64_t deq_burst_pkt_cnt;
  uint64_t deq_RTT_total_us;
  uint64_t deq_RTT_total_cycles;
  uint64_t matches;
};

struct regex_conf {
  uint32_t match_mode;
  uint32_t nb_qps;
  uint16_t qp_id_base;
  struct rte_regex_ops **ops;
  struct regex_stats_burst *stats;
};

struct hs_conf {
  hs_database_t *db;
  hs_scratch_t *scratch;
  struct hs_stats *stats;
};

struct lcore_stats {
  uint64_t wasted_cycles;
  uint64_t useful_cycles;
};

struct app_stats {
  struct regex_stats_burst *regex_stats;
  struct hs_stats *hs_stats;
  struct lcore_stats *lcore_stats;
};

typedef struct shared_vars_ {
  uint16_t port_id;
  uint16_t total_queues;
  rte_atomic16_t wq_id; // worker queue id - incrementing on launch
  uint16_t regex_dev_id;
  struct regex_conf *rgxc_arr;
  hs_database_t *hs_db;
  hs_scratch_t *hs_scratch[MAX_WORKER_THREADS];
  struct app_stats *stats[MAX_WORKER_THREADS];
} shared_vars;

typedef struct lcore_vars_ {
  uint16_t pid;
  uint16_t qid; // queue id
  uint16_t rid; // regex device id
  struct lcore_stats *lcore_stats;
  struct regex_conf *rgxc;
  struct hs_conf *hsc;
} lcore_vars;

static void init_port(int port_id, struct rte_mempool *mbuf_pool,
                      uint16_t nb_rx_queues, uint16_t nb_tx_queues,
                      uint16_t mtu_size);

// static struct app_stats *worker_rx_pkts(lcore_vars *lv);

static int worker_run(void *data);
