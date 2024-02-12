import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt
import seaborn as sns
import argparse

CSV_NAN = "NaN"

# function to process regex related columns:
def process_rgx_cols(df):
    rgx_df = df[df['param_rgx_enabled'] == 1].copy()
    if rgx_df.empty:
        # Direct initialization of values to avoid SettingWithCopyWarning
        for col in ['rgx_processed_rate_0_to_1', 'rgx_processed_rate_of_rx_percent', 
                    'rgx_weighted_avg_latency_cycles', 'rgx_matches_per_rcvd_kB', 
                    'subsets_inspected_subset_size', 'subsets_cnt']:
            rgx_df[col] = 0
        return rgx_df
    
    rgx_df['param_rule_subset_ratio'] = rgx_df['param_rule_subset_ratio'].astype(str)
    rgx_df[['subsets_inspected_subset_size', 'subsets_cnt']] = rgx_df['param_rule_subset_ratio'].apply(
        lambda x: pd.Series([float(x.split(':')[0]), len(x.split(':'))])
    )
    
    # Columns that represent dequeued RGX packets for various bucket sizes
    rgx_deq_cols = [col for col in rgx_df.columns if '_deq_brst_pkts_cnt' in col]
    rgx_enq_cols = [col for col in rgx_df.columns if '_enq_brst_pkts_cnt' in col]
    rgx_deq_avg_cycles_cols = [col for col in rgx_df.columns if '_deq_avg_rtt_cycles' in col]
    rgx_deq_ttl_cycles_cols = [col for col in rgx_df.columns if '_deq_rtt_ttl_cycles' in col]
    rgx_matches_cols = [col for col in rgx_df.columns if 'rgx' in col and '_patterns_matched' in col]

    # Convert all data to numeric, coerce errors to NaN, then fill NaN with 0
    for col in rgx_df[rgx_deq_cols + rgx_enq_cols + rgx_deq_avg_cycles_cols + rgx_deq_ttl_cycles_cols + rgx_matches_cols]:
        rgx_df[col] = pd.to_numeric(rgx_df[col], errors='coerce').fillna(0)
        
    # Summing up the dequeued RGX packets for each row
    rgx_df['sum_rgx_dequeued_packets'] = rgx_df[rgx_deq_cols].sum(axis=1)
    rgx_df['sum_rgx_enqueued_packets'] = rgx_df[rgx_enq_cols].sum(axis=1)
    rgx_df['median_rgx_deq_avg_cycles_cols'] = rgx_df[rgx_deq_avg_cycles_cols].median(axis=1)
    rgx_df['sum_rgx_deq_ttl_cycles_cols'] = rgx_df[rgx_deq_ttl_cycles_cols].sum(axis=1)
    rgx_df['sum_rgx_matched_patterns'] = rgx_df[rgx_matches_cols].sum(axis=1)
    
    # using where statement calc this column using rgx_df['sum_rgx_deq_ttl_cycles_cols'] / rgx_df['sum_rgx_dequeued_packets'], but you need to account for 0 division
    rgx_df['avg_cycles_ttl_cycles_div_ttl_pkts'] = (rgx_df['sum_rgx_deq_ttl_cycles_cols'] / rgx_df['sum_rgx_dequeued_packets']).replace([np.inf, -np.inf], 0)
    rgx_df['rgx_processed_rate_0_to_1'] = (rgx_df['sum_rgx_dequeued_packets'] / rgx_df['port0_rx_phy_packets']).replace([np.inf, -np.inf], 0)
    # should be the same as the processed rate otherwise the bottleneck is the RGX engine
    rgx_df['rgx_processed_rate_of_rx_percent'] = (rgx_df['sum_rgx_dequeued_packets'] / rgx_df['port0_rx_good_packets']).replace([np.inf, -np.inf], 0) * 100
    rgx_df['rgx_matches_per_rcvd_kB'] = (rgx_df['sum_rgx_matched_patterns'] / (rgx_df['port0_rx_good_bytes'] / 1000)).replace([np.inf, -np.inf], 0)
    
    # Initialize a list to hold weighted average latency for each row
    weighted_avg_lat_cycles = []

    # Iterate through each row in the DataFrame
    for index, row in rgx_df.iterrows():
        total_latency = 0
        total_packets = 0
        # Iterate through each RGX bucket size
        for bs in range(4, 65, 4):  # Assuming bucket sizes range from 4 to 64
            avg_latency_col = f'rgx_bs{bs}_deq_avg_rtt_cycles'
            pkts_cnt_col = f'rgx_bs{bs}_deq_brst_pkts_cnt'
            
            # Calculate total latency for this bucket size
            total_latency += row[avg_latency_col] * row[pkts_cnt_col]
            # Accumulate total packets
            total_packets += row[pkts_cnt_col]

        # Calculate weighted average latency for this row and add it to the list
        if total_packets > 0:
            weighted_avg_lat_cycles.append(total_latency / total_packets)
        else:
            weighted_avg_lat_cycles.append(0)

    # Add the weighted average latencies as a new column in the DataFrame
    rgx_df['rgx_weighted_avg_latency_cycles'] = weighted_avg_lat_cycles
    return rgx_df

