
/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright(c) 2010-2014 Intel Corporation
 */

// Simple proxy that listens to two ports and forwards packets from one port to
// another

#include "regex-test.h"
#include "helpers.h"
#include "hs_common.h"
#include "rgx_stats.h"
#include "util-hs.h"
#include <assert.h>
#include <bits/getopt_ext.h>
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
#define TX_PORTID 1

struct rte_mempool *mbuf_pool;

#define RSS_HKEY_LEN 40
// General purpose RSS key for symmetric bidirectional flow distribution
uint8_t rss_hkey[] = {0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A,
                      0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A,
                      0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A,
                      0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A,
                      0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A, 0x6D, 0x5A};

// Calculates the closest multiple of y from x
#define ROUNDUP(x, y) ((((x) + ((y)-1)) / (y)) * (y))

// Enum for argument parsing

// Usage function to display help
static void usage(const char *prog_name) {
  rte_log(
      RTE_LOG_NOTICE, RTE_LOGTYPE_USER1,
      "%s [EAL options] --\n"
      " --help: Display this help message\n"
      " --explib_disabled: Disable explib output (RESULT... -) (default: %s)\n"
      // Hyperscan
      "\n Hyperscan parameters\n"
      " --hs_enabled: Enable Hyperscan processing (default: %d)\n"
      " --hs_rules_path PATH: Path to Hyperscan rules file (default: %s)\n"
      "\n Hyperscan flags are set from scratch when at least one flag is "
      "specified,\n"
      " default flags: %s\n"
      " --hs_flag_caseless: Hyperscan caseless matching flag\n"
      " --hs_flag_dotall: Hyperscan dot matches newline flag\n"
      " --hs_flag_multiline: Hyperscan multi-line matching flag\n"
      " --hs_flag_singlematch: Hyperscan single match only flag\n"
      " --hs_flag_allowempty: Hyperscan allow empty matches flag\n"
      " --hs_flag_utf8: Hyperscan UTF-8 mode flag\n"
      " --hs_flag_ucp: Hyperscan Unicode property support flag\n"
      " --hs_flag_prefilter: Hyperscan prefiltering mode flag\n"
      " --hs_flag_som_leftmost: Hyperscan start of match reporting flag\n"
      " --hs_flag_combination: Hyperscan logical combination flag\n"
      " --hs_flag_quiet: Hyperscan quiet mode flag\n"
      // DPDK HW Regex engine
      "\n DPDK HW Regex engine parameters\n"
      " --rgx_enabled: Enable regex processing (default: %d)\n"
      " --rgx_num_of_match_mode N: Regex match mode (default: %d) 0 - "
      "none, 1 - RTE_REGEX_OPS_REQ_STOP_ON_MATCH_F, 2 - "
      "RTE_REGEX_OPS_REQ_MATCH_HIGH_PRIORITY_F\n"
      " --rgx_rules_path PATH: Path to regex rules file (default: %s)\n"
      " --rgx_descriptors N: Number of regex descriptors (default: %d)\n"
      " --rgx_rule_subset_ratio string: How are rules separated into subsets in the current ruleset - mainly to derive the overall subset count (default number of subsets: %d argument format: %s)\n"
      // Port settings
      "\n DPDK port parameters\n"
      " --port_mtu N: Port MTU size (default: %d)\n"
      " --port_mp_size N: Port mempool size (default: %d) - calculated as this "
      "size times (nb_workers + 1)\n"
      " --port_mp_cache_size N: Port mempool cache size (default: %d)\n"
      " --port_rx_descriptors N: Number of RX descriptors (default: %d)\n"
      " --port_tx_descriptors N: Number of TX descriptors (default: %d)\n"
      " --port_burst_size N: Port burst size (default: %d)\n"
      " --forwarding_mode N: Forwarding mode. 0 for no forwarding, 1 for "
      "sending back to the rx port, 2 to send to the host (default %u)\n",
      // ARGS
      prog_name, EXPLIB_OUTPUT ? "enabled" : "disabled", HS_ENABLED,
      HS_RULES_FILES_PATH, hs_log_expression_flags(HS_EXPRESSION_FLAGS),
      RGX_ENABLED,
      RGX_MATCH_MODE == RTE_REGEX_OPS_REQ_STOP_ON_MATCH_F         ? 1
      : RGX_MATCH_MODE == RTE_REGEX_OPS_REQ_MATCH_HIGH_PRIORITY_F ? 2
                                                                  : 0,
      RGX_RULES_FILES_PATH, RGX_NB_DESC, RGX_SUBSET_CNT, RGX_SUBSET_EXAMPLE_ARG,
      PORT_MTU, NB_MBUF, MEMPOOL_CACHE_SIZE,
      RTE_TEST_RX_DESC_DEFAULT, RTE_TEST_TX_DESC_DEFAULT, MAX_PKT_BURST,
      FORWARDING_MODE_DEFAULT);
}

static uint32_t args_parse_subset_ratios(char *s) {
    int i = 1;
    for (; s[i]; s[i]==':' ? i++ : *s++);
    return i;
}

