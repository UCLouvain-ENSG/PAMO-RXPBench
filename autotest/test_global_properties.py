import expelib as exp
import os
import sys
__exp = "EXPERIMENT"
__bf2_ssh = "BF2_SSH_KEY_PATH"
__rx_user = "RX_USER"
__rx_host = "RX_HOST"
__host_ssh = "HOST_SSH_KEY_PATH"
needed_envs = [__exp, __bf2_ssh, __rx_user, __rx_host, __host_ssh]
for i, env in enumerate(needed_envs):
    if os.getenv(env) is None:
        print(f"Environment variables:\n {needed_envs[i:]}\n are necessary !", file=sys.stderr)
        exit(-1)

experiment      = os.getenv(__exp)
rx              = os.getenv(__rx_host)
tx              = "elrond" # pippin
rx_out_file     = "rx_output.log"
tx_out_file     = "tx_output.log"
result_file     = f"result_{experiment}.csv"
save_file       = f"save_{experiment}.pckl"
# if running tests on dormeur make sure to:
# enable RGX engine - Prerequisite - https://docs.nvidia.com/doca/archive/doca-v2.2.1/regex-programming-guide/index.html
# forward packets from nic_dormeur to dormeur
# change rx variable to dormeur (few lines up)
# automatic: change PCIe address to 0000:51:00.0 (few lines down)
# automatic: change rx_ssh_cfg to the following
if rx == "dormeur":
    rx_ssh_cfg  = exp.SSHConfig(
        identity=os.getenv(__host_ssh), # os.path.expanduser("~/.ssh/id_rsa"),
        user=os.getenv(__rx_user),
        host_address="dormeur"
    )
elif rx == "nic_dormeur":
    rx_ssh_cfg  = exp.SSHConfig(
        identity=os.getenv(__bf2_ssh),
        user="ubuntu",
        host_address="10.0.0.15"
        #host_address="192.168.100.2"
    )

init_config = {
    # add a number of repetitions to the experiment here
    "exp_repetitions":              2,
    # "exp_repetitions":              3,
    "n_queues":                     "8",
    "tx_burst_size":                "1",
    "host_tx":                      "10.100.0.1",
    "mac_tx":                       "04:3f:72:dc:4a:65", # 04:3f:72:dc:4a:64 is the real one
    "tx_pci":                       "0000:98:00.0" if tx == "elrond" else "0000:01:00.1", # else is pippin
    "tx_dpdk_lcores":               "1,3,5,7,9,11,13,15,17,19,21,23" if tx == "elrond" else "0-7", # else is pippin
    "tx_cpu_cores":                 "3/5/7/9:11/13/15/17/19/21/23" if tx == "elrond" else "2/3/4:5/6/7", # else is pippin
    "host_rx":                      "10.100.0.2",
    "mac_rx":                       "04:3f:72:dc:4a:64",
    "rx_pci":                       "0000:51:00.0" if rx == "dormeur" else "0000:03:00.0",
    "pktgen_lag":                   "1.5",
    "latency_rate":                 "1000",
    "fixed_seed":                   "1",
    "rx_warmup":                    "2",
    "rx_timeout":                   "7",
    "rx_cooldown":                  "1",
    "platform":                     "host" if rx == "dormeur" else "nic",
    "dpdk":                         "user" #mellanox or user
}
