#!/usr/bin/env python3
import os
import re
import json
import argparse
from collections import Counter
from tabulate import tabulate

def parse_eve(eve_path):
    """
    Reads eve.json line by line, sums up pkts/bytes toserver/toclient per proto.
    Returns two Counters:
      - packets[("<proto>.<direction>")] = packet count
      - bytes_[("<proto>.<direction>")] = byte count
    """
    pkts = Counter()
    bytes_ = Counter()
    with open(eve_path) as f:
        for line in f:
            j = json.loads(line)
            if j.get("event_type") == "flow":
                proto = j["proto"].lower()
                flow = j["flow"]
                # Packet counts
                pkts[f"{proto}.toserver"] += flow.get("pkts_toserver", 0)
                pkts[f"{proto}.toclient"] += flow.get("pkts_toclient", 0)
                # Byte counts
                bytes_[f"{proto}.toserver"] += flow.get("bytes_toserver", 0)
                bytes_[f"{proto}.toclient"] += flow.get("bytes_toclient", 0)
    return pkts, bytes_

# (other helper functions remain unchanged)
def load_rule_groups(rg_json_path):
    """
    Load the mapping from SGH id -> human‐readable path.
    """
    try:
        with open(rg_json_path) as f:
            rg = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}
    if not rg:
        return {}
    id_to_path = {}
    def recurse(d, path=[]):
        if isinstance(d, dict) and "rulegroup" in d and "id" in d["rulegroup"]:
            id_to_path[d["rulegroup"]["id"]] = ".".join(path)
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict):
                    recurse(v, path + [k])
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            if "port" in item and "port2" in item:
                                recurse(item, path + [k, f"{item['port']}-{item['port2']}"])
                            else:
                                recurse(item, path + [k])
    recurse(rg)
    return id_to_path


def parse_rule_group_perf(rgp_path):
    # unchanged
    from collections import Counter
    checks = Counter()
    try:
        with open(rgp_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('-') or 'Sgh' in line or 'Stats for:' in line or 'Date:' in line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        sgid = int(parts[0])
                        check_count = int(parts[1])
                        checks[sgid] += check_count
                    except ValueError:
                        continue
    except FileNotFoundError:
        pass
    return checks


def parse_prefilter_perf(pf_path):
    # unchanged
    data = {}
    try:
        with open(pf_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('-') or 'Prefilter' in line or 'Stats for:' in line or 'Date:' in line:
                    continue
                parts = line.split()
                if len(parts) >= 7:
                    try:
                        name = parts[0]
                        calls = int(parts[2])
                        bytes_val = int(parts[5])
                        data[name] = {"uses": calls, "bytes": bytes_val}
                    except (ValueError, IndexError):
                        continue
    except FileNotFoundError:
        pass
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-l", "--logdir", required=True,
                   help="Directory containing fast.log, eve.json, rule_group*.json/log, prefilter_perf.log")
    args = p.parse_args()
    d = args.logdir.rstrip("/")

    # ---- Part 1: Traffic direction from eve.json ----
    eve_path = os.path.join(d, "eve.json")
    traffic_pkts, traffic_bytes = parse_eve(eve_path)
    # Prepare table: combine packet and byte counts per direction
    directions = sorted(set(traffic_pkts.keys()) | set(traffic_bytes.keys()))
    table1 = []
    for dir_ in directions:
        table1.append([dir_, traffic_pkts.get(dir_, 0), traffic_bytes.get(dir_, 0)])
    print("\nPart 1 – Traffic Direction\n")
    print(tabulate(table1,
                   headers=["Traffic direction", "Pkts", "Bytes"],
                   tablefmt="github"))

    # ---- Part 2: SGH checks ----
    rg_json = os.path.join(d, "rule_group.json")
    id_to_path = load_rule_groups(rg_json)
    perf = parse_rule_group_perf(os.path.join(d, "rule_group_perf.log"))
    table2 = []
    for sgid, cnt in perf.items():
        path = id_to_path.get(sgid, f"<unknown:{sgid}>")
        table2.append([path, cnt])
    table2.sort(key=lambda x: x[0])
    print("\nPart 2 – SGH Checks\n")
    print(tabulate(table2,
                   headers=["SGH", "Checks"],
                   tablefmt="github"))

    # ---- Part 3: MPM prefilter usage ----
    pf = parse_prefilter_perf(os.path.join(d, "prefilter_perf.log"))
    total_pkts = sum(x["uses"] for x in pf.values())
    total_bytes = sum(x["bytes"] for x in pf.values())
    table3 = []
    for name, v in pf.items():
        uses = v["uses"]
        b = v["bytes"]
        table3.append([
            name,
            uses,
            f"{uses/total_pkts*100:.1f}%",
            b,
            f"{b/total_bytes*100:.1f}%"
        ])
    table3.sort(key=lambda x: x[0])
    print("\nPart 3 – MPM Prefilter Usage\n")
    print(tabulate(table3,
                   headers=["MPM", "Uses", "Pkts (in %)", "Bytes", "Bytes (in %)"],
                   tablefmt="github"))

if __name__ == "__main__":
    main()