// Function to parse arguments
static void args_parse(int argc, char **argv) {
  static struct option lgopts[] = {
      {"help", no_argument, 0, ARG_HELP},
      {"explib_disabled", no_argument, 0, ARG_HELP},
      // Hyperscan parameters
      {"hs_enabled", required_argument, 0, ARG_HS_ENABLED},
      {"hs_rules_path", required_argument, 0, ARG_HS_RULES_PATH},
      {"hs_flag_caseless", no_argument, 0, ARG_HS_FLAG_CASELESS},
      {"hs_flag_dotall", no_argument, 0, ARG_HS_FLAG_DOTALL},
      {"hs_flag_multiline", no_argument, 0, ARG_HS_FLAG_MULTILINE},
      {"hs_flag_singlematch", no_argument, 0, ARG_HS_FLAG_SINGLEMATCH},
      {"hs_flag_allowempty", no_argument, 0, ARG_HS_FLAG_ALLOWEMPTY},
      {"hs_flag_utf8", no_argument, 0, ARG_HS_FLAG_UTF8},
      {"hs_flag_ucp", no_argument, 0, ARG_HS_FLAG_UCP},
      {"hs_flag_prefilter", no_argument, 0, ARG_HS_FLAG_PREFILTER},
      {"hs_flag_som_leftmost", no_argument, 0, ARG_HS_FLAG_SOM_LEFTMOST},
      {"hs_flag_combination", no_argument, 0, ARG_HS_FLAG_COMBINATION},
      {"hs_flag_quiet", no_argument, 0, ARG_HS_FLAG_QUIET},
      // Regex engine
      {"rgx_enabled", required_argument, 0, ARG_RGX_ENABLED},
      {"rgx_num_of_match_mode", required_argument, 0,
       ARG_RGX_NUM_OF_MATCH_MODE},
      {"rgx_rules_path", required_argument, 0, ARG_RGX_RULES_PATH},
      {"rgx_descriptors", required_argument, 0, ARG_RGX_DESCRIPTORS},
      {"rgx_stats_histogram_bucket_size", required_argument, 0,
       ARG_RGX_STATS_HISTOGRAM_BUCKET_SIZE},
      {"rgx_rule_subset_ratio", required_argument, 0, ARG_RGX_RULE_SUBSET_RATIO},
      // Port settings
      {"port_mtu", required_argument, 0, ARG_PORT_MTU},
      {"port_mp_size", required_argument, 0, ARG_PORT_MP_SIZE},
      {"port_mp_cache_size", required_argument, 0, ARG_PORT_MP_CACHE_SIZE},
      {"port_rx_descriptors", required_argument, 0, ARG_PORT_RX_DESCRIPTORS},
      {"port_tx_descriptors", required_argument, 0, ARG_PORT_TX_DESCRIPTORS},
      {"port_burst_size", required_argument, 0, ARG_PORT_BURST_SIZE},
      {"forwarding_mode", required_argument, 0, ARG_FORWARDING_MODE},
      {NULL, 0, 0, 0}};

  bool hs_flag_specified = false;
  int opt, option_index;
  while ((opt = getopt_long(argc, argv, "", lgopts, &option_index)) != -1) {
    // If a Hyperscan flag is specified for the first time, reset hs_flags
    if (!hs_flag_specified &&
        (opt == ARG_HS_FLAG_CASELESS || opt == ARG_HS_FLAG_DOTALL ||
         opt == ARG_HS_FLAG_MULTILINE || opt == ARG_HS_FLAG_SINGLEMATCH ||
         opt == ARG_HS_FLAG_ALLOWEMPTY || opt == ARG_HS_FLAG_UTF8 ||
         opt == ARG_HS_FLAG_UCP || opt == ARG_HS_FLAG_PREFILTER ||
         opt == ARG_HS_FLAG_SOM_LEFTMOST || opt == ARG_HS_FLAG_COMBINATION ||
         opt == ARG_HS_FLAG_QUIET)) {
      g_app_args.hs_flags = 0;
      hs_flag_specified = true;
    }

    switch (opt) {
    case ARG_HELP:
      g_app_args.help = true;
      break;
    case ARG_EXPLIB_OUTPUT_DISABLED:
      g_app_args.explib_out = false;
      break;
    case ARG_HS_ENABLED: {
      int32_t hs_enabled = atoi(optarg);
      if (hs_enabled == 0)
        g_app_args.hs_enabled = false;
      else
        g_app_args.hs_enabled = true;
    } break;
    case ARG_HS_RULES_PATH:
      strncpy(g_app_args.hs_rules_path, optarg,
              sizeof(g_app_args.hs_rules_path) - 1);
      g_app_args.hs_rules_path[sizeof(g_app_args.hs_rules_path) - 1] = '\0';
      break;
    case ARG_HS_FLAG_CASELESS:
      g_app_args.hs_flags |= HS_FLAG_CASELESS;
      break;
    case ARG_HS_FLAG_DOTALL:
      g_app_args.hs_flags |= HS_FLAG_DOTALL;
      break;
    case ARG_HS_FLAG_MULTILINE:
      g_app_args.hs_flags |= HS_FLAG_MULTILINE;
      break;
    case ARG_HS_FLAG_SINGLEMATCH:
      g_app_args.hs_flags |= HS_FLAG_SINGLEMATCH;
      break;
    case ARG_HS_FLAG_ALLOWEMPTY:
      g_app_args.hs_flags |= HS_FLAG_ALLOWEMPTY;
      break;
    case ARG_HS_FLAG_UTF8:
      g_app_args.hs_flags |= HS_FLAG_UTF8;
      break;
    case ARG_HS_FLAG_UCP:
      g_app_args.hs_flags |= HS_FLAG_UCP;
      break;
    case ARG_HS_FLAG_PREFILTER:
      g_app_args.hs_flags |= HS_FLAG_PREFILTER;
      break;
    case ARG_HS_FLAG_SOM_LEFTMOST:
      g_app_args.hs_flags |= HS_FLAG_SOM_LEFTMOST;
      break;
    case ARG_HS_FLAG_COMBINATION:
      g_app_args.hs_flags |= HS_FLAG_COMBINATION;
      break;
    case ARG_HS_FLAG_QUIET:
      g_app_args.hs_flags |= HS_FLAG_QUIET;
      break;
    case ARG_RGX_ENABLED: {
      int32_t rgx_enabled = atoi(optarg);
      if (rgx_enabled == 0)
        g_app_args.rgx_enabled = false;
      else
        g_app_args.rgx_enabled = true;
    } break;
    case ARG_RGX_NUM_OF_MATCH_MODE:
      g_app_args.rgx_num_of_match_mode = atoi(optarg);
      if (g_app_args.rgx_num_of_match_mode < 0 ||
          g_app_args.rgx_num_of_match_mode > 2) {
        rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER1,
                "Invalid value for rgx_num_of_match_mode\n");
        usage(argv[0]);
        exit(EXIT_FAILURE);
      }

      if (g_app_args.rgx_num_of_match_mode == 1)
        g_app_args.rgx_num_of_match_mode = RTE_REGEX_OPS_REQ_STOP_ON_MATCH_F;
      else if (g_app_args.rgx_num_of_match_mode == 2)
        g_app_args.rgx_num_of_match_mode =
            RTE_REGEX_OPS_REQ_MATCH_HIGH_PRIORITY_F;

      break;
    case ARG_RGX_RULES_PATH:
      strncpy(g_app_args.rgx_rules_path, optarg,
              sizeof(g_app_args.rgx_rules_path) - 1);
      g_app_args.rgx_rules_path[sizeof(g_app_args.rgx_rules_path) - 1] = '\0';
      break;
    case ARG_RGX_DESCRIPTORS:
      g_app_args.rgx_descriptors = atoi(optarg);
      break;
    case ARG_RGX_STATS_HISTOGRAM_BUCKET_SIZE:
      g_app_args.rgx_stats_histogram_bucket_size = atoi(optarg);
      break;
    case ARG_RGX_RULE_SUBSET_RATIO:
      g_app_args.rgx_subset_cnt = args_parse_subset_ratios(optarg);
      break;
    case ARG_PORT_MTU:
      g_app_args.port_mtu = atoi(optarg);
      break;
    case ARG_PORT_MP_SIZE:
      g_app_args.port_mp_size = atoi(optarg);
      break;
    case ARG_PORT_MP_CACHE_SIZE:
      g_app_args.port_mp_cache_size = atoi(optarg);
      break;
    case ARG_PORT_RX_DESCRIPTORS:
      g_app_args.port_rx_descriptors = atoi(optarg);
      break;
    case ARG_PORT_TX_DESCRIPTORS:
      g_app_args.port_tx_descriptors = atoi(optarg);
      break;
    case ARG_PORT_BURST_SIZE:
      g_app_args.port_burst_size = atoi(optarg);
      break;
    case ARG_FORWARDING_MODE: {
      g_app_args.forwarding_mode = atoi(optarg);
      break;
    }
    default:
      usage(argv[0]);
      exit(EXIT_FAILURE);
    }
  }

  if (g_app_args.help) {
    usage(argv[0]);
    exit(EXIT_SUCCESS);
  }

  g_app_args.rgx_stats_histogram_bucket_cnt =
      g_app_args.port_burst_size / g_app_args.rgx_stats_histogram_bucket_size;
}

