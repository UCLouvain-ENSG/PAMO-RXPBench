def divide_space(first_group_percentage: float, groups: int, total_percentage: float = 1.0):
    """
    Divide the space according to the rules provided.
    
    Args:
    - first_group_percentage: The percentage of the space to be allocated to the first group.
    - groups: The number of groups to divide the space into.
    - total_percentage: The total percentage of the space to be divided. Default is 1.0.
    
    Returns:
    - A list of percentages for each group.
    """
    # Calculate the remaining percentage to be divided among the other groups
    remaining_percentage = total_percentage - first_group_percentage
    if (groups - 1) == 0 or remaining_percentage == 0:
        return [round(first_group_percentage, 3)]
    
    other_group_percentage = remaining_percentage / (groups - 1)
    
    result = [round(first_group_percentage, 3)]
    for _ in range(groups - 1):
        result.append(round(other_group_percentage, 3))
    
    return result

def format_lists(lists):
    formatted_strings = []
    
    for lst in lists:
        # If there's only one element, return it as is
        if len(lst) == 1:
            formatted_strings.append(f'{lst[0]:.1f}')
        else:
            # Join the elements after formatting them to 3 decimal places
            formatted_string = ":".join([f"{x:.3f}".rstrip('0').rstrip('.') for x in lst])
            formatted_strings.append(f'{formatted_string}')
    
    return formatted_strings

def gen_params(group_percentage_step: int = 10, group_cnt: int = 128):
    """
    Generate parameters for the experiment.
    
    Args:
    - group_percentage_step: The step size for the group percentage. Default is 10., starts at close to 0, goes up to 100, size of the first and used subset group
    - group_cnt: The number of groups to divide the space into. Should be power of 2. Default is 128.
    

    Returns:
    - A list of formatted strings of the parameters.
    """
    params = []
    for i in range(1, 10000):
        groups = 2**i
        if (groups > group_cnt):
            break
        for j in range(0, 101, 10):
            if j == 0:
                params.append(divide_space(0.001, groups))
            else:                
                params.append(divide_space(j / 100, groups))
    
    formatted_params = format_lists(params)
    return formatted_params


#The goal of this experiment is to find out at which point we start having drops in efficiency related to the number of prefixes in the rgx
g_nreps = 1

g_test_parameters = [
    ("n_rules", [2048, 28255]),
    # ("n_rules", [2048]),
    # !!! rule_subset_ratio RXPC specific!
    #("rule_subset_ratio", ["1.0", "0.9:0.1", "0.5:0.5", "0.1:0.9", "0.1:0.2:"*3+"0.1", "0.025:"*39+"0.025"]),
    ("rule_subset_ratio", ["1.0", "0.1:" * 9 + "0.1", "0.01:" * 99 + "0.01", "0.001:" * 999 + "0.001"]),
    #("rule_subset_ratio", gen_params(group_cnt=128)),

    ("target_tp", [i for i in range(5, 53, 1)]),
    # ("target_tp", [10, 40]),
    ("pkt_size", [1500, 9000]),
    # ("pkt_size", [1500]),
    ("lcores", ['0-7']),
    ("hs_flags", ['--hs_flag_allowempty']), # '--hs_flag_allowempty --hs_flag_singlematch --hs_flag_dotall --hs_flag_prefilter']),
    ("nb_rgx_desc", [2048]),
    ("port_mp_size", [32767]),
    ("port_rx_descriptors", [16384]),
    ("port_tx_descriptors", [16384]),
    ("jumbo_frames", ["1"]),
    ("rgx_enabled", ["1"]),
    ("hs_enabled", ["0"]),
    ("port_forward_mode", ['1']), # 0: no forwarding, 1: forward to the same rx port, 2: forward to host
    ("pktgen_latency_enabled", ["1"]),
    ("rules_use_content_kw", ["1"]), # extract patterns from the content keyword
    ("rules_use_pcre_kw", ["1"]),
    ("rules_patlen_greaterthan", ["5"]),
    ("pattern_db", ["working_set.rules"])
    
        # ("n_rules", [2048, 28255]),
        # # !!! rule_subset_ratio RXPC specific!
        # ("rule_subset_ratio", ["1.0", "0.9:0.1", "0.025:"*39+"0.025"]),
        # ("target_tp", [i for i in range(5, 51, 10)]),
        # ("pkt_size", [1500, 9000]),
        # ("lcores", ['0-7']),
        # ("hs_flags", ['--hs_flag_allowempty', '--hs_flag_allowempty --hs_flag_singlematch --hs_flag_dotall --hs_flag_prefilter']),
        # ("nb_rgx_desc", [256]),
        # ("port_mp_size", [32768]),
        # ("port_rx_descriptors", [32768]),
        # ("port_tx_descriptors", [2048]),
        # ("jumbo_frames", ["1"]),
        # ("rgx_enabled", ["1"]),
        # ("hs_enabled", ["0"]),
        # ("port_forward_mode", ['1']), # 0: no forwarding, 1: forward to the same rx port, 2: forward to host
        # ("pktgen_latency_enabled", ["1"]),
        # ("rules_use_content_kw", ["1"]), # extract patterns from the content keyword
        # ("rules_use_pcre_kw", ["1"]),
        # ("pattern_db", ["working_set.rules"])
    
]

default_vals = {
    "hs_flags" : [t[1] for t in g_test_parameters if t[0] == "hs_flags"][0][0],
    "nb_rgx_desc" : [t[1] for t in g_test_parameters if t[0] == "nb_rgx_desc"][0][0],
}
if None in default_vals.values():
    print("None found in default_vals!", file=sys.stderr)
    exit(-1)
    
g_param_filters = [
    lambda p: not(p["rgx_enabled"] == "1" and p["hs_enabled"] == "1"),
    lambda p: not(p["rgx_enabled"] == "0" and p["hs_enabled"] == "0"),
    lambda p: not(p["rgx_enabled"] == "1" and p["hs_flags"] != default_vals['hs_flags']),
    lambda p: not(p["rules_use_content_kw"] == "0" and p["rules_use_pcre_kw"] == "0"),
]
