#!/usr/bin/env python3
import sys
import re
import argparse

# -----------------------
# Helper functions
# -----------------------

def parse_histogram(block_lines):
    """
    Parse the histogram lines from a block and return the sum of the counts.
    Expected lines are indented lines like "    1: 1404".
    """
    total = 0
    histo_started = False
    for line in block_lines:
        if "Histogram of rule multiplicity" in line:
            histo_started = True
            continue
        if histo_started:
            # if the line is blank or not indented, assume histogram ended.
            if not line.strip() or not line.startswith("    "):
                break
            # Extract the number after the colon
            m = re.search(r":\s*([\d\.]+)", line)
            if m:
                total += float(m.group(1))
    return int(total)

def parse_mpm_analysis(block_lines):
    """
    Extract Total SGHs, MPM patterns and Pattern Lengths from the MPM Analysis sub‐section.
    Returns a dictionary with keys:
      "sgh": int,
      "mpm": { "min":float, "max":float, "median":float, "avg":float },
      "length": { "min":float, "max":float, "median":float, "avg":float }
    """
    result = {
        "sgh": None,
        "mpm": {},
        "length": {}
    }
    in_mpm = False
    in_length = False
    for line in block_lines:
        line_strip = line.strip()
        # Look for Total SGHs
        if line_strip.startswith("Total SGHs:"):
            try:
                result["sgh"] = int(line_strip.split("Total SGHs:")[1].strip())
            except ValueError:
                result["sgh"] = None
        # Detect start of MPM patterns for group 'payload'
        if "MPM patterns for group" in line:
            in_mpm = True
            in_length = False
            continue
        # Detect start of Pattern Lengths for group 'payload'
        if "Pattern Lengths for group" in line:
            in_length = True
            in_mpm = False
            continue
        # Within a subsection, look for Average, Median, Min, Max
        if in_mpm or in_length:
            m = re.match(r"(Average|Median|Min|Max)\s*:\s*([\d\.]+)", line_strip)
            if m:
                key, value = m.group(1).lower(), float(m.group(2))
                if in_mpm:
                    result["mpm"][key] = value
                elif in_length:
                    result["length"][key] = value

    # Reorder into the desired order (min, max, median, avg)
    mpm = result["mpm"]
    length = result["length"]
    result["mpm"] = {
        "min": mpm.get("min"),
        "max": mpm.get("max"),
        "median": mpm.get("median"),
        "avg": mpm.get("average") if "average" in mpm else mpm.get("avg")
    }
    result["length"] = {
        "min": length.get("min"),
        "max": length.get("max"),
        "median": length.get("median"),
        "avg": length.get("average") if "average" in length else length.get("avg")
    }
    return result

def map_level(level_name):
    """
    Converts a level string into a tuple: (Protocol, Direction)
    The mapping is as follows:
      - "global" -> ("All", "Both")
      - "tcp" -> ("TCP", "Both")
      - "tcp.toserver" -> ("TCP", "To-Server")
      - "tcp.toclient" -> ("TCP", "To-Client")
      - "udp" -> ("UDP", "Both")
      - "udp.toserver" -> ("UDP", "To-Server")
      - "udp.toclient" -> ("UDP", "To-Client")
      - "icmpv4" -> ("ICMPv4", "Both")
      - "icmpv4.toserver" -> ("ICMPv4", "To-Server")
      - "icmpv4.toclient" -> ("ICMPv4", "To-Client")
      - "icmpv6" -> ("ICMPv6", "Both")
      - "icmpv6.toserver" -> ("ICMPv6", "To-Server")
      - "icmpv6.toclient" -> ("ICMPv6", "To-Client")
    """
    if level_name.lower() == "global":
        return ("All", "Both")
    parts = level_name.split(".")
    proto = parts[0].upper()
    if len(parts) == 1:
        direction = "Both"
    else:
        if parts[1].lower() == "toclient":
            direction = "To-Client"
        elif parts[1].lower() == "toserver":
            direction = "To-Server"
        else:
            direction = parts[1].capitalize()
    return (proto, direction)

# -----------------------
# Main Parsing Logic
# -----------------------

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Summarize statistics into a LaTeX table")
parser.add_argument("--decimals", type=int, default=0,
                    help="Number of decimals for MPM analysis values (default: 0)")
args = parser.parse_args()
decimals = args.decimals

data_by_level = {}
lines = sys.stdin.readlines()
current_level = None
current_block = []

for line in lines:
    m = re.match(r"Statistics for level:\s*(\S+)", line)
    if m:
        if current_level is not None:
            data_by_level[current_level] = current_block
        current_level = m.group(1).strip()
        current_block = []
    else:
        if current_level is not None:
            current_block.append(line.rstrip("\n"))
if current_level is not None:
    data_by_level[current_level] = current_block

summary = {}
for level, block_lines in data_by_level.items():
    proto, direction = map_level(level)
    unique_rule_count = parse_histogram(block_lines)
    mpm_data = parse_mpm_analysis(block_lines)
    sgh = mpm_data.get("sgh")
    mpm = mpm_data.get("mpm", {})
    length = mpm_data.get("length", {})
    summary[level] = {
        "protocol": proto,
        "direction": direction,
        "sgh": sgh,
        "unique_rules": unique_rule_count,
        "mpm": mpm,      # keys: min, max, median, avg
        "length": length # keys: min, max, median, avg
    }

