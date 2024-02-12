#!/usr/bin/env python3
import json
import argparse
import math
import matplotlib.pyplot as plt
from collections import defaultdict, Counter

def parse_args():
    parser = argparse.ArgumentParser(
        description=("Enhanced data mining and statistics program for JSON rule groups, "
                     "including MPM statistics with pattern length analysis.")
    )
    parser.add_argument("--input", "-i", default="rule_group.json",
                        help="Path to the input JSON file (default: rule_group.json)")
    parser.add_argument("--path", "-p", default=None,
                        help=("Optional hierarchical path to filter by "
                              "(e.g., 'tcp', 'tcp.toserver', 'icmpv4', etc.)"))
    parser.add_argument("--show-plot", action="store_true", default=False,
                        help="If set, the plots will be shown (default: disabled)")
    parser.add_argument("--disable-mpm", action="store_true", default=False,
                        help="Disable MPM analysis (default: enabled)")
    parser.add_argument("--mpm-group", default="payload",
                        help="Specify which MPM group context to analyze (default: payload)")
    return parser.parse_args()

def load_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def recursive_extract_groups(current_data, current_path, groups):
    """
    Recursively traverse the JSON structure.
    Any dictionary that contains a "rulegroup" key is considered an SGH node.
    This function extracts:
      - sigs: the list of signature IDs from rulegroup.rules,
      - stats: from the current node’s "stats" key or, if missing, from rulegroup.stats.
    """
    if isinstance(current_data, dict):
        if "rulegroup" in current_data:
            sigs = [rule.get("sig_id") for rule in current_data["rulegroup"].get("rules", [])
                    if "sig_id" in rule]
            stats = current_data.get("stats")
            if stats is None:
                stats = current_data["rulegroup"].get("stats", {})
            groups.append((current_path, sigs, stats))
        for key, val in current_data.items():
            recursive_extract_groups(val, current_path + [key], groups)
    elif isinstance(current_data, list):
        for idx, item in enumerate(current_data):
            recursive_extract_groups(item, current_path + [str(idx)], groups)

def extract_groups(data, filter_path=None):
    """
    Extract all nodes having a "rulegroup" key. If a filter_path is specified (e.g., "tcp.toserver" or "icmpv4"),
    only the corresponding branch will be processed.
    """
    if filter_path:
        for key in filter_path.split("."):
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                print(f"Filter path '{filter_path}' not found in the data.")
                return []
    groups = []
    recursive_extract_groups(data, filter_path.split(".") if filter_path else [], groups)
    return groups

def compute_metrics(groups):
    """
    Compute SGH membership metrics from the list of nodes (based solely on sig_ids):
      - Average SGH memberships per rule,
      - Unique rule coverage,
      - Average overlap per pair of nodes,
      - Entropy of the rule multiplicity distribution, and
      - Histogram of rule multiplicity.
    """
    rule_memberships = defaultdict(set)
    for group_index, (_, sigs, _) in enumerate(groups):
        for sig in sigs:
            rule_memberships[sig].add(group_index)
            
    total_memberships = sum(len(members) for members in rule_memberships.values())
    total_unique_rules = len(rule_memberships)
    avg_sgh = total_memberships / total_unique_rules if total_unique_rules else 0
    unique_coverage = (sum(1 for members in rule_memberships.values() if len(members) == 1) /
                       total_unique_rules) if total_unique_rules else 0

    num_groups = len(groups)
    if num_groups > 1:
        overlap_sum = 0
        count_pairs = 0
        group_sigs = [set(sigs) for (_, sigs, _) in groups]
        for i in range(num_groups):
            for j in range(i + 1, num_groups):
                overlap_sum += len(group_sigs[i].intersection(group_sigs[j]))
                count_pairs += 1
        avg_overlap = overlap_sum / count_pairs if count_pairs else 0
    else:
        avg_overlap = 0

    multiplicities = [len(members) for members in rule_memberships.values()]
    hist = Counter(multiplicities)
    entropy = -sum((count/total_unique_rules) * math.log(count/total_unique_rules, 2)
                   for count in hist.values()) if total_unique_rules else 0

    return {
        "avg_sgh_per_rule": avg_sgh,
        "unique_rule_coverage": unique_coverage,
        "avg_overlap_per_pair": avg_overlap,
        "entropy": entropy,
        "multiplicity_histogram": dict(hist)
    }

