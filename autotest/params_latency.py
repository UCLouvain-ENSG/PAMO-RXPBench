#The goal of this experiment is to find out at which point we start having drops in efficiency related to the number of prefixes in the rgx
g_nreps = 2

g_test_parameters = [
    ("n_rules", [2048, 28255]), #26624]),#, 26624]),
    #("n_rules", [i for i in range(2048, 28256, 4096)]),
    # !!! rule_subset_ratio RXPC specific!
    ("rule_subset_ratio", ["1.0"]),

    ("target_tp", [0.1, 0.5, 1]),
    ("pkt_size", [1500, 3000, 6000, 9000]),
    ("lcores", ['0-7']),
    ("hs_flags", ['--hs_flag_allowempty']), # '--hs_flag_allowempty --hs_flag_singlematch --hs_flag_dotall --hs_flag_prefilter']),
    ("nb_rgx_desc", [2048]),
    ("port_mp_size", [32767]),
    ("port_rx_descriptors", [16384]),
    ("port_tx_descriptors", [16384]),
    ("jumbo_frames", ["1"]),
    ("rgx_enabled", ["0","1"]),
    ("hs_enabled", ["0","1"]),
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