// Function to print current application arguments
static void print_app_args() {
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Application Arguments:\n");
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Help: %s\n",
          g_app_args.help ? "true" : "false");
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Explib output enabled: %s\n",
          g_app_args.explib_out ? "enabled" : "disabled");
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Hyperscan enabled: %s\n",
          g_app_args.hs_enabled ? "true" : "false");
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Hyperscan rules path: %s\n",
          g_app_args.hs_rules_path);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Hyperscan flags: %s\n",
          hs_log_expression_flags(g_app_args.hs_flags));
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Regex enabled: %s\n",
          g_app_args.rgx_enabled ? "true" : "false");
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Regex number of match mode: %u\n",
          g_app_args.rgx_num_of_match_mode == RTE_REGEX_OPS_REQ_STOP_ON_MATCH_F
              ? 1
          : g_app_args.rgx_num_of_match_mode ==
                  RTE_REGEX_OPS_REQ_MATCH_HIGH_PRIORITY_F
              ? 2
              : 0);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Regex rules path: %s\n",
          g_app_args.rgx_rules_path);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Regex descriptors: %u\n",
          g_app_args.rgx_descriptors);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1,
          " Regex stats histogram bucket size: %u\n",
          g_app_args.rgx_stats_histogram_bucket_size);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1,
          " Regex subset count: %u\n", g_app_args.rgx_subset_cnt);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port MTU: %u\n",
          g_app_args.port_mtu);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port mempool size: %u\n",
          g_app_args.port_mp_size);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port mempool cache size: %u\n",
          g_app_args.port_mp_cache_size);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port RX descriptors: %u\n",
          g_app_args.port_rx_descriptors);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port TX descriptors: %u\n",
          g_app_args.port_tx_descriptors);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port burst size: %u\n",
          g_app_args.port_burst_size);
  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, " Port forwarding mode: %d\n",
          g_app_args.forwarding_mode);
}

static volatile bool force_quit;

static int PortValidateMTU(uint16_t mtu,
                           const struct rte_eth_dev_info *dev_info) {
  if (mtu > dev_info->max_mtu || mtu < dev_info->min_mtu) {
    rte_panic("MTU (%u) is out of port bounds - min %u max %u\n", mtu,
              dev_info->min_mtu, dev_info->max_mtu);
  }

#if RTE_VERSION < RTE_VERSION_NUM(21, 11, 0, 0)
  // check if jumbo frames are set and are available
  if (mtu > RTE_ETHER_MAX_LEN &&
      !(dev_info->rx_offload_capa & RTE_ETH_RX_OFFLOAD_RSS_HASH)) {
    rte_panic("jumbo frames not supported, set MTU to 1500");
  }
#endif

  return 0;
}

static void DeviceSetMTU(struct rte_eth_conf *port_conf, uint16_t mtu) {
#if RTE_VERSION >= RTE_VERSION_NUM(21, 11, 0, 0)
  port_conf->rxmode.mtu = mtu;
#else
  port_conf->rxmode.max_rx_pkt_len = mtu;
  if (mtu > RTE_ETHER_MAX_LEN) {
    port_conf->rxmode.offloads |= RTE_ETH_RX_OFFLOAD_RSS_HASH;
  }
#endif
}

static void init_port(int port_id, struct rte_mempool *mbuf_pool,
                      uint16_t nb_rx_queues, uint16_t nb_tx_queues,
                      uint16_t mtu) {
  int ret;
  static struct rte_eth_conf port_conf = (struct rte_eth_conf){
      .rxmode =
          {
              .mq_mode = RTE_ETH_MQ_RX_NONE,
              .offloads = 0,
          },
      .txmode =
          {
              .mq_mode = RTE_ETH_MQ_TX_NONE,
              .offloads =
                  RTE_ETH_TX_OFFLOAD_IPV4_CKSUM | RTE_ETH_TX_OFFLOAD_TCP_CKSUM,
          },
  };
  struct rte_eth_txconf txq_conf;
  struct rte_eth_rxconf rxq_conf;
  struct rte_eth_dev_info dev_info;

  ret = rte_eth_dev_info_get(port_id, &dev_info);
  if (ret != 0)
    rte_exit(EXIT_FAILURE, "Error during getting device (port %u) info: %s\n",
             port_id, strerror(-ret));

  if (PortValidateMTU(mtu, &dev_info) == 0)
    DeviceSetMTU(&port_conf, mtu);

  // test out the capacities of the nics
  if (dev_info.tx_offload_capa & RTE_ETH_TX_OFFLOAD_MBUF_FAST_FREE) {
    port_conf.txmode.offloads |= RTE_ETH_TX_OFFLOAD_MBUF_FAST_FREE;
  }
  if (!(dev_info.rx_offload_capa & RTE_ETH_RX_OFFLOAD_RSS_HASH)) {
    rte_exit(EXIT_FAILURE, "The device does not support RSS, panicking\n");
  } else {
    port_conf.rxmode.mq_mode = RTE_ETH_MQ_RX_RSS;
    port_conf.rx_adv_conf.rss_conf =
        (struct rte_eth_rss_conf){.rss_key = rss_hkey,
                                  .rss_key_len = RSS_HKEY_LEN,
                                  .rss_hf = RTE_ETH_RSS_IP};
  }
  port_conf.txmode.offloads &= dev_info.tx_offload_capa;
  printf(":: initializing port: %d\n", port_id);
  ret = rte_eth_dev_configure(port_id, nb_rx_queues, nb_tx_queues, &port_conf);
  if (ret < 0) {
    rte_exit(EXIT_FAILURE, ":: cannot configure device: err=%d, port=%u\n", ret,
             port_id);
  }

  ret = rte_eth_dev_set_mtu(port_id, mtu);
  if (ret < 0) {
    rte_panic("cannot set MTU: err=%d, port=%u\n", ret, port_id);
  }

  rxq_conf = dev_info.default_rxconf;
  rxq_conf.offloads = port_conf.rxmode.offloads;
  /* >8 End of ethernet port configured with default settings. */

  /* Configuring number of RX and TX queues connected to single port. 8< */
  for (int i = 0; i < nb_rx_queues; i++) {
    ret = rte_eth_rx_queue_setup(port_id, i, g_app_args.port_rx_descriptors,
                                 rte_eth_dev_socket_id(port_id), &rxq_conf,
                                 mbuf_pool);
    if (ret < 0) {
      rte_exit(EXIT_FAILURE, ":: Rx queue setup failed: err=%d, port=%u\n", ret,
               port_id);
    }
  }

  txq_conf = dev_info.default_txconf;
  txq_conf.offloads = port_conf.txmode.offloads;
  for (int i = 0; i < nb_tx_queues; i++) {
    ret = rte_eth_tx_queue_setup(port_id, i, g_app_args.port_tx_descriptors,
                                 rte_eth_dev_socket_id(port_id), &txq_conf);
    if (ret < 0) {
      rte_exit(EXIT_FAILURE, ":: Tx queue setup failed: err=%d, port=%u\n", ret,
               port_id);
    }
  }
  /* >8 End of Configuring RX and TX queues connected to single port. */

  /* Setting the RX port to promiscuous mode. 8< */
  ret = rte_eth_promiscuous_enable(port_id);
  if (ret != 0)
    rte_exit(EXIT_FAILURE,
             ":: promiscuous mode enable failed: err=%s, port=%u\n",
             rte_strerror(-ret), port_id);
  /* >8 End of setting the RX port to promiscuous mode. */

  /* Starting the port. 8< */
  ret = rte_eth_dev_start(port_id);
  if (ret < 0) {
    rte_exit(EXIT_FAILURE, "rte_eth_dev_start:err=%d, port=%u\n", ret, port_id);
  }
  /* >8 End of starting the port. */
  printf(":: initializing port: %d done\n", port_id);
}

