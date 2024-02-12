# Should not be used of the source method is used in expelib
# shopt -s expand_aliases
# source ~/.bashrc

cd $EXPATH
sudo pkill -9 pktgen
sudo pktgen --proc-type primary -v 8 -n {{n_queues}} -a {{tx_pci}} -l {{tx_dpdk_lcores}} --  -m [{{tx_cpu_cores}}].0 -f {{gen_lua}} {% if pktgen_latency_enabled | int == 1 %} -P {% endif %} {% if jumbo_frames | int == 1 %} -j {% endif %}
echo EVENT stopped-tx
