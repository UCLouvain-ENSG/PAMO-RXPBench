#include "rgx_stats.h"
#include <rte_ethdev.h>
#include <rte_malloc.h>
#include <rte_regexdev.h>

void xstats_print(uint32_t port_id) {
  char port_name[RTE_ETH_NAME_MAX_LEN];
  if (rte_eth_dev_get_name_by_port(port_id, port_name) < 0)
    rte_panic("Error getting name of port %u\n", port_id);

  struct rte_eth_xstat *xstats;
  struct rte_eth_xstat_name *xstats_names;

  int32_t len = rte_eth_xstats_get(port_id, NULL, 0);
  if (len < 0)
    rte_panic("Error (%s) getting count of rte_eth_xstats failed on port %s\n",
              rte_strerror(-len), port_name);

  xstats = rte_calloc("xstats", len, sizeof(*xstats), 0);
  if (xstats == NULL)
    rte_panic("Failed to allocate memory for the rte_eth_xstat structure\n");

  int32_t ret = rte_eth_xstats_get(port_id, xstats, len);
  if (ret < 0 || ret > len) {
    rte_free(xstats);
    rte_panic("Error (%s) getting rte_eth_xstats failed on port %s\n",
              rte_strerror(-ret), port_name);
  }
  xstats_names = rte_calloc("xstats_names", len, sizeof(*xstats_names), 0);
  if (xstats_names == NULL) {
    rte_free(xstats);
    rte_panic("Failed to allocate memory for the rte_eth_xstat_name array\n");
  }
  ret = rte_eth_xstats_get_names(port_id, xstats_names, len);
  if (ret < 0 || ret > len) {
    rte_free(xstats);
    rte_free(xstats_names);
    rte_panic("Error (%s) getting names of rte_eth_xstats failed on port %s\n",
              rte_strerror(-ret), port_name);
  }
  for (int32_t i = 0; i < len; i++) {
    rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "RESULT-port%u_%s %lu\n",
            port_id, xstats_names[i].name, xstats[i].value);
  }

  rte_free(xstats);
  rte_free(xstats_names);
}

int regex_xstats_print(uint32_t port_id) {
  int32_t xstats_len = rte_regexdev_xstats_names_get(0, NULL);
  if (xstats_len < 0)
    return -1;

  struct rte_regexdev_xstats_map *xstats_map =
      rte_calloc("regex xstats", xstats_len, sizeof(*xstats_map), 0);
  if (xstats_map == NULL)
    rte_panic("Failed to allocate memory for the rte_eth_xstat structure\n");

  uint16_t *map_ids =
      rte_calloc("regex xstats id", xstats_len, sizeof(*map_ids), 0);
  if (map_ids == NULL) {
    rte_free(xstats_map);
    rte_panic("Failed to allocate memory for the rte_eth_xstat_name array\n");
  }
  for (int32_t i = 0; i < xstats_len; i++) {
    map_ids[i] = xstats_map[i].id;
  }

  uint64_t *values =
      rte_calloc("regex xstats values", xstats_len, sizeof(*values), 0);
  if (values == NULL) {
    rte_free(map_ids);
    rte_free(xstats_map);
    rte_panic("Failed to allocate memory for the rte_eth_xstat_name array\n");
  }

  int32_t ret = rte_regexdev_xstats_get(port_id, map_ids, values, xstats_len);
  if (ret < 0 || ret > xstats_len) {
    rte_free(map_ids);
    rte_free(xstats_map);
    rte_free(values);
    rte_panic("Error (%s) getting rte_eth_xstats failed on port %d\n",
              rte_strerror(-ret), port_id);
  }

  for (int32_t i = 0; i < xstats_len; i++) {
    if (values[i] > 0)
      rte_log(RTE_LOG_NOTICE, RTE_LOGTYPE_USER2, "Port %u - %s: %" PRIu64 "\n",
              port_id, xstats_map[i].name, values[i]);
  }

  rte_free(map_ids);
  rte_free(xstats_map);
  rte_free(values);
  return 0;
}