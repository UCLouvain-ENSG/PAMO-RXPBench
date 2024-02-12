import pandas as pd
import matplotlib.pyplot as plt
import argparse
import itertools
import numpy as np
import importlib.util
import os

def load_style_module(style_filepath):
    """Dynamically load a style module from a given filepath."""
    if not os.path.exists(style_filepath):
        raise FileNotFoundError(f"Style file '{style_filepath}' not found.")
    spec = importlib.util.spec_from_file_location("matplotlibstyle", style_filepath)
    style_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(style_module)
    return style_module

def main():
    # --- 1. Parse Command Line Arguments ---
    parser = argparse.ArgumentParser(
        description="Plot average packet latency vs. average burst size with error bars for multiple runs, "
                    "assigning colors and styles by engine and workload (light/medium/intensive).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input_file", 
                        help="Path to the CSV file with the data", 
                        default="results_selected_aggr.csv")
    parser.add_argument("--pandas_query", 
                        help="Pandas query string to filter the rows", 
                        default="index >= 0")
    parser.add_argument("--latency_col", 
                        help="Column name for the per-packet latency measurement (e.g., in ns or cycles)", 
                        default="app_avg_ns_to_process_a_packet_from_a_burst")
    parser.add_argument("--burst_col", 
                        help="Column name for the average burst size", 
                        default="app_avg_burst_size")
    parser.add_argument("--output_file", 
                        help="Filename for the output plot", 
                        default="latency_vs_burst_size.pdf")
    parser.add_argument("--paper_ready", 
                        help="Apply paper-ready formatting to the plot", 
                        action="store_true")
    # New argument to select a matplotlib style file.
    parser.add_argument("--style_file", 
                        help="Path to the matplotlib style file", 
                        default="matplotlibstyle.py")
    args = parser.parse_args()

    # --- 1.1 Load Matplotlib Style Module ---
    try:
        style_mod = load_style_module(args.style_file)
    except Exception as e:
        print(f"Error loading style file: {e}")
        return

    # --- 2. Load Data and (optionally) Filter ---
    df = pd.read_csv(args.input_file)
    df = df.rename(columns=lambda x: x.strip())
    # Apply filtering if a query is provided
    df = df.query(args.pandas_query).copy()

    # --- 3. Derive the Pattern Matching Engine Column ---
    # For this plot, if param_hs_enabled equals 1 then the engine is "HS", else "RXP".
    if "param_hs_enabled" not in df.columns:
        print("Error: 'param_hs_enabled' column not found in the data.")
        return
    df["engine"] = df["param_hs_enabled"].apply(lambda x: "HS" if int(x) == 1 else "RXP")

    # --- 4. Verify Required Columns Exist ---
    required_columns = [args.burst_col, args.latency_col, "param_pkt_size", "param_n_rules"]
    for col in required_columns:
        if col not in df.columns:
            print(f"Error: Required column '{col}' not found in the data.")
            return

    # --- 5. Group Data ---
    # Group by engine, packet size, number of rules, and burst size.
    group_cols = ["engine", "param_pkt_size", "param_n_rules", args.burst_col]
    grouped = df.groupby(group_cols)[args.latency_col].agg(["mean", "std"]).reset_index()

    # --- 6. Build Marker and Linestyle Mappings ---
    # Marker mapping based on unique rule counts.
    unique_rules = sorted(df["param_n_rules"].unique(), key=lambda x: float(x))
    marker_symbols = ['o', 's', '^', 'd']
    marker_cycle = itertools.cycle(marker_symbols)
    marker_mapping = {rule: next(marker_cycle) for rule in unique_rules}
    
    # Linestyle mapping based on unique packet sizes.
    unique_pkt = sorted(df["param_pkt_size"].unique(), key=lambda x: float(x))
    linestyle_patterns = ['-', '--', ':', '-.']
    linestyle_cycle = itertools.cycle(linestyle_patterns)
    linestyle_mapping = {pkt: next(linestyle_cycle) for pkt in unique_pkt}

    # --- 7. Build Global Color Mapping ---
    # We use keys based on (engine, param_n_rules, param_pkt_size)
    unique_keys = set()
    for _, row in grouped.iterrows():
        key = (row["engine"], row["param_n_rules"], row["param_pkt_size"])
        unique_keys.add(key)
    # Group these keys by engine.
    mode_groups = {}
    for key in unique_keys:
        engine = key[0]
        mode_groups.setdefault(engine, []).append(key)
    color_mapping = {}
    cmap_dict = {"RXP": plt.get_cmap("Oranges"), "HS": plt.get_cmap("Blues"), "Unknown": plt.get_cmap("Greys")}
    for engine, keys in mode_groups.items():
        n = len(keys)
        cmap = cmap_dict.get(engine, plt.get_cmap("viridis"))
        # Sort keys by numeric rule count and packet size
        keys_sorted = sorted(keys, key=lambda k: (float(k[1]), float(k[2])))
        for j, key in enumerate(keys_sorted):
            color_mapping[key] = cmap((j + 1) / (n + 1))

    # --- 8. Plot the Data ---
    plt.figure(figsize=(10, 6))
    
    # Group by engine, param_pkt_size, and param_n_rules (the variant) leaving burst size as the x-axis.
    for (engine, pkt_size, n_rules), group in grouped.groupby(["engine", "param_pkt_size", "param_n_rules"]):
        # Sort by burst size
        group = group.sort_values(args.burst_col)
        # Use the variant key for color mapping.
        variant_key = (engine, n_rules, pkt_size)
        color = color_mapping.get(variant_key, "black")
        # Get marker and linestyle based on rule count and packet size.
        marker = marker_mapping.get(n_rules, "o")
        linestyle = linestyle_mapping.get(pkt_size, "-")
        
        # Determine the label based on workload:
        # • Light workload: 2048 rules paired with 1500-byte packets.
        # • Medium workload: 28255 rules paired with 9000-byte packets.
        # • Intensive workload: 28255 rules paired with 1500-byte packets.
        # if int(n_rules) == 2048 and int(pkt_size) == 1500:
        #     label = f"{engine}, Light workload"
        # elif int(n_rules) == 28255 and int(pkt_size) == 9000:
        #     label = f"{engine}, Medium workload"
        # elif int(n_rules) == 28255 and int(pkt_size) == 1500:
        #     label = f"{engine}, Intensive workload"
        # else:
        #     label = f"{engine}, {n_rules} rules, {pkt_size}-byte packets"
        label = f"{engine}, {n_rules} rules, {pkt_size}-byte packets"
        
        # Plot error bars: x-axis is the burst size, y-axis is the latency mean and std as error.
        plt.errorbar(
            group[args.burst_col],      # x-axis: average burst size
            group["mean"],              # y-axis: mean latency
            yerr=group["std"],          # error bars: standard deviation
            marker=marker,
            linestyle=linestyle,
            color=color,
            capsize=5,
            label=label
        )
    
    # --- 9. Configure Plot Axes and Labels ---
    max_burst_size = grouped[args.burst_col].max()
    tick_step = 2
    x_ticks = np.arange(0, max_burst_size + tick_step, tick_step)
    plt.xticks(ticks=x_ticks)
    plt.xlabel("Average Burst Size")
    yaxis_unit = "[ns]" if args.latency_col == "app_avg_ns_to_process_a_packet_from_a_burst" else "[cycles]"
    plt.ylabel(f"Average Packet Processing Time {yaxis_unit}")

    # Apply grid with style-defined properties
    if hasattr(style_mod, "graph_tick_params"):
        grid_linestyle = style_mod.graph_tick_params.get("grid_linestyle", "dotted")
        grid_color = style_mod.graph_tick_params.get("grid_color", "#444444")
        plt.grid(True, linestyle=grid_linestyle, color=grid_color)
        # Set the tick parameters (excluding grid-specific keys)
        tick_params = style_mod.graph_tick_params.copy()
        for key in ["grid_linestyle", "grid_color"]:
            tick_params.pop(key, None)
        plt.tick_params(**tick_params)
    else:
        plt.grid(True)
    
    # Use legend parameters from style module if available.
    if hasattr(style_mod, "graph_legend_params"):
        plt.legend(**style_mod.graph_legend_params)
    else:
        plt.legend(loc="best")
    
    if args.paper_ready:
        plt.xlabel("Average Burst Size", fontsize=16)
        plt.ylabel(f"Average Packet Processing Time {yaxis_unit}", fontsize=16)
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)
    
    plt.tight_layout()
    plt.savefig(args.output_file)
    print(f"Plot saved to '{args.output_file}'")
    plt.show()

if __name__ == "__main__":
    main()