static void signal_handler(int signum) {
  if (signum == SIGINT || signum == SIGTERM) {
    printf("\n\nSignal %d received, preparing to exit...\n", signum);
    force_quit = true;
  }
}

static bool regexdev_selftest_passed(uint16_t rid) {
  if (rte_regexdev_selftest(rid) == 0) {
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "REGEX selftest passed\n");
    return true;
  } else if (rte_regexdev_selftest(rid) == -ENOTSUP) {
    rte_log(RTE_LOG_WARNING, RTE_LOGTYPE_USER2,
            "REGEX selftest not supported\n");
    return true;
  } else {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2, "REGEX selftest failed\n");
    return false;
  }
}

// This function could also allocate a sequential memory block for all ops then
// assign chunks of the array to ops But it threw segfault/EAL: Invalid memory
// when stopping the regex device Using the single block of memory seem to
// improve performance a little
static struct rte_regex_ops **regexdev_allocate_ops(uint16_t ops_cnt,
                                                    u_int16_t max_matches_cnt) {
  struct rte_regex_ops **ops =
      rte_calloc("regex ops", ops_cnt, sizeof(*ops), 0);
  if (ops == NULL) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
            "Error, can't allocate memory for ops\n");
    return NULL;
  }

  for (int i = 0; i < ops_cnt; i++) {
    ops[i] = rte_calloc("regex op", 1,
                        sizeof(*ops[0]) +
                            (1 + max_matches_cnt) * sizeof(ops[0]->matches[0]),
                        0);
    if (ops[i] == NULL) {
      rte_panic("NULL calloc");
    }
  }

  return ops;
}

static void regexdev_deallocate_ops(struct rte_regex_ops **ops) {
  if (ops != NULL) {
    if (ops[0] != NULL)
      rte_free(ops[0]); // just free the first elem because the whole array of
                        // ops is allocated in one go
    rte_free(ops);
  }
  ops = NULL;
}

static inline void update_cycles_counts(bool wasted, uint64_t loop_start_ts,
                                        struct lcore_stats *s) {
  uint64_t loop_cycles_delta = rte_rdtsc_precise() - loop_start_ts;
  if (wasted) {
    s->wasted_cycles += loop_cycles_delta;
  } else {
    s->useful_cycles += loop_cycles_delta;
  }
}

static inline void forward_or_free_pkts(struct rte_mbuf **pkts_burst,
                                        uint16_t nb_to_tx, uint16_t qid) {
  if (g_app_args.forwarding_mode > 0) {
    rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Forwarding pkts\n");
    uint16_t dst_port =
        g_app_args.forwarding_mode == 1 ? ETHERNET_PORTID : TX_PORTID;
    uint16_t nb_tx = rte_eth_tx_burst(dst_port, qid, pkts_burst, nb_to_tx);
    rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Forwarded %d of %d pkts\n", nb_tx,
            nb_to_tx);
    // TODO Maybe keep track of non-txd pkts?
    uint16_t pkts_left = nb_to_tx - nb_tx;
    rte_pktmbuf_free_bulk(pkts_burst + nb_tx, pkts_left);
  } else {
    rte_pktmbuf_free_bulk(pkts_burst, nb_to_tx);
  }
}

static struct app_stats *worker_rx_pkts(lcore_vars *lv) {
  // Regex vars
  uint16_t rgx_enqd = 0;
  uint16_t rgx_dqd = 0;
  // Port vars
  uint64_t pkts_rx = 0;
  struct rte_mbuf **pkts_burst = NULL;
  struct rte_mbuf **rgx_dqd_collector = NULL;

