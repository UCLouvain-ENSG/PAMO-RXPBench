import pandas as pd
import matplotlib.pyplot as plt
import argparse
from textwrap import wrap

# Map of possible Y axis choices to their respective labels and colors
y_axis_options = {
    'processed_rate_percent': ('TPT', 'Processed Rate [%]', 'blue'),
    # should be the same as the processed rate otherwise the bottleneck is the RGX engine
    'rgx_processed_rate_of_rx_percent': ('MpKB', 'RGX dequeued to Port received ratio [%]', 'grey'),
    'combined_scan_avg_cycles': ('LAT', 'Latency Cycles', 'red'),
    'tx_p0_b2b_latency_cycles_avg': ('PGLAT', 'Pktgen Latency Cycles', 'green'),
    'tx_p0_b2b_latency_us_avg': ('PGLAT_US', 'Pktgen Latency US', 'cyan'),
    'matches_per_rcvd_kB': ('MpKB', 'Matches per received KiloByte', 'grey'),
    'none': ('None', 'None', 'black') # dont use the axis
}

def main():
    pandas_query_default = "index >= 0"
    parser = argparse.ArgumentParser(description="Visualize data matplotlib and pandas - the input data needs to be processed by process.py first", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input_file", help="The CSV file to visualize", default="results_selected_aggr.csv")
    parser.add_argument("--pandas_query", help="The data query to filter data - examples: 'param_lcores == \"0-1\" and param_n_rules == 1' or 'param_hs_enabled == 0 and param_pkt_size > 3000'", default=pandas_query_default)
    parser.add_argument("--left_y_axis", help=f"The Y axis to plot on the left - options: {list(y_axis_options.keys())}", default="processed_rate_percent")
    parser.add_argument("--right_y_axis", help=f"The Y axis to plot on the right - options: {list(y_axis_options.keys())}", default="combined_scan_avg_cycles")

    # Parse command line arguments
    args = parser.parse_args()
    df = pd.read_csv(args.input_file)
    df = df.rename(columns=lambda x: x.strip())
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df = df.query(args.pandas_query)

    # Initialize a figure and create a twin axis for the second Y-axis
    fig, ax1 = plt.subplots(figsize=(26, 8))
    fig.subplots_adjust(right=0.75)
    
    if args.left_y_axis not in y_axis_options or args.right_y_axis not in y_axis_options:
        raise ValueError(f"Invalid --y_axis value. Expected one of {list(y_axis_options.keys())}")

    if args.left_y_axis == 'none':
        raise ValueError(f"'none' value is not supported as a --left_y_axis value.")
        
    left_sign, left_label, left_color = y_axis_options[args.left_y_axis]
    if args.right_y_axis != 'none':
        right_sign, right_label, right_color = y_axis_options[args.right_y_axis]
        ax2 = ax1.twinx()
    
    new = pd.DataFrame()
    new['label'] = df['label']
    new['param_target_tp'] = df['param_target_tp']
    new[f"mean_{args.left_y_axis}"] = df.groupby(['label', 'param_target_tp'])[args.left_y_axis].transform('mean')
    new[f"std_{args.left_y_axis}"] = df.groupby(['label', 'param_target_tp'])[args.left_y_axis].transform('std')
    # new[f"std_{args.left_y_axis}"] = new[f"std_{args.left_y_axis}"].fillna(0.01)

    
    if args.right_y_axis != 'none':
        new[f"mean_{args.right_y_axis}"] = df.groupby(['label', 'param_target_tp'])[args.right_y_axis].transform('mean')
        new[f"std_{args.right_y_axis}"] = df.groupby(['label', 'param_target_tp'])[args.right_y_axis].transform('std')
    
    # Plotting left Y axis with error bars
    for label, group in new.groupby(['label']):
        ax1.errorbar(group['param_target_tp'], group[f"mean_{args.left_y_axis}"], yerr=group[f"std_{args.left_y_axis}"], fmt='-o', label=f'{left_sign} - {label}', capsize=3) #, uplims=True, lolims=True) # remove uplims=True, lolims=True to remove arrow error bars
        if args.right_y_axis != 'none':
            ax2.errorbar(group['param_target_tp'], group[f"mean_{args.right_y_axis}"], yerr=group[f"std_{args.right_y_axis}"], fmt='--x', label=f'{right_sign} - {label}', capsize=3, uplims=True, lolims=True)

    # Setting labels, titles, and legends
    ax1.set_xlabel('Target Throughput (param_target_tp)', fontsize=14)
    ax1.set_ylabel(f"{left_sign} - {left_label} (solid line)", fontsize=14, color=left_color)
    if args.right_y_axis != 'none':
        ax2.set_ylabel(f"{right_sign} - {right_label} (dashed line)", fontsize=14, color=right_color)

    # Create combined legend from both axes
    if args.left_y_axis != 'none':
        lines_1, labels_1 = ax1.get_legend_handles_labels()
    if args.right_y_axis != 'none':
        lines_2, labels_2 = ax2.get_legend_handles_labels()
    else:
        lines_2, labels_2 = [], []
    
    # Wrap each label
    wrapped_labels1 = ['\n'.join(wrap(label, 50)) for label in labels_1]
    wrapped_labels2 = ['\n'.join(wrap(label, 50)) for label in labels_2]

    # Position the legend outside of the figure/plot to the right side
    ax1.legend(lines_1 + lines_2, wrapped_labels1 + wrapped_labels2, loc='upper left', bbox_to_anchor=(1.1, 1), borderaxespad=0.)

    plt.title('Performance Metrics by Target Throughput with Variability', fontsize=16)

    # Adjust the padding to make room for the legend outside
    plt.tight_layout(rect=[0, 0, 0.85, 1])

    plt.title(f"Queried data: {args.pandas_query if args.pandas_query != pandas_query_default else 'all'} from {args.input_file}", fontsize=12)
    plt.savefig("results.png")
    # plt.show()


if __name__ == "__main__":
    main()

