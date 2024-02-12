#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import sys
import importlib.util

def to_bool(val):
    if isinstance(val, str):
        return val.lower() in ['true', '1', 'yes']
    return bool(val)

def convert_lcores(x):
    """
    If x is a range like '0-7', convert to int(7)-int(0) = 7.
    Otherwise, return it as float.
    """
    try:
        parts = str(x).split('-')
        if len(parts) == 2:
            return int(parts[1]) - int(parts[0])
        else:
            return float(x)
    except Exception:
        return x

def apply_grid_from_style(ax, style_dict):
    """
    Turn on the grid using the linestyle/color stored in style_dict.
    style_dict is expected to have keys 'grid_linestyle' and 'grid_color'.
    """
    linestyle = style_dict.get("grid_linestyle", "dotted")
    color     = style_dict.get("grid_color", "#444444")
    ax.grid(True, which="both", axis="both",
            linestyle=linestyle, color=color)

def format_with_commas(n):
    """Format an integer with thousands separators (e.g. 4648 → '4,648')."""
    return f"{n:,}"

def format_thousands(n: int) -> str:
    return f"{n/1000:.1f}K"

def main():
    parser = argparse.ArgumentParser(
        description="Plot zero‐loss throughput vs. cores, two subplots (one per rule count). "
                    "CPU = given by each file’s LABEL. Subtitles show literal/PCRE counts."
    )
    parser.add_argument(
        "--input_file",
        nargs=2,
        action="append",
        metavar=("FILE", "LABEL"),
        help="CSV file path followed by a label (e.g. 'ARM' or 'x86').",
        required=True
    )
    parser.add_argument(
        "--pandas_query",
        help="Query to filter pandas data (e.g. 'param_pkt_size != 9000').",
        default="index >= 0"
    )
    parser.add_argument(
        "--groupby",
        help=(
            "Comma‐separated list of columns to group by. Must be exactly: "
            "param_hs_enabled,param_rgx_enabled,param_pkt_size,param_n_rules,param_lcores"
        ),
        default="param_hs_enabled,param_rgx_enabled,param_pkt_size,param_n_rules,param_lcores"
    )
    parser.add_argument(
        "--zero-loss-threshold",
        type=float,
        default=99.5,
        help="Threshold for 'processed_rate_percent' to be considered zero‐loss."
    )
    parser.add_argument(
        "--y_axis",
        default="param_target_tp",
        help="Column name to use on the Y‐axis."
    )
    parser.add_argument(
        "--x_axis",
        default="param_lcores",
        help="Column name to use on the X‐axis."
    )
    parser.add_argument(
        "--share_y",
        action="store_true",
        default=False,
        help="If specified, both subplots share the same Y‐axis limits."
    )
    parser.add_argument(
        "--stylesheet",
        help="Path to matplotlib style file (defines grid linestyle/color).",
        default="matplotlibstyle.py"
    )
    parser.add_argument(
        "--graph_title",
        default="",
        help="(Optional) Overall figure title above the legend."
    )
    args = parser.parse_args()

    # -----------------------------------------------------
    # (A) Mapping of exact metadata for known rule counts.
    # -----------------------------------------------------
    # If we see exactly “2048” or “28255”, use these exact literal/PCRE counts.
    rule_metadata = {
        2048: (4648, 131),
        28255: (62108, 1886)
    }
    # Multipliers for estimates if a rule count is not in rule_metadata:
    literal_multiplier = 2.198124226
    pcre_multiplier    = 0.066749248

    # -----------------------------------------------------
    # 1) Load the external style file so we can draw grids exactly as before.
    # -----------------------------------------------------
    spec = importlib.util.spec_from_file_location("mplstyle", args.stylesheet)
    mplstyle = importlib.util.module_from_spec(spec)
    sys.modules["mplstyle"] = mplstyle
    spec.loader.exec_module(mplstyle)
    # Now mplstyle.graph_tick_params is available.

    # -----------------------------------------------------
    # 2) Parse groupby columns; ensure x_axis is among them.
    # -----------------------------------------------------
    groupby_cols = [col.strip() for col in args.groupby.split(",") if col.strip()]
    if args.x_axis not in groupby_cols:
        sys.exit(f"Error: x_axis '{args.x_axis}' is not in the groupby list: {groupby_cols}")
    variant_cols = list(groupby_cols)

    # -----------------------------------------------------
    # 3) FIRST PASS: Collect all distinct rule counts across both CSVs.
    # -----------------------------------------------------
    all_rule_counts = set()
    for file_path, file_label in args.input_file:
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            sys.exit(f"Error loading '{file_path}': {e}")

        # Strip whitespace from column names & string cells
        df = df.rename(columns=lambda x: x.strip())
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # Filter out rows below zero‐loss threshold if that column exists
        if "processed_rate_percent" in df.columns:
            df = df[df["processed_rate_percent"] >= args.zero_loss_threshold]

        # Apply the user‐supplied pandas_query
        try:
            df = df.query(args.pandas_query)
        except Exception as e:
            sys.exit(f"Error applying pandas_query '{args.pandas_query}': {e}")

        if "param_n_rules" not in df.columns:
            sys.exit("Error: CSV must contain a column named 'param_n_rules'.")
        all_rule_counts.update(df["param_n_rules"].unique())

    sorted_rules = sorted(all_rule_counts, key=lambda x: float(x))
    if len(sorted_rules) == 0:
        sys.exit("Error: No rule counts found in any CSV.")

    # -----------------------------------------------------
    # 4) Build figure & subplots: one subplot per rule count
    # -----------------------------------------------------
    n_rules_total = len(sorted_rules)
    fig, axes = plt.subplots(
        1, n_rules_total,
        sharey=args.share_y,
        figsize=(5, 2.5)
    )
    
    if n_rules_total == 1:
        axes = [axes]

    global_handles = []
    global_labels  = []
    seen_labels    = set()
    local_max_y_list = [0.0] * n_rules_total

    color_arm = "#1f77b4"   # blue
    color_x86 = "#d62728"   # red

    # -----------------------------------------------------
    # 5) For each rule count, plot that subplot and gather local_max_y
    # -----------------------------------------------------
    for idx, n_rules in enumerate(sorted_rules):
        ax = axes[idx]
        local_max_y = 0.0

        # Determine literal/PCRE counts or estimates:
        if n_rules in rule_metadata:
            (exact_literals, exact_pcres) = rule_metadata[n_rules]
        else:
            exact_literals = round(n_rules * literal_multiplier)
            exact_pcres    = round(n_rules * pcre_multiplier)

        # Loop over both CSVs (one labeled “ARM,” one labeled “x86”)
        for file_path, cpu_label in args.input_file:
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                sys.exit(f"Error loading '{file_path}': {e}")
            df = df.rename(columns=lambda x: x.strip())
            df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

            if "processed_rate_percent" in df.columns:
                df = df[df["processed_rate_percent"] >= args.zero_loss_threshold]
            try:
                df = df.query(args.pandas_query)
            except Exception as e:
                sys.exit(f"Error applying pandas_query '{args.pandas_query}': {e}")

            df = df[df["param_n_rules"] == n_rules]
            if len(df) == 0:
                continue

            try:
                agg_df = df.groupby(variant_cols).agg({args.y_axis: "max"}).reset_index()
            except Exception as e:
                sys.exit(f"Error during groupby/agg on '{file_path}': {e}")

            def get_mode(r):
                hs  = to_bool(r["param_hs_enabled"])
                rgx = to_bool(r["param_rgx_enabled"])
                if (not hs) and rgx:
                    return "RXP"
                elif hs and (not rgx):
                    return "HS"
                else:
                    return "Unknown"

            agg_df["mode"] = agg_df.apply(get_mode, axis=1)

            if args.y_axis in agg_df.columns and len(agg_df) > 0:
                local_max_this_cpu = agg_df[args.y_axis].max()
                if local_max_this_cpu > local_max_y:
                    local_max_y = local_max_this_cpu

            agg_df = agg_df.sort_values(by=args.x_axis)

            for (mode,), group in agg_df.groupby(["mode"]):
                if mode not in ("HS", "RXP"):
                    continue

                x_vals = group[args.x_axis].apply(convert_lcores).values
                y_vals = group[args.y_axis].values

                color = color_arm if (cpu_label == "ARM") else color_x86
                marker = 'x' if (mode == "HS") else 'o'
                
                if mode == "HS":
                    label_text = f"HS on {cpu_label}"
                elif mode == "RXP":
                    label_text = f"{cpu_label} to RXP"
                plot_label = label_text if (label_text not in seen_labels) else None

                ax.plot(
                    x_vals,
                    y_vals,
                    linestyle='-',
                    marker=marker,
                    markersize=5.0,
                    color=color,
                    label=plot_label
                )

                if plot_label is not None:
                    h = ax.lines[-1]
                    global_handles.append(h)
                    global_labels.append(label_text)
                    seen_labels.add(label_text)

        local_max_y_list[idx] = local_max_y

        # Keep the grid ON
        apply_grid_from_style(ax, mplstyle.graph_tick_params)

        # X‐axis ticks
        subset_cores = set()
        for file_path, _ in args.input_file:
            df2 = pd.read_csv(file_path)
            df2 = df2.rename(columns=lambda x: x.strip())
            df2 = df2.applymap(lambda x: x.strip() if isinstance(x, str) else x)
            if "processed_rate_percent" in df2.columns:
                df2 = df2[df2["processed_rate_percent"] >= args.zero_loss_threshold]
            try:
                df2 = df2.query(args.pandas_query)
            except:
                pass
            df2 = df2[df2["param_n_rules"] == n_rules]
            subset_cores.update(df2[args.x_axis].apply(convert_lcores).unique())

        unique_cores = sorted(subset_cores, key=lambda x: float(x))
        ax.set_xticks(unique_cores)
        ax.set_xlabel("Cores used")

        # Build a two‐line title with exact/estimated metadata
        line1 = f"{n_rules} rules"
        line2 = (f"({format_thousands(exact_literals)} literals, "
                 f"{format_thousands(exact_pcres)} PCREs)")
        ax.set_title(f"{line1}\n{line2}",
                     loc='center',
                    fontsize='medium',
                     pad=9.5,
                     backgroundcolor='white')

    # -----------------------------------------------------
    # 6) Set Y‐limits & Y‐ticks now that we've collected all local_max_y
    # -----------------------------------------------------
    if args.share_y:
        global_max_y = max(local_max_y_list)
        top_limit = (int(global_max_y // 10) + 1) * 10
        common_yticks = list(range(0, top_limit + 1, 10))

        for ax in axes:
            ax.set_ylim(0, top_limit)
            ax.set_yticks(common_yticks)
        axes[0].set_ylabel("Max. Throughput [Gbps]")

    else:
        for idx, ax in enumerate(axes):
            lm = local_max_y_list[idx]
            this_rules = sorted_rules[idx]

            if this_rules == 2048:
                tick_interval = 10
                yticks = [0, 10, 20, 30, 40, 50]
            elif this_rules == 28255:
                tick_interval = 2
                yticks = [0, 2, 4, 6, 8, 10, 12]
            else:
                tick_interval = 10
                top_ = (int(lm // 10) + 1) * 10
                yticks = list(range(0, top_ + 1, 10))

            top_limit = (int(lm // tick_interval) + 1) * tick_interval
            ax.set_ylim(0, top_limit)
            ax.set_yticks(yticks)

            if idx == 0:
                ax.set_ylabel("Max. Throughput [Gbps]")

    # -----------------------------------------------------
    # 7) Shared legend
    # -----------------------------------------------------
    desired_order = [
        "HS on ARM",
        "ARM to RXP",
        "HS on x86",
        "x86 to RXP"
    ]
    final_handles = []
    final_labels  = []
    for lbl in desired_order:
        if lbl in seen_labels:
            idx0 = global_labels.index(lbl)
            final_handles.append(global_handles[idx0])
            final_labels.append(lbl)

    # Make sure the legend does not overflow:
    top_margin = 0.88 if args.graph_title else 1.0
    fig.legend(
        final_handles,
        final_labels,
        loc='upper center',
        ncol=2,
        bbox_to_anchor=(0.5, top_margin),
        frameon=False
    )

    # -----------------------------------------------------
    # 8) Overall title, final layout, save & show
    # -----------------------------------------------------
    if args.graph_title:
        fig.suptitle(args.graph_title, y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.8])
    plt.savefig("results.pdf")
    plt.show()

if __name__ == "__main__":
    main()