  pkts_burst = rte_calloc("pkts_burst", g_app_args.port_burst_size,
                          sizeof(*pkts_burst), 0);
  if (pkts_burst == NULL) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
            "Error, can't allocate memory for pkts_burst\n");
    goto end;
  }
  rgx_dqd_collector = rte_calloc("dqd_rgx_pkts", g_app_args.port_burst_size,
                                 sizeof(struct rte_mbuf *), 0);

  if (rgx_dqd_collector == NULL) {
    rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
            "Error, can't allocate memory for rgx_dqd_collector\n");
    rte_free(pkts_burst);
    goto end;
  }

  rte_eth_stats_reset(lv->pid);
  rte_eth_xstats_reset(lv->pid);

  rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
          "lcore %d\t port queue %d\tready to receive pkts\n", rte_lcore_id(),
          lv->qid);

  bool loop_wasted = true;

  uint32_t group0_selector = 1;

  while (!force_quit) {
    loop_wasted = true;
    uint64_t loop_start_ts = rte_rdtsc_precise();
    uint16_t nb_rx = rte_eth_rx_burst(lv->pid, lv->qid, pkts_burst,
                                      g_app_args.port_burst_size);
    if (nb_rx > 0) {
      loop_wasted = false;
      // Process received packets
      rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "lcore %d\tnb_rx %d\n",
              rte_lcore_id(), nb_rx);

      if (!lv->rgxc && !lv->hsc) {
        forward_or_free_pkts(pkts_burst, nb_rx, lv->qid);
        goto continue_loop;
      }

      for (int i = 0; i < nb_rx; i++) {
        struct rte_mbuf *pkt = pkts_burst[i];
        struct rte_ether_hdr *eth_hdr;
        eth_hdr = rte_pktmbuf_mtod(pkt, struct rte_ether_hdr *);
        static const struct rte_ether_addr desired_src_mac = {{0x6C, 0xB3, 0x11, 0x21, 0xAD, 0xB1}};
        static const struct rte_ether_addr desired_dst_mac = {{0x00, 0x00, 0x00, 0x00, 0x00, 0x00}};

        if (rte_is_same_ether_addr(&eth_hdr->src_addr, &desired_src_mac) && rte_is_same_ether_addr(&eth_hdr->dst_addr, &desired_dst_mac)) {
            // Swap the MAC addresses
            struct rte_ether_addr tmp_mac;
            rte_ether_addr_copy(&eth_hdr->src_addr, &tmp_mac);
            rte_ether_addr_copy(&eth_hdr->dst_addr, &eth_hdr->src_addr);
            rte_ether_addr_copy(&tmp_mac, &eth_hdr->dst_addr);
        }


        if (lv->hsc) {
          HSCallBackCtx ctx = {0};
          rte_log(
              RTE_LOG_INFO, RTE_LOGTYPE_USER2,
              "lcore %d hs_db %p hs_sp %p pktdata %p pkt data len %u cb %p\n",
              rte_lcore_id(), lv->hsc->db, lv->hsc->scratch,
              rte_pktmbuf_mtod(pkt, const char *), rte_pktmbuf_data_len(pkt),
              hs_match_cb);
          uint64_t t1 = rte_rdtsc_precise();
          int ret = hs_scan(lv->hsc->db, rte_pktmbuf_mtod(pkt, const char *),
                            rte_pktmbuf_data_len(pkt), 0, lv->hsc->scratch,
                            hs_match_cb, (void *)&ctx);
          if (ret != HS_SUCCESS) {
            rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
                    "hs_scan failed with an error %d - %s\n", ret,
                    rte_strerror(-ret)); // hs_error_message(ret));
          } else {
            uint64_t t2 = rte_rdtsc_precise();
            const uint64_t ticks_per_us = rte_get_tsc_hz() / 1000000;
            if (ticks_per_us != 0) {
              if (lv->hsc->stats == NULL)
                rte_panic("lv->hsc->stats is NULL");
              lv->hsc->stats->total_scans_cycles += (t2 - t1);
              lv->hsc->stats->total_scans_us += (t2 - t1) / ticks_per_us;
              lv->hsc->stats->total_scans++;
            } else {
              rte_panic("why zero");
            }
          }

          if (ctx.match_count > 0) {
            lv->hsc->stats->total_matches += ctx.match_count;
            rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER2,
                    "lcore %d pkt %" PRIu64 " matched %u patterns\n",
                    rte_lcore_id(), pkts_rx, ctx.match_count);
          }
        }

        if (lv->rgxc) {
          rte_log(
              RTE_LOG_INFO, RTE_LOGTYPE_USER2,
              "lcore %u\tpkt %" PRIu64 "\tpktlen %d\tdatalen %d\tdatalen_fun "
              "%d\tdataoffset %d\trte_pktmbuf_mtod 0x%ld\tdataoffset_calced "
              "%lu\n",
              rte_lcore_id(), pkts_rx, pkt->pkt_len, pkt->data_len,
              rte_pktmbuf_data_len(pkt), pkt->data_off,
              rte_pktmbuf_mtod(pkt, uintptr_t),
              rte_pktmbuf_mtod(pkt, uintptr_t) - (uintptr_t)pkt);

          lv->rgxc->ops[i]->mbuf = pkt;
          pkt->tx_offload = rte_rdtsc_precise(); // tx_offload is actually used
                                                 // as a cycle counter
          lv->rgxc->ops[i]->user_ptr = pkt;
          if (g_app_args.rgx_subset_cnt > 1) {
            lv->rgxc->ops[i]->group_id0 = group0_selector;
            group0_selector++;
            if (group0_selector > g_app_args.rgx_subset_cnt) {
              group0_selector = 1;
            }
          } else {
            lv->rgxc->ops[i]->group_id0 = 1;
          }
          lv->rgxc->ops[i]->req_flags |= lv->rgxc->match_mode;
          pkts_rx++;

          rte_log(
              RTE_LOG_INFO, RTE_LOGTYPE_USER1,
              "lcore %d\t preparing mbuf %p to the matcher with cycles %lu\n",
              rte_lcore_id(), lv->rgxc->ops[i]->mbuf,
              lv->rgxc->ops[i]->mbuf->tx_offload);
        }
      }

      if (lv->hsc) {
        forward_or_free_pkts(pkts_burst, nb_rx, lv->qid);
        goto continue_loop;
      }

      if (lv->rgxc) {
        rgx_enqd = rte_regexdev_enqueue_burst(lv->rid, lv->rgxc->qp_id_base,
                                              lv->rgxc->ops, nb_rx);
        if (rgx_enqd < nb_rx) {
          rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER2,
                  "lcore %d: Not all ops enqueued, enqueued %u out of %u\n",
                  rte_lcore_id(), rgx_enqd, nb_rx);
          rte_pktmbuf_free_bulk(&pkts_burst[rgx_enqd], nb_rx - rgx_enqd);
        }

        for (int stats_i = 1;
             stats_i <= g_app_args.rgx_stats_histogram_bucket_cnt; stats_i++) {
          if (rgx_enqd <=
              stats_i * g_app_args.rgx_stats_histogram_bucket_size) {
            lv->rgxc->stats[stats_i - 1].enq_burst_cnt++;
            lv->rgxc->stats[stats_i - 1].enq_burst_pkts_cnt += rgx_enqd;
            break;
          }
        }
      }
    }

    if (lv->rgxc) {
      rgx_dqd =
          rte_regexdev_dequeue_burst(lv->rid, lv->rgxc->qp_id_base,
                                     lv->rgxc->ops, g_app_args.port_burst_size);
      if (rgx_dqd > 0) {
        loop_wasted = false;
        int stats_i;
        for (stats_i = 1; stats_i <= g_app_args.rgx_stats_histogram_bucket_cnt;
             stats_i++) {
          if (rgx_dqd <= stats_i * g_app_args.rgx_stats_histogram_bucket_size) {
            lv->rgxc->stats[stats_i - 1].deq_burst_cnt++;
            lv->rgxc->stats[stats_i - 1].deq_burst_pkt_cnt += rgx_dqd;
            break;
          }
        }
        // you can't touch things that might be remains from the enqueue op
        for (int i = 0; i < rgx_dqd; i++) {
          lv->rgxc->stats[stats_i].matches += lv->rgxc->ops[i]->nb_matches;
          rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1,
                  "lcore %d\trgx_dqd %d\tmbuf %p matches %u "
                  "usrptr %p usrptr refcnt %d usr timestamp cycles %lu\n",
                  rte_lcore_id(), rgx_dqd, lv->rgxc->ops[i]->mbuf,
                  lv->rgxc->ops[i]->nb_matches, lv->rgxc->ops[i]->user_ptr,
                  ((struct rte_mbuf *)lv->rgxc->ops[i]->user_ptr)->refcnt,
                  ((struct rte_mbuf *)lv->rgxc->ops[i]->user_ptr)->tx_offload);
          struct rte_mbuf *p = lv->rgxc->ops[i]->user_ptr;
          const uint64_t ticks_per_us = rte_get_tsc_hz() / 1000000;
          if (ticks_per_us != 0) {
            if (!p || !p->tx_offload) {
              rte_panic("why NULL");
            }
            uint64_t t = rte_rdtsc_precise();
            lv->rgxc->stats[stats_i].deq_RTT_total_cycles +=
                (t - p->tx_offload);
            lv->rgxc->stats[stats_i].deq_RTT_total_us +=
                (t - p->tx_offload) / ticks_per_us;
          } else {
            rte_panic("why zero");
          }
          rgx_dqd_collector[i] = p;
        }
        forward_or_free_pkts(rgx_dqd_collector, rgx_dqd, lv->qid);
      }
    }

  continue_loop:
    update_cycles_counts(loop_wasted, loop_start_ts, lv->lcore_stats);
  }

end:
  if (lv->rgxc) {
    while ((rgx_dqd = rte_regexdev_dequeue_burst(
                lv->rid, lv->rgxc->qp_id_base, lv->rgxc->ops,
                g_app_args.port_burst_size)) > 0) {
      for (int i = 0; i < rgx_dqd; i++) {
        struct rte_mbuf *p = lv->rgxc->ops[i]->user_ptr;
        rte_pktmbuf_free(p);
      }
    }
    rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER2, "Regex queue %d is drained\n",
            lv->rgxc->qp_id_base);
  }
  if (lv->qid == 0) {
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "REGEX dev xstats\n");
    if (regex_xstats_print(lv->rid) < 0) { // not supported on BF2
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
              "REGEX xstats not supported on %d\n", lv->rid);
    }
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "PORT dev xstats\n");
    xstats_print(lv->pid);
  }

  struct app_stats *stats = rte_calloc("app_stats", 1, sizeof(*stats), 0);
  if (stats == NULL) {
    rte_panic("Error, can't allocate memory for app stats\n");
  } else {
    if (lv->rgxc && lv->rgxc->stats) {
      stats->regex_stats = lv->rgxc->stats;
    }
    if (lv->hsc && lv->hsc->stats) {
      stats->hs_stats = lv->hsc->stats;
    }
    stats->lcore_stats = lv->lcore_stats;
  }

  return stats;
}