def process_hs_cols(df):
    hs_df = df[df['param_hs_enabled'] == 1].copy()
    if hs_df.empty:
        # Direct initialization of values to avoid SettingWithCopyWarning
        for col in ['param_hs_flags', 'hs_total_scans', 
                    'hs_avg_scan_time_cycles', 'hs_processed_rate_0_to_1', 
                    'hs_matches_per_rcvd_kB']:
            hs_df[col] = 0
        return hs_df
    
    hs_df['hs_processed_rate_0_to_1'] = hs_df['hs_total_scans'] / hs_df['port0_rx_phy_packets'].replace(0, pd.NA)
    hs_df['hs_matches_per_rcvd_kB'] = hs_df['hs_total_patterns_matched'] / (hs_df['port0_rx_good_bytes'] / 1000)
    return hs_df
    
def process_pktgen_cols(df):
    if 'tx_p0_b2b_latency_cycles_avg' not in df.columns:
        df['tx_p0_b2b_latency_cycles_avg'] = 0
    if 'tx_p0_b2b_latency_us_avg' not in df.columns:
        df['tx_p0_b2b_latency_us_avg'] = 0

def postprocess_all(df):
    # Process the DataFrame to prepare for plotting
    # Processed rate
    # Check if both columns have a non-zero value in any row
    if ((df['hs_processed_rate_0_to_1'] > 0) & (df['rgx_processed_rate_0_to_1'] > 0)).any():
        raise ValueError("Both 'hs_processed_rate_0_to_1' and 'rgx_processed_rate_0_to_1' columns have non-zero values in the same row.")

    # Combine the two columns, assuming that only one of them can have a non-zero value at a time
    df['combined_processed_rate_0_to_1'] = df['hs_processed_rate_0_to_1'] + df['rgx_processed_rate_0_to_1']

    # Converting processed rates to percentages
    df['processed_rate_percent'] = df['combined_processed_rate_0_to_1'] * 100
    df['matches_per_rcvd_kB'] = df['hs_matches_per_rcvd_kB'] + df['rgx_matches_per_rcvd_kB']

    # Latency
    # Check if both columns have a non-zero value in any row
    df['rgx_weighted_avg_latency_cycles'] = df['rgx_weighted_avg_latency_cycles'].fillna(0).astype('float64')
    df['hs_avg_scan_time_cycles'] = df['hs_avg_scan_time_cycles'].fillna(0).astype('float64')
    if ((df['rgx_weighted_avg_latency_cycles'] > 0) & (df['hs_avg_scan_time_cycles'] > 0)).any():
        raise ValueError("Both 'rgx_weighted_avg_latency_cycles' and 'hs_avg_scan_time_cycles' columns have non-zero values in the same row.")

    # Combine the two columns, assuming that only one of them can have a non-zero value at a time
    df['combined_scan_avg_cycles'] = df['rgx_weighted_avg_latency_cycles'] + df['hs_avg_scan_time_cycles']

    # Create labels
    # df['label'] = df.apply(lambda row: (f"LC:{row['param_lcores']}_NR:{row['param_n_rules']}_PS:{row['param_pkt_size']}_RE:{row['param_rgx_enabled']}_HS:{row['param_hs_enabled']}" + f"_HSFLGS:{row['param_hs_flags']}" if 'param_hs_flags' in df.columns else "" + f"_NRD:{row['param_nb_rgx_desc']}"), axis=1)
    # 
    df['label'] = df.apply(
        lambda row: 
            
            f"LC:{row['param_lcores']} NR:{row['param_n_rules']} RC:{row['param_rules_use_content_kw']} RP:{row['param_rules_use_pcre_kw']} PS:{row['param_pkt_size']} RE:{row['param_rgx_enabled']}" + (f" NRD:{row['param_nb_rgx_desc']}" if row['param_rgx_enabled'] == 1 else "") + (f" RG:{row['param_rule_subset_ratio']}" if "param_rule_subset_ratio" in row else "") + f" HS:{row['param_hs_enabled']}" + (f" HSFLGS:{row['param_hs_flags']}" if row['param_hs_enabled'] == 1 else "") + f" PDB:{row['param_pattern_db']}", axis=1)


