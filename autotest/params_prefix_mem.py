#The goal of this experiment is to find out at which point we start having drops in efficiency related to the number of prefixes in the rgx
g_test_parameters = [

    ("n_rules", [1024] + [i for i in range(4096, 24000, 4096)]),
    ("target_tp", [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]),
    ("pkt_size", [1500]),
    ("lcores", ['0-7']),
    ("hs_flags", ['--hs_flag_allowempty']),
    ("nb_rgx_desc", [256]),
    ("port_mp_size", [32768]),
    ("port_rx_descriptors", [32768]),
    ("port_tx_descriptors", [2048]),
    ("jumbo_frames", ["1"]),
    ("rgx_enabled", ["1"]),
    ("hs_enabled", ["0"]),
    ("port_forward_mode", ['1']), # 0: no forwarding, 1: forward to the same rx port, 2: forward to host
    ("pktgen_latency_enabled", ["1"]),
    ("rules_use_content_kw", ["1"]), # extract patterns from the content keyword
    ("rules_use_pcre_kw", ["0"]),
    ("rules_patlen_greaterthan", ["5"]),
    ("pattern_db", ["prefixes_4b_64k.rules"])
]

    
g_param_filters = [
    lambda p: not(p["rgx_enabled"] == "1" and p["hs_enabled"] == "1"),
    lambda p: not(p["rgx_enabled"] == "0" and p["hs_enabled"] == "0"),
    lambda p: not(p["rules_use_content_kw"] == "0" and p["rules_use_pcre_kw"] == "0"),
]
g_nreps = 2 