static int worker_init(lcore_vars *lv, shared_vars *sv, uint16_t qid) {
  lv->pid = sv->port_id;
  lv->qid = qid;
  lv->rid = sv->regex_dev_id;

  if (sv->rgxc_arr != NULL) {
    lv->rgxc = &sv->rgxc_arr[qid];
    if (lv->rgxc->qp_id_base == 0) { // not supported on BF2
      if (!regexdev_selftest_passed(lv->rgxc->qp_id_base))
        goto fail;
    }

    struct rte_regexdev_info dev_info;
    int ret = rte_regexdev_info_get(lv->rid, &dev_info);
    if (ret != 0) {
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
              "Error, can't get regexdev info\n");
      goto fail;
    }

    lv->rgxc->ops =
        regexdev_allocate_ops(g_app_args.port_burst_size, dev_info.max_matches);
    if (lv->rgxc->ops == NULL) {
      goto fail;
    }

    lv->rgxc->stats = rte_calloc("stats_burst array",
                                 g_app_args.rgx_stats_histogram_bucket_cnt,
                                 sizeof(*lv->rgxc->stats), 0);
    if (lv->rgxc->stats == NULL) {
      regexdev_deallocate_ops(lv->rgxc->ops);
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
              "Error, can't allocate memory for stats\n");
      goto fail;
    }
  }

  if (sv->hs_scratch[0] != NULL) {
    lv->hsc = rte_calloc("hs_conf", 1, sizeof(*lv->hsc), 0);
    if (lv->hsc == NULL) {
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
              "Error, can't allocate memory for hs_conf\n");
      goto fail;
    }
    lv->hsc->db = sv->hs_db;
    lv->hsc->scratch = sv->hs_scratch[qid];
    lv->hsc->stats = rte_calloc("hs_stats", 1, sizeof(*lv->hsc->stats), 0);
    if (lv->hsc->stats == NULL) {
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
              "Error, can't allocate memory for hs_stats\n");
      goto fail;
    }
  }

  if (lv->lcore_stats == NULL) {
    lv->lcore_stats = rte_calloc("lcore_stats", 1, sizeof(*lv->lcore_stats), 0);
    if (lv->lcore_stats == NULL) {
      rte_log(RTE_LOG_ERR, RTE_LOGTYPE_USER2,
              "Error, can't allocate memory for lcore_stats\n");
      goto fail;
    }
  }

  return 0;

fail:
  if (lv->rgxc) {
    if (lv->rgxc->ops) {
      regexdev_deallocate_ops(lv->rgxc->ops);
    }
    if (lv->rgxc->stats) {
      rte_free(lv->rgxc->stats);
    }
  }
  if (lv->hsc) {
    if (lv->hsc->stats) {
      rte_free(lv->hsc->stats);
    }
    rte_free(lv->hsc);
  }
  if (lv->lcore_stats) {
    rte_free(lv->lcore_stats);
  }

  return -1;
}

static int worker_run(void *data) {
  shared_vars *sv = (shared_vars *)data;
  uint16_t qid = rte_atomic16_add_return(&sv->wq_id, 1) - 1;
  if (qid > sv->total_queues) {
    rte_log(
        RTE_LOG_INFO, RTE_LOGTYPE_USER1,
        "More workers than queues configured, quiting lcore %d for port %d\n",
        rte_lcore_id(), sv->port_id);
    return 0;
  }

  rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Hello from worker %d with P%dQ%d\n",
          rte_lcore_id(), sv->port_id, qid);

  lcore_vars lv = {0};
  int ret = worker_init(&lv, sv, qid);
  if (ret != 0) {
    return -1;
  }

  sv->stats[lv.qid] = worker_rx_pkts(&lv);
  if (lv.rgxc && lv.rgxc->ops) {
    regexdev_deallocate_ops(lv.rgxc->ops);
  }

  return 0;
}