def print_metrics(level_name, metrics):
    print(f"\nStatistics for level: {level_name}")
    print(f"  Average SGH memberships per rule (how many SGH the rule belongs to): {metrics['avg_sgh_per_rule']:.3f}")
    print(f"  Unique rule coverage (fraction in only one group): {metrics['unique_rule_coverage']:.3f}")
    print(f"  Average overlap per group pair: {metrics['avg_overlap_per_pair']:.3f}")
    print(f"  Entropy of rule multiplicity distribution: {metrics['entropy']:.3f}")
    print("  Histogram of rule multiplicity (rule count : occurrences):")
    for count, occ in sorted(metrics['multiplicity_histogram'].items()):
        print(f"    {count}: {occ}")

def plot_histogram(metrics, level_name):
    hist = metrics['multiplicity_histogram']
    x = list(hist.keys())
    y = list(hist.values())
    plt.figure()
    plt.bar(x, y)
    plt.xlabel("Number of group memberships (rule multiplicity)")
    plt.ylabel("Number of rules")
    plt.title(f"Histogram of rule multiplicity for level: {level_name}")
    plt.show()

def aggregate_protocol_composition(groups):
    """
    For each node, examine its stats (if available) and sum values for each protocol key.
    Keys "total" and "types" are skipped.
    The key "payload" is renamed to "IP", and "http" and "http_any" are merged under "http".
    If a value is a dict, its "total" field is used.
    """
    composition = defaultdict(int)
    for (_, _, stats) in groups:
        if not (isinstance(stats, dict) and stats):
            continue
        for key, value in stats.items():
            if key in ("total", "types"):
                continue
            if isinstance(value, dict):
                numeric_value = value.get("total")
                if numeric_value is None:
                    continue
                value = numeric_value
            if key == "payload":
                composition["IP"] += value
            elif key in ("http", "http_any"):
                composition["http"] += value
            else:
                composition[key] += value
    return dict(composition)

def print_protocol_composition(comp):
    print("  Aggregated Protocol Composition:")
    if comp:
        for prot, val in comp.items():
            print(f"    {prot}: {val}")
    else:
        print("    No protocol composition data available.")

