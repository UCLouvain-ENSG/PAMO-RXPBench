import pandas as pd
import matplotlib.pyplot as plt
import argparse
import importlib.util
import sys
import math

def main():
    pandas_query_default = "index >= 0"
    parser = argparse.ArgumentParser(
        description="Generate bar graph from CSV data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input_file", help="The CSV file to visualize", default="results_selected_aggr.csv")
    parser.add_argument("--pandas_query", help="The data query to filter data - e.g. 'param_lcores == \"0-1\" and param_n_rules == 1'", default=pandas_query_default)
    parser.add_argument("--x_axis", help="The column for the X axis - must be 'param_n_rules'", default="param_n_rules")
    parser.add_argument("--y_axis", help="The column for the Y axis - e.g. param_target_tp combined_scan_avg_cycles tx_p0_b2b_latency_cycles_avg", default="param_target_tp")
    parser.add_argument("--zero_drop_thres", help="Minimal allowed process rate to be considered zero-drop", default="99.95")
    parser.add_argument("--stylesheet", help="Path to matplotlib style file (Python file with style dicts)", default="matplotlibstyle.py")
    
    args = parser.parse_args()

    # --- Load matplotlib style from stylesheet ---
    stylesheet_path = args.stylesheet
    spec = importlib.util.spec_from_file_location("mplstyle", stylesheet_path)
    mplstyle = importlib.util.module_from_spec(spec)
    sys.modules["mplstyle"] = mplstyle
    spec.loader.exec_module(mplstyle)
    # Now mplstyle.graph_tick_params and mplstyle.graph_legend_params are available
    
    # Read and filter data
    df = pd.read_csv(args.input_file)
    df = df.rename(columns=lambda x: x.strip())
    df = df.query(args.pandas_query).copy()
    zero_drop_threshold = float(args.zero_drop_thres)
    df = df[df['processed_rate_percent'] >= zero_drop_threshold]
    
    # We expect x_axis to be "param_n_rules"
    # Group by (param_n_rules, subsets_cnt) and take max of y_axis
    grouped = (
        df
        .groupby([args.x_axis, 'subsets_cnt'])[args.y_axis]
        .max()
        .reset_index()
    )

    # Compute rules per subset, then lookup string literals and PCREs
    # Conversion constants
    LITERAL_MULTIPLIER = 2.198124226
    PCRE_MULTIPLIER   = 0.066749248

    # Build conversion table for exact rule counts
    # For 28 and 28255 we use provided exact values; for 282 and 2822 we compute via multipliers
    conv_table = {
        28:    (61,   2),
        282:   (int(round(282  * LITERAL_MULTIPLIER)), int(round(282  * PCRE_MULTIPLIER))),
        2822:  (int(round(2822 * LITERAL_MULTIPLIER)), int(round(2822 * PCRE_MULTIPLIER))),
        28255: (62108, 1886)
    }

    # Add columns for rules_per_subset, literals, pcres
    grouped['rules_per_subset'] = (grouped[args.x_axis] / grouped['subsets_cnt']).astype(int)
    literals_list = []
    pcre_list     = []
    for rps in grouped['rules_per_subset']:
        if rps in conv_table:
            lits, pcrs = conv_table[rps]
        else:
            # approximate if not in table
            lits  = int(round(rps * LITERAL_MULTIPLIER))
            pcrs  = int(round(rps * PCRE_MULTIPLIER))
        literals_list.append(lits)
        pcre_list.append(pcrs)
    grouped['string_literals'] = literals_list
    grouped['pcre_count']      = pcre_list

    # Sort by rules_per_subset ascending
    grouped = grouped.sort_values(by='rules_per_subset').reset_index(drop=True)

    # Build custom X-axis labels: exactly two lines each
    #   Line 1: "RPS / total_subsets"
    #   Line 2: "(LITERALS / PCRES)"
    labels = []
    for idx, row in grouped.iterrows():
        rps     = int(row['rules_per_subset'])
        subsets = int(row['subsets_cnt'])
        lits    = int(row['string_literals'])
        pcrs    = int(row['pcre_count'])
        label   = f"{rps} / {subsets}\n({lits} / {pcrs})"
        labels.append(label)

    # Y-values for the bar heights
    y_values   = grouped[args.y_axis].values
    x_positions = list(range(len(y_values)))

    # Create figure and axes with requested size
    fig, ax = plt.subplots(figsize=(5, 2.3))

    # Plot bars in solid black
    bars = ax.bar(x_positions, y_values, color='black', width=0.8)

    # Add absolute max‐throughput labels on top of each bar
    ax.bar_label(bars, fmt="%.0f", padding=3)

    # Apply tick params from stylesheet
    ax.tick_params(**mplstyle.graph_tick_params)
    # Apply grid style from stylesheet (Y-axis only)
    apply_grid_from_style(ax, mplstyle.graph_tick_params)
    ax.set_axisbelow(True)

    # Set custom X-axis ticks and labels, centered
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, rotation=0, ha='center')

    ax.set_ylim(0, 60)

    # X-axis label (two lines)
    ax.set_xlabel("Rules in each subset / Subsets\n(≈String literals / ≈PCREs)")

    # Y-axis label, moved downward by 0.125
    if args.y_axis == "param_target_tp":
        ax.set_ylabel("Max. Throughput [Gbps]")
    elif args.y_axis == "combined_scan_avg_cycles":
        ax.set_ylabel("Average Cycles (locally measured) on max throughput")
    elif args.y_axis == "tx_p0_b2b_latency_cycles_avg":
        ax.set_ylabel("Average PKTGEN CPU Cycles on MAX TPT")
    else:
        ax.set_ylabel(args.y_axis)

    # Move Y-axis label down by 0.125 in normalized axis coordinates
    # Default label‐position is (x≈-0.08, y=0.5). We keep x roughly the same and shift y.
    ax.yaxis.set_label_coords(-0.08, 0.5 - 0.125)

    # No legend anymore

    # Tight layout to accommodate two-line X labels
    fig.tight_layout()

    # Save the figure as a PDF
    plt.savefig("results_bar.pdf", bbox_inches='tight')


def apply_grid_from_style(ax, style_dict):
    grid_linestyle = style_dict.get("grid_linestyle", "dotted")
    grid_color     = style_dict.get("grid_color", "#444444")
    # Only apply grid on Y-axis (horizontal lines)
    ax.grid(True, which="both", axis="y", linestyle=grid_linestyle, color=grid_color)


if __name__ == "__main__":
    main()
