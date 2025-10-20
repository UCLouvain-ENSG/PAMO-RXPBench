# PAMO-RXPBench

The repository containing PAMO source code on how RXP engine on Bluefield-2 was tested in the paper.
PAMO-RXPBench uses DPDK rte_regex API, supported by both Bluefield-3 and Marvel Octeon TX2 NICs.

# Dependencies

These dependencies are primarily listed for Bluefield-2 and Ubuntu Server 22.04.

- DPDK 23.07
- DOCA 2.0 (DOCA 2.2.1 is the latest with RXP support) (PAMO-RXPBench doesn't use DOCA but it may be needed for BF2 to work properly)
- meson & ninja

# Enable regex engine

Taken from https://docs.nvidia.com/doca/archive/doca-v2.2.0/regex-programming-guide/index.html

```
host> sudo /etc/init.d/openibd stop
host> sudo echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
```

On the BF

```
echo 1 > /sys/bus/pci/devices/0000\:03\:00.0/regex/pf/regex_en
```

Then re-enable OpenIBD on the host:

```
sudo /etc/init.d/openibd start
```

# Running

```
ninja -C build/ && sudo ./build/regex-test -l 0,1,2,3,4 -a 0000:03:00.0,class=eth:regex,representor=[0,65535] --log-level=info
```

Run `./regex-rxpc.sh` to compile the rules in `regex.rules` and place them to 
the expected location of `regex-test` app. 

# Autotest

Autotest is used to systematically test RXP engine under different variables defined in `param_*` files.
It is expected to operate the framework from `surrexcata/autotest/` folder.
The file `exp_runner.py` is the starting point for experiments. The second argument is the file with parameters.
Variables in `param_*` files are defined as an arrays. Cartesian product of arrays are all different combinations that are executed.
Parameter files also support filters to avoid redudant or impossible variable combinations.

Generally, all tests are prefixed by some environment variables. This is the expectected command to run the tests.

```
EXPERIMENT="<EXPERIMENT_NAME>" BF2_SSH_KEY_PATH="<SSH_PATH_TO_BF2>" RX_USER="<SSH_USERNAME>" RX_HOST="<SERVER_TO_RUN_EXP_ON>" HOST_SSH_KEY_PATH="<SSH_PATH_TO_HOST>" python3 exp_runner.py <param_*.py>
```

`RX_HOST` variable can be set to either host machine or to DPU itself.


The results are then stored to `autotest/result_<EXPERIMENT_NAME>.csv`, according to `EXPERIMENT_NAME` variable defined in the previous command.

## Post-processing results

`python3 process.py` processes results file to reduce the number of results and to prepare the file for plotting.

There are numerous of plotting scripts shown below.

## RXP performance heatmap

```
<ENV_PREFIX> python3 exp_runner.py params_heatmap_rulesetsz_pktsz.py
python3 process.py --input_file result_heatmap_host.csv # <- example experiment name
python3 plot-heatmap2.py --x_axis param_n_rules --y_axis param_pkt_size --zero_drop_thres 99.7 --pandas_query "param_n_rules >= 2048"
```

## RXP subsets

```
<ENV_PREFIX> python3 exp_runner.py params_rule_subsets.py
python3 process.py --input_file result_rule_subsets.csv
python3 plot-bar4.py --pandas_query "param_n_rules == 28255 and param_pkt_size == 1500" --zero_drop_thres 99.8
```

### RXP on the host vs on the DPU

```
<ENV_PREFIX> python3 exp_runner.py params_hs_vs_rxp_cores.py # one cmd is defined with the host RX_HOST name
<ENV_PREFIX> python3 exp_runner.py params_hs_vs_rxp_cores.py # the other cmd is defined with the DPU RX_HOST name

python3 process.py --input_file result_hs_vs_rxp_v4_host.csv && mv results_selected_aggr.csv host.csv
python3 process.py --input_file result_hs_vs_rxp_v4_nic.csv && mv results_selected_aggr.csv nic.csv

python3 plot-groups-new3.py --pandas_query 'param_pkt_size != 9000' --input_file nic.csv ARM --input_file host.csv x86
```