static void app_stats_dump(struct app_stats **svstats, uint16_t nb_worker_cores,
                           uint16_t rgx_bkt_cnt, bool explib_out) {
  // print out aggregated stats
  struct app_stats *stats = rte_calloc("app_stats", 1, sizeof(*stats), 0);
  if (stats == NULL) {
    rte_panic("Error, can't allocate memory for app stats\n");
  }
  struct regex_stats_burst *s =
      rte_calloc("regex stats", rgx_bkt_cnt, sizeof(*s), 0);
  if (s == NULL) {
    rte_panic("Error, can't allocate memory for regex stats\n");
  }
  struct hs_stats *hs_stats = rte_calloc("hs_stats", 1, sizeof(*hs_stats), 0);
  if (hs_stats == NULL) {
    rte_panic("Error, can't allocate memory for hs_stats\n");
  }
  struct lcore_stats *lc_stats =
      rte_calloc("struct lcore_stats", 1, sizeof(*lc_stats), 0);
  if (lc_stats == NULL) {
    rte_panic("Error, can't allocate memory for lc_stats\n");
  }

  stats->regex_stats = s;
  stats->hs_stats = hs_stats;
  stats->lcore_stats = lc_stats;

  for (int i = 0; i < nb_worker_cores; i++) {
    if (svstats[i] != NULL) {
      for (int j = 0; j < rgx_bkt_cnt; j++) {
        if (svstats[i]->regex_stats != NULL) {
          s[j].burst_size =
              (j + 1) * g_app_args.rgx_stats_histogram_bucket_size;
          s[j].enq_burst_cnt += svstats[i]->regex_stats[j].enq_burst_pkts_cnt;
          s[j].enq_burst_pkts_cnt +=
              svstats[i]->regex_stats[j].enq_burst_pkts_cnt;
          s[j].deq_burst_cnt += svstats[i]->regex_stats[j].deq_burst_cnt;
          s[j].deq_burst_pkt_cnt +=
              svstats[i]->regex_stats[j].deq_burst_pkt_cnt;
          s[j].deq_RTT_total_us += svstats[i]->regex_stats[j].deq_RTT_total_us;
          s[j].deq_RTT_total_cycles +=
              svstats[i]->regex_stats[j].deq_RTT_total_cycles;
          s[j].matches += svstats[i]->regex_stats[j].matches;
        }
      }
    }
  }

  for (int i = 0; i < nb_worker_cores; i++) {
    if (svstats[i] != NULL && svstats[i]->hs_stats != NULL) {
      hs_stats->total_scans += svstats[i]->hs_stats->total_scans;
      hs_stats->total_scans_us += svstats[i]->hs_stats->total_scans_us;
      hs_stats->total_scans_cycles += svstats[i]->hs_stats->total_scans_cycles;
      hs_stats->total_matches += svstats[i]->hs_stats->total_matches;
      rte_free(svstats[i]->hs_stats);
    }
  }

  for (int i = 0; i < nb_worker_cores; i++) {
    if (svstats[i] != NULL && svstats[i]->lcore_stats != NULL) {
      lc_stats->useful_cycles += svstats[i]->lcore_stats->useful_cycles;
      lc_stats->wasted_cycles += svstats[i]->lcore_stats->wasted_cycles;
      rte_free(svstats[i]->lcore_stats);
      svstats[i]->lcore_stats = NULL;
    }
  }

  if (g_app_args.rgx_enabled) {
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "Aggregated REGEX dev stats\n");
    for (int i = 0; i < g_app_args.rgx_stats_histogram_bucket_cnt; i++) {
      rte_log(
          RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
          "Burst size %d: enq_burst_cnt %lu enq_burst_pkts_cnt %lu "
          "deq_burst_cnt %lu deq_burst_pkt_cnt %lu ttl_matches %lu"
          "deq_RTT_total_us %lu "
          "avg RTT in us %lu deq_RTT_total_cycles %lu avg RTT in cycles %lu\n",
          s[i].burst_size, s[i].enq_burst_cnt, s[i].enq_burst_pkts_cnt,
          s[i].deq_burst_cnt, s[i].deq_burst_pkt_cnt, s[i].matches,
          s[i].deq_RTT_total_us,
          s[i].deq_burst_pkt_cnt == 0
              ? 0
              : s[i].deq_RTT_total_us / s[i].deq_burst_pkt_cnt,
          s[i].deq_RTT_total_cycles,
          s[i].deq_burst_pkt_cnt == 0
              ? 0
              : s[i].deq_RTT_total_cycles / s[i].deq_burst_pkt_cnt);
    }
    if (explib_out) {
      for (int i = 0; i < g_app_args.rgx_stats_histogram_bucket_cnt; i++) {
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "burstsize= %u\n",
                s[i].burst_size);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_enq_brst_cnt %lu\n", s[i].burst_size,
                s[i].enq_burst_cnt);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_enq_brst_pkts_cnt %lu\n",
                s[i].burst_size, s[i].enq_burst_pkts_cnt);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_deq_brst_cnt %lu\n", s[i].burst_size,
                s[i].deq_burst_cnt);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_deq_brst_pkts_cnt %lu\n",
                s[i].burst_size, s[i].deq_burst_pkt_cnt);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_patterns_matched %lu\n",
                s[i].burst_size, s[i].matches);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_deq_rtt_ttl_us %lu\n",
                s[i].burst_size, s[i].deq_RTT_total_us);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_deq_avg_rtt_us %lu\n",
                s[i].burst_size,
                s[i].deq_burst_pkt_cnt == 0
                    ? 0
                    : s[i].deq_RTT_total_us / s[i].deq_burst_pkt_cnt);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_deq_rtt_ttl_cycles %lu\n",
                s[i].burst_size, s[i].deq_RTT_total_cycles);
        rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
                "RESULT-rgx_bs%" PRIu16 "_deq_avg_rtt_cycles %lu\n",
                s[i].burst_size,
                s[i].deq_burst_pkt_cnt == 0
                    ? 0
                    : s[i].deq_RTT_total_cycles / s[i].deq_burst_pkt_cnt);
      }
    }
  }

  if (g_app_args.hs_enabled) {
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "Aggregated HS dev stats\n");
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
            "total scans: %lu total_matched_patterns: %lu total scans us: %lu "
            "avg scan time in us: %lu total "
            "scan cycles: %lu avg scan cycles: %lu\n",
            hs_stats->total_scans, hs_stats->total_matches,
            hs_stats->total_scans_us,
            hs_stats->total_scans == 0
                ? 0
                : hs_stats->total_scans_us / hs_stats->total_scans,
            hs_stats->total_scans_cycles,
            hs_stats->total_scans == 0
                ? 0
                : hs_stats->total_scans_cycles / hs_stats->total_scans);

    if (explib_out) {
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "RESULT-hs_total_scans %lu\n",
              hs_stats->total_scans);
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
              "RESULT-hs_total_patterns_matched %lu\n",
              hs_stats->total_matches);
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
              "RESULT-hs_total_scans_us %lu\n", hs_stats->total_scans_us);
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
              "RESULT-hs_avg_scan_time_us %lu\n",
              hs_stats->total_scans == 0
                  ? 0
                  : hs_stats->total_scans_us / hs_stats->total_scans);
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
              "RESULT-hs_total_scans_cycles %lu\n",
              hs_stats->total_scans_cycles);
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
              "RESULT-hs_avg_scan_time_cycles %lu\n",
              hs_stats->total_scans == 0
                  ? 0
                  : hs_stats->total_scans_cycles / hs_stats->total_scans);
    }
  }

  rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "Aggregated lcore stats\n");
  rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2,
          "useful cycles: %lu wasted cycles: %lu\n", lc_stats->useful_cycles,
          lc_stats->wasted_cycles);
  if (explib_out) {
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "RESULT-app_useful_cycles %lu\n",
            lc_stats->useful_cycles);
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "RESULT-app_wasted_cycles %lu\n",
            lc_stats->wasted_cycles);
  }

  rte_free(s);
  rte_free(hs_stats);
  rte_free(lc_stats);
  rte_free(stats);
}