def analyze_mpm(groups, mpm_group="payload"):
    """
    For MPM analysis over nodes:
      - Count total SGHs (nodes with a rulegroup).
      - Count SGHs that report MPM (if stats.types.mpm > 0).
      - For each node, retrieve the pattern count from stats.mpm.<mpm_group> (numeric or dict with 'total').
      Additionally, aggregate pattern length information from the "sizes" array (if present)
      to compute average, median, min, and max pattern lengths.
    """
    total_sgh = len(groups)
    mpm_present = 0
    pattern_counts = []
    # For pattern lengths: accumulate size -> total count (from each node's sizes array)
    length_dict = defaultdict(int)

    for (_, _, stats) in groups:
        patterns = 0
        has_mpm = False
        if isinstance(stats, dict):
            types = stats.get("types", {})
            if types.get("mpm", 0) > 0:
                has_mpm = True
            mpm_obj = stats.get("mpm", {})
            if isinstance(mpm_obj, dict):
                grp = mpm_obj.get(mpm_group)
                if isinstance(grp, dict):
                    patterns = grp.get("total", 0)
                    sizes = grp.get("sizes", [])
                    if isinstance(sizes, list):
                        for entry in sizes:
                            size_val = entry.get("size")
                            count_val = entry.get("count", 0)
                            if size_val is not None:
                                length_dict[size_val] += count_val
                elif isinstance(grp, (int, float)):
                    patterns = grp
        if has_mpm:
            mpm_present += 1
        pattern_counts.append(patterns)
    if pattern_counts:
        avg_patterns = sum(pattern_counts) / len(pattern_counts)
        sorted_counts = sorted(pattern_counts)
        n = len(sorted_counts)
        median_patterns = sorted_counts[n//2] if n % 2 == 1 else (sorted_counts[n//2 - 1] + sorted_counts[n//2]) / 2
        min_patterns = min(pattern_counts)
        max_patterns = max(pattern_counts)
    else:
        avg_patterns = median_patterns = min_patterns = max_patterns = 0

    # Compute pattern length statistics from length_dict using a weighted approach.
    if length_dict:
        total_length_count = sum(length_dict.values())
        total_length_sum = sum(size * count for size, count in length_dict.items())
        avg_length = total_length_sum / total_length_count if total_length_count > 0 else 0
        min_length = min(length_dict.keys())
        max_length = max(length_dict.keys())
        sorted_sizes = sorted(length_dict.items())  # list of (size, count)
        cumulative = 0
        half_total = total_length_count / 2
        median_length = None
        for size, count in sorted_sizes:
            cumulative += count
            if cumulative >= half_total:
                median_length = size
                break
    else:
        avg_length = median_length = min_length = max_length = 0

    mpm_stats = {
        "total_sgh": total_sgh,
        "mpm_present": mpm_present,
        "avg_patterns": avg_patterns,
        "median_patterns": median_patterns,
        "min_patterns": min_patterns,
        "max_patterns": max_patterns,
        "pattern_counts": pattern_counts,
    }
    mpm_stats["length_stats"] = {
        "avg_length": avg_length,
        "median_length": median_length,
        "min_length": min_length,
        "max_length": max_length,
    }
    return mpm_stats

def print_mpm_analysis(mpm_stats, mpm_group):
    print("  MPM Analysis:")
    print(f"    Total SGHs: {mpm_stats['total_sgh']}")
    print(f"    SGHs with MPM present: {mpm_stats['mpm_present']}")
    print(f"    MPM patterns for group '{mpm_group}':")
    print(f"      Average: {mpm_stats['avg_patterns']:.2f}")
    print(f"      Median : {mpm_stats['median_patterns']:.2f}")
    print(f"      Min    : {mpm_stats['min_patterns']}")
    print(f"      Max    : {mpm_stats['max_patterns']}")
    length_stats = mpm_stats.get("length_stats", {})
    print(f"    Pattern Lengths for group '{mpm_group}':")
    print(f"      Average: {length_stats.get('avg_length', 0):.2f}")
    print(f"      Median : {length_stats.get('median_length', 0):.2f}")
    print(f"      Min    : {length_stats.get('min_length', 0)}")
    print(f"      Max    : {length_stats.get('max_length', 0)}")

def analyze_levels(data, filter_path=None):
    """
    Organize analysis by hierarchical level.
    When no filter is provided, global analysis plus per top-level and second-level keys is performed.
    Only nodes with a "rulegroup" key are extracted.
    Returns:
      - levels: mapping level name -> list of nodes extracted.
      - results: mapping level name -> computed metrics (based on sig_ids).
    """
    levels = {}
    if filter_path:
        levels[filter_path] = extract_groups(data, filter_path)
    else:
        levels["global"] = extract_groups(data, None)
        for key in data.keys():
            levels[key] = extract_groups(data, key)
            if isinstance(data[key], dict):
                for sub in data[key].keys():
                    levels[f"{key}.{sub}"] = extract_groups(data, f"{key}.{sub}")
    results = {}
    for level, groups in levels.items():
        if groups:
            results[level] = compute_metrics(groups)
    return levels, results

def main():
    args = parse_args()
    data = load_data(args.input)
    
    levels, metrics_results = analyze_levels(data, args.path)
    
    # For each level, print SGH metrics, aggregated protocol composition, and extended MPM analysis.
    for level in sorted(levels.keys()):
        groups = levels[level]
        if not groups:
            continue
        print_metrics(level, metrics_results[level])
        comp = aggregate_protocol_composition(groups)
        print_protocol_composition(comp)
        if not args.disable_mpm:
            mpm_stats = analyze_mpm(groups, mpm_group=args.mpm_group)
            print_mpm_analysis(mpm_stats, args.mpm_group)
        if args.show_plot:
            plot_histogram(metrics_results[level], level)
    
if __name__ == "__main__":
    main()

