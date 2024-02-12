#!/bin/bash

cd $EXPATH/builddir
((sudo ./regex-test -l {{lcores}} -a {{rx_pci}},class=eth:regex,representor=[0,65535] \
--log-level=notice -- --forwarding_mode {{port_forward_mode}} \
{% if packets_process_atleast is defined %}--pkts_process_atleast {{packets_process_atleast}} \{% endif %} \
--rgx_descriptors {{nb_rgx_desc}} --rgx_rules_path $EXPATH/current.rof2.binary  \
--rgx_enabled {{rgx_enabled}} \
--rgx_rule_subset_ratio {{rule_subset_ratio}} \
--port_mp_size {{port_mp_size}} \
--port_rx_descriptors {{port_rx_descriptors}} \
--port_tx_descriptors {{port_tx_descriptors}} {% if pkt_size | int > 1500 %} \
--port_mtu {{pkt_size + 100}} {% endif %} \
--hs_enabled {{hs_enabled}} {{ hs_flags }} \
--hs_rules_path $EXPATH/current.hyperscan 2>&1) | tee rgx_output) &

# monitor the output file until ready to receive pkts
#TODO Implement some sort of warm up in the regex-test i.e: reject the first X packets from the stats
cat /tmp/rgx_cnt # stores the number of content and pcre rules from the prep_rules.sh phase