def main():
    parser = argparse.ArgumentParser(description="Process data for the plot.py script.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input_file", help="The CSV file to process", default="results.csv")

    # Parse command line arguments
    args = parser.parse_args()
    

    # Load CSV data into DataFrame
    df = pd.read_csv(args.input_file)
    # Initial CSV transforms
    df = df.rename(columns=lambda x: x.strip())
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df.replace(CSV_NAN, pd.NA, inplace=True)
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except ValueError: # ignore all errors
            pass
    
    process_pktgen_cols(df)
    rgx_df = process_rgx_cols(df)
    hs_df = process_hs_cols(df)
    
    rgx_filtered = rgx_df[rgx_df['param_rgx_enabled'] == 1]
    hs_filtered = hs_df[hs_df['param_hs_enabled'] == 1]
    new_df = pd.concat([rgx_filtered, hs_filtered], axis=0)
    new_df = new_df.sort_index()

    # Identify unique columns in both DataFrames and combine them
    unique_rgx_cols = set(rgx_filtered.columns) - set(hs_filtered.columns)
    unique_hs_cols = set(hs_filtered.columns) - set(rgx_filtered.columns)
    unique_columns = (unique_rgx_cols | unique_hs_cols)

    # Fill NA with 0 for unique columns in the concatenated DataFrame
    for col in unique_columns:
        if col in new_df.columns:
            new_df[col] = new_df[col].fillna(0)

    postprocess_all(new_df)

    # Saving the aggregated data to a new CSV file
    new_df.to_csv('results_aggregated_rgx_dequeued_packets.csv', index=False)
    print("Aggregated data saved to 'aggregated_rgx_dequeued_packets.csv'.")

    param_cols = rgx_deq_cols = [col for col in new_df.columns if 'param_' in col]
    app_cols = [ col for col in new_df.columns if 'app_' in col]
    selected_cols = param_cols + app_cols + ['rgx_processed_rate_0_to_1', 'rgx_weighted_avg_latency_cycles', 'rgx_processed_rate_0_to_1', 'rgx_weighted_avg_latency_cycles', 'rgx_processed_rate_of_rx_percent', 'tx_p0_b2b_latency_cycles_avg', 'tx_p0_b2b_latency_us_avg', 'processed_rate_percent', 'matches_per_rcvd_kB', 'combined_scan_avg_cycles', 'subsets_inspected_subset_size', 'subsets_cnt', 'label']
    selected_new_df = new_df[sorted(selected_cols)].reset_index()
    selected_new_df.to_csv('results_selected_aggr.csv', index=False)
    print("Aggregated data for plotting saved to 'results_selected_aggr.csv'.")

# write main
if __name__ == "__main__":
    main()