# Desired output order (same as sample table)
desired_order = [
    "global",
    "tcp", "tcp.toserver", "tcp.toclient",
    "udp", "udp.toserver", "udp.toclient",
    "icmpv4", "icmpv4.toserver", "icmpv4.toclient",
    "icmpv6", "icmpv6.toserver", "icmpv6.toclient"
]

rows = []
for level in desired_order:
    if level in summary:
        rec = summary[level]
        row = {
            "protocol": rec["protocol"],
            "direction": rec["direction"],
            "sgh": rec["sgh"] if rec["sgh"] is not None else "",
            "unique": rec["unique_rules"],
            # MPM patterns (Count) values (in order: min, max, median, avg)
            "mpm_min": rec["mpm"].get("min", ""),
            "mpm_max": rec["mpm"].get("max", ""),
            "mpm_median": rec["mpm"].get("median", ""),
            "mpm_avg": rec["mpm"].get("avg", ""),
            # Pattern Length values (in order: min, max, median, avg)
            "len_min": rec["length"].get("min", ""),
            "len_max": rec["length"].get("max", ""),
            "len_median": rec["length"].get("median", ""),
            "len_avg": rec["length"].get("avg", ""),
        }
        rows.append(row)

# -----------------------
# LaTeX Table Output
# -----------------------

def print_latex_table(rows, decimals):
    print(r"\begin{table*}[ht]")
    print(r"\centering")
    # 12 columns: Protocol, Direction, SGH Count, Unique Rule Count, and 8 columns for analysis
    # print(r"\begin{tabular}{|l|l|r|r|r|r|r|r|r|r|r|r|}")
    print(r"\begin{tabular}{|l|l|r|r|r|r|r|r|}")
    print(r"\hline")
    # First header row: single multi-column for MPM analysis spanning 8 columns
    # header1 = (r"\textbf{Protocol} & \textbf{Direction} & \textbf{SGH Count} & \textbf{Unique Rule Count} & "
    #            r"\multicolumn{8}{c|}{\textbf{Per SGH MPM Packet-payload Patterns}} \\")
    header1 = (r"\textbf{Protocol} & \textbf{Direction} & \textbf{SGH Count} & \textbf{Unique Rule Count} & "
               r"\multicolumn{4}{c|}{\textbf{Per SGH MPM Packet-payload Pattern Count}} \\")
    print(header1)
    print(r"\hline")
    # Second header row: split into two groups (Count and Length) each spanning 4 columns
    # header2 = (r" &  &  &  & \multicolumn{4}{c|}{Count} \\") # & \multicolumn{4}{c|}{Length} \\")
    # print(header2)
    # print(r"\hline")
    # Third header row: sub-columns for each group
    # header3 = r" &  &  &  & Min & Max & Median & Avg & Min & Max & Median & Avg \\"
    header3 = r" &  &  &  & Min & Max & Median & Avg \\"
    print(header3)
    print(r"\hline")
    
    # For each row, format using the given number of decimals for the MPM analysis values.
    for rec in rows:
        # SGH Count and Unique Rule Count are printed as integers.
        # For the MPM (Count) and Pattern Lengths values use f-string formatting based on the decimals parameter.
        mpm_min = f"{rec['mpm_min']:.{decimals}f}" if rec['mpm_min'] != "" else ""
        mpm_max = f"{rec['mpm_max']:.{decimals}f}" if rec['mpm_max'] != "" else ""
        mpm_median = f"{rec['mpm_median']:.{decimals}f}" if rec['mpm_median'] != "" else ""
        mpm_avg = f"{rec['mpm_avg']:.{decimals}f}" if rec['mpm_avg'] != "" else ""
        # len_min = f"{rec['len_min']:.{decimals}f}" if rec['len_min'] != "" else ""
        # len_max = f"{rec['len_max']:.{decimals}f}" if rec['len_max'] != "" else ""
        # len_median = f"{rec['len_median']:.{decimals}f}" if rec['len_median'] != "" else ""
        # len_avg = f"{rec['len_avg']:.{decimals}f}" if rec['len_avg'] != "" else ""
        
        row_line = (f"{rec['protocol']} & {rec['direction']} & {rec['sgh']} & {rec['unique']:,} & "
                    f"{mpm_min} & {mpm_max} & {mpm_median} & {mpm_avg} \\\\ ")
                    # Removing the length values for now - not used in the text
                    # f"{mpm_min} & {mpm_max} & {mpm_median} & {mpm_avg} & "
                    # f"{len_min} & {len_max} & {len_median} & {len_avg} \\\\")
        print(row_line)
        print(r"\hline")
    print(r"\end{tabular}")
    print(r"\caption{Distribution of Signature Group Heads (SGHs) and rules by protocol and directionality along with per SGH MPM packet-payload patterns.}")
    print(r"\label{tab:sgh_rule_distribution}")
    print(r"\end{table*}")

# Print the LaTeX table with the desired decimal formatting
print_latex_table(rows, decimals)

