import pandas as pd
import matplotlib.pyplot as plt
import argparse
import numpy as np
import importlib.util
import sys

def main():
    # --- 1. Parse Command Line Arguments ---
    pandas_query_default = "index >= 0"
    parser = argparse.ArgumentParser(
        description="Generate heatmap from CSV data with left‐neighbor smoothing of processed_rate_percent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input_file", help="The CSV file to visualize", default="results_selected_aggr.csv")
    parser.add_argument("--pandas_query", help="Filter the data via a pandas query string", default=pandas_query_default)
    parser.add_argument("--x_axis", help="Column name to use for the X axis", default="subsets_inspected_subset_size")
    parser.add_argument("--y_axis", help="Column name to use for the Y axis", default="subsets_cnt")
    parser.add_argument("--zero_drop_thres", 
                        help="Minimal allowed processed_rate_percent (after smoothing) to be considered zero‐drop", 
                        default="99.95")
    parser.add_argument("--stylesheet", help="Path to matplotlib style file (Python file with style dicts)", default="matplotlibstyle.py")
    args = parser.parse_args()

    # --- Load matplotlib style from stylesheet ---
    stylesheet_path = args.stylesheet
    spec = importlib.util.spec_from_file_location("mplstyle", stylesheet_path)
    mplstyle = importlib.util.module_from_spec(spec)
    sys.modules["mplstyle"] = mplstyle
    spec.loader.exec_module(mplstyle)
    # Now mplstyle.graph_legend_params and mplstyle.graph_tick_params are available

    # --- 2. Load Data and Apply Initial Filtering ---
    df = pd.read_csv(args.input_file)
    df = df.rename(columns=lambda x: x.strip())
    df = df.query(args.pandas_query).copy()
    zero_drop_threshold = float(args.zero_drop_thres)

    # --- 3. Define Grouping Columns ---
    grouping_columns = [
        'param_hs_enabled', 'param_hs_flags', 'param_jumbo_frames', 
        'param_lcores', 'param_n_rules', 'param_nb_rgx_desc', 'param_pattern_db', 
        'param_pkt_size', 'param_pktgen_latency_enabled', 'param_port_forward_mode', 
        'param_port_mp_size', 'param_port_rx_descriptors', 'param_port_tx_descriptors', 
        'param_rgx_enabled', 'param_rule_subset_ratio', 'param_rules_use_content_kw', 
        'param_rules_use_pcre_kw', 'subsets_cnt', 'subsets_inspected_subset_size', 'label'
    ]

    # --- 4. Define the Smoothing and Filtering Function ---
    def find_zero_drop_throughput(group, threshold):
        group = group.sort_index().copy()
        smoothed = group['processed_rate_percent'].copy()
        if len(smoothed) > 1:
            smoothed.iloc[1:] = (smoothed.iloc[1:] + smoothed.shift(1).iloc[1:]) / 2
        group['processed_rate_percent_smoothed'] = smoothed

        valid = group[group['processed_rate_percent_smoothed'] >= threshold]
        if valid.empty:
            return None
        return valid['param_target_tp'].max()

    # --- 5. Apply the Smoothing and Filtering per Group ---
    zero_drop_df = (
        df.groupby(grouping_columns, as_index=False, group_keys=False)
          .apply(lambda g: pd.Series({
              'zero_drop_throughput': find_zero_drop_throughput(g, zero_drop_threshold)
          }))
    )
    zero_drop_df.dropna(subset=["zero_drop_throughput"], inplace=True)

    # --- 6. Pivot the Data for the Heatmap ---
    heatmap_data = zero_drop_df.pivot_table(
        index=args.y_axis,
        columns=args.x_axis,
        values='zero_drop_throughput',
        aggfunc='max'
    )

    # --- 7. Plot the Heatmap (figsize = 5 × 2.3 inches) ---
    fig, ax = plt.subplots(figsize=(5, 3))
    cax = ax.matshow(heatmap_data, cmap="viridis")
    ax.invert_yaxis()

    # Configure axis ticks and labels
    ax.xaxis.set_ticks_position('none')
    ax.xaxis.set_ticks_position('bottom')
    ax.set_xlabel(args.x_axis, labelpad=2)
    ax.set_ylabel(args.y_axis)
    ax.tick_params(**mplstyle.graph_tick_params)

    # Add a vertical colorbar on the right edge
    cbar = fig.colorbar(cax, orientation="vertical", ax=ax, pad=0.02, fraction=0.05)
    cbar.set_ticks(np.arange(5, 51, 5))
    cbar.ax.set_ylabel("Max. Throughput [Gbps]", rotation=90, labelpad=5)

    # Set tick labels based on pivot‐table indices/columns
    ax.set_xticks(np.arange(len(heatmap_data.columns)))
    ax.set_yticks(np.arange(len(heatmap_data.index)))
    ax.set_xticklabels(heatmap_data.columns)
    ax.set_yticklabels(heatmap_data.index)
    plt.xticks(rotation=30)

    # --- 8. Paper‐Ready Formatting and Overlay Text ---
    ax.set_xlabel("Rule Count", labelpad=1)
    ax.set_ylabel("Packet Length [bytes]")
    ax.set_title("")  # no title

    cmap = cax.get_cmap()
    norm = cax.norm
    for i in range(len(heatmap_data.index)):
        for j in range(len(heatmap_data.columns)):
            val = heatmap_data.iloc[i, j]
            if pd.isna(val):
                continue
            rgba = cmap(norm(val))
            luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
            text_color = "white" if luminance < 0.5 else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", color=text_color)
            
    plt.subplots_adjust(left=0.2, right=0.8, top=0.98, bottom=0.2)


    output_file = "throughput_heatmap.pdf"
    plt.savefig(output_file)  
    print(f"Heatmap saved to '{output_file}'.")
    plt.show()

if __name__ == "__main__":
    main()