int main(int argc, char **argv) {
  int ret = 0;

  ret = rte_eal_init(argc, argv);
  if (ret < 0)
    rte_panic("Cannot init EAL\n");
  argc -= ret;
  argv += ret;

  args_parse(argc, argv);
  print_app_args();

  if (g_app_args.rgx_enabled && g_app_args.hs_enabled)
    rte_panic("HS and REGEX engine can't be simultaneously enabled");

  force_quit = false;
  signal(SIGINT, signal_handler);
  signal(SIGTERM, signal_handler);
  int nb_ports = rte_eth_dev_count_avail();
  uint32_t nb_worker_cores = rte_lcore_count() - 1; // processing cores
  char mbuf_pool_name[100] = "mbuf_pool_X";
  for (int portid = 0; portid < nb_ports; portid++) {
    struct rte_ether_addr addr = {0};
    rte_eth_macaddr_get(portid, &addr);
    uint8_t *mac_bytes = addr.addr_bytes;
    char macStr[100];
    snprintf(macStr, sizeof(macStr), "%02x:%02x:%02x:%02x:%02x:%02x",
             mac_bytes[0], mac_bytes[1], mac_bytes[2], mac_bytes[3],
             mac_bytes[4], mac_bytes[5]);
    char portStr[128];
    rte_eth_dev_get_name_by_port(portid, portStr);
    printf("PORT ID %d - %s MAC : %s\n", portid, portStr, macStr);

    // +4 for VLAN header
    uint32_t mtu_size =
        g_app_args.port_mtu; // + RTE_ETHER_CRC_LEN + RTE_ETHER_HDR_LEN + 4;
    uint32_t mbuf_size = ROUNDUP(mtu_size, 1024) + RTE_PKTMBUF_HEADROOM + 32; // 32 for extra space
    mbuf_pool_name[strlen(mbuf_pool_name) - 1] = 48 + portid;
    mbuf_pool = rte_pktmbuf_pool_create(
        mbuf_pool_name, g_app_args.port_mp_size * (nb_worker_cores + 1),
        g_app_args.port_mp_cache_size, 0, mbuf_size, rte_socket_id());

    if (mbuf_pool == NULL)
      rte_exit(EXIT_FAILURE, "Cannot init mbuf pool\n");
  }
  init_port(ETHERNET_PORTID, mbuf_pool, nb_worker_cores, nb_worker_cores,
            g_app_args.port_mtu);

  // init the RGX structure
  struct regex_conf *rgxc = NULL;
  if (g_app_args.rgx_enabled) {
    // regex configure start
    uint16_t num_devs;
    char *rules = NULL;
    long rules_len;
    struct rte_regexdev_info info;
    struct rte_regexdev_config dev_conf = {
        .nb_queue_pairs = nb_worker_cores
    };
    struct rte_regexdev_qp_conf qp_conf = {
        .nb_desc = g_app_args.rgx_descriptors,
        .qp_conf_flags = 0,
        .cb = NULL,
    };
    int res = 0;

    num_devs = rte_regexdev_count();
    if (num_devs == 0) {
      printf("Error, no devices detected.\n");
      return -EINVAL;
    }

    rules_len = read_file(g_app_args.rgx_rules_path, &rules);
    if (rules_len < 0) {
      res = -EIO;
      rte_free(rules);
      rte_exit(EXIT_FAILURE, "Cannot read rules file\n");
    }

    for (int id = 0; id < num_devs; id++) {
      res = rte_regexdev_info_get(id, &info);
      if (res != 0) {
        rte_free(rules);
        rte_exit(EXIT_FAILURE, "Cannot get device info\n");
      }
      printf(":: initializing dev: %d max matches: %d max payload sz: %d max group cnt: %d max rules per group cnt: %d\n", id,
             info.max_matches, info.max_payload_size, info.max_groups, info.max_rules_per_group);
      if (info.regexdev_capa & RTE_REGEXDEV_SUPP_MATCH_AS_END_F)
        dev_conf.dev_cfg_flags |= RTE_REGEXDEV_CFG_MATCH_AS_END_F;

      dev_conf.nb_groups = g_app_args.rgx_subset_cnt;
      dev_conf.nb_max_matches =
          info.max_matches; // BF doesn't support changing this value - too bad,
                            // it takes precious space
      dev_conf.nb_rules_per_group = info.max_rules_per_group;
      dev_conf.rule_db_len = rules_len;
      dev_conf.rule_db = rules;
      res = rte_regexdev_configure(id, &dev_conf);
      if (res < 0) {
        rte_free(rules);
        rte_exit(EXIT_FAILURE, "Error, can't configure device %d.\n", id);
      }
      if (info.regexdev_capa & RTE_REGEXDEV_CAPA_QUEUE_PAIR_OOS_F) {
        rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1,
                "Configuring out-of-order queue pairs for device %d\n", id);
        qp_conf.qp_conf_flags |= RTE_REGEX_QUEUE_PAIR_CFG_OOS_F;
      }

      for (int qp_id = 0; qp_id < nb_worker_cores; qp_id++) {
        res = rte_regexdev_queue_pair_setup(id, qp_id, &qp_conf);
        if (res < 0) {
          rte_free(rules);
          rte_exit(EXIT_FAILURE,
                   "Error, can't setup queue pair %u for device %d.\n", qp_id,
                   id);
        }
      }
    }
    rte_free(rules);

    rgxc = rte_malloc(NULL, sizeof(*rgxc) * nb_worker_cores, 0);
    if (!rgxc)
      rte_exit(EXIT_FAILURE, "Failed to create Regex Conf\n");

    for (int lcore_idx = 0; lcore_idx < nb_worker_cores; lcore_idx++) {
      rgxc[lcore_idx] = (struct regex_conf){
          .qp_id_base = lcore_idx,
          .nb_qps = 1,
          .match_mode = g_app_args.rgx_num_of_match_mode,
      };
    }
  }
  // End of regex

  // Hyperscan begin
  hs_database_t *db = NULL;
  hs_scratch_t *scratch = NULL;
  if (g_app_args.hs_enabled) {
    rte_log(
        RTE_LOG_INFO, RTE_LOGTYPE_USER1,
        "Initializing Hyperscan, rule path %s, regex expression flags: %s\n",
        g_app_args.hs_rules_path, hs_log_expression_flags(g_app_args.hs_flags));
    ret = hs_init_db(g_app_args.hs_rules_path, &db, g_app_args.hs_flags);
    char *db_info = NULL;
    if (hs_database_info(db, &db_info) != HS_SUCCESS) {
      rte_panic("Error: Could not get db info !\n");
    }
    if (ret != 0)
      rte_panic("Error: Unable to initialize database\n");
    if (hs_alloc_scratch(db, &scratch) != HS_SUCCESS) {
      size_t db_size = 0;
      if (hs_database_size(db, &db_size) != HS_SUCCESS)
        rte_panic("Error: Could not initialize scratch space and could not get "
                  "db size\n");
      rte_panic("Error: Unable to initialize scratch space\n ! Required "
                "memory: %ld bytes.\n",
                db_size);
    }
    rte_log(RTE_LOG_INFO, RTE_LOGTYPE_USER1, "Hyperscan initialized\n");
  }
  // Hyperscan end

  shared_vars sv = {
      .port_id = ETHERNET_PORTID,
      .total_queues = nb_worker_cores,
      .regex_dev_id = 0,
      .rgxc_arr = rgxc,
      .hs_db = db,
      .hs_scratch = {0},
      .stats = {0},
  };

  rte_atomic16_init(&sv.wq_id);
  rte_atomic16_set(&sv.wq_id, 0);
  if (scratch) {
    for (int i = 0; i < nb_worker_cores; i++) {
      ret = hs_clone_scratch(scratch, &(sv.hs_scratch[i]));
      if (ret != HS_SUCCESS)
        rte_panic("Error: Unable to clone scratch\n");
    }
  }

  rte_eal_mp_remote_launch(worker_run, &sv, SKIP_MAIN);
  rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "EVENT starting-rx\n");
  while (!force_quit)
    sleep(1);

  rte_eal_mp_wait_lcore();

  app_stats_dump(sv.stats, nb_worker_cores,
                 g_app_args.rgx_stats_histogram_bucket_cnt,
                 g_app_args.explib_out);

  // clean up HS
  for (int i = 0; i < nb_worker_cores; i++) {
    if (sv.hs_scratch[i])
      hs_free_scratch(sv.hs_scratch[i]);
  }
  if (scratch)
    hs_free_scratch(scratch);
  if (db)
    hs_free_database(db);

  if (g_app_args.rgx_enabled == true) {
    if (rte_regexdev_stop(sv.regex_dev_id) < 0) {
      rte_panic("Error stopping regex device\n");
    }

    if (rte_regexdev_close(sv.regex_dev_id) < 0) {
      rte_panic("Error closing regex device\n");
    }
  }

  // stop ports
  if (rte_eth_dev_stop(ETHERNET_PORTID) < 0) {
    rte_panic("Error stopping port %d\n", ETHERNET_PORTID);
  }

  if (rte_eth_dev_close(ETHERNET_PORTID) < 0) {
    rte_panic("Error closing port %d\n", ETHERNET_PORTID);
  }

  rte_mempool_free(mbuf_pool);

  /* clean up the EAL */
  rte_eal_cleanup();
  return 0;
}
