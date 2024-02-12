import expelib as exp
import threading as thr
from random import randint
from time import sleep
from time import time
import subprocess as sp
import os
from typing import Set, Dict, List
from random import shuffle
from copy import deepcopy

experiment      = "rgx-benchmark" 
rx              = "smart-dormeur"
tx              = "blanche"
rx_out_file     = "rx_output.log"
tx_out_file     = "tx_output.log"
result_file     = "results.csv"
save_file       = "experiment.pckl"

rx_ssh_cfg  = exp.SSHConfig(
    identity=os.path.expanduser("~/.ssh/id_rsa_inlab_colin"),
    user="ubuntu",
    host_address="192.168.100.2"
)

def log_cmd(to_rx: bool, to_log: str) -> None: 
    out_file = rx_out_file if to_rx else tx_out_file
    with open(out_file, "a") as f:
        f.write(to_log)

def log_msg(to_rx: bool, to_log: str, mode="a") -> None:
    out_file = rx_out_file if to_rx else tx_out_file
    with open(out_file, mode) as f:
        f.write(f"\n{'-' * 50} \n {to_log} \n{'-' * 50}\n")

def sec_to_hm(sec: int):
    h = sec // 3600
    m = (sec - h * 3600) // 60
    return f"{int(h)}h{int(m)}"



def rx_run(aggregator, cfg):
    
    output = exp.remote_tmux_launch_script(
        rx, experiment, "rx.sh", cfg, verbose=False, ssh_cfg=rx_ssh_cfg
    )
    log_cmd(True, output)

    aggregator.update(exp.host_parse_results(output))
    print("RX done.")

def tx_run(aggregator, cfg):
    cfg['gen_lua'] = exp.remote_upload_rendered_script(tx, experiment, "gen_pkts.lua", cfg)

    print("Waiting for starting-rx...")
    exp.wait_for_remote_event(rx, "starting-rx", timeout=120)
    print("Got event !")
    output = exp.remote_tmux_launch_script(tx, experiment, "launch_pktgen.sh", cfg, verbose=False)
    log_cmd(False, output)

    aggregator.update(exp.host_parse_results(output))
    print("TX Done.")

def setup():
    exp.clean_renders()
    #Establish connections to experiments runners
    exp.remote_tmux_stop(tx)
    exp.remote_tmux_stop(rx)
    #Setup sshcfg

    exp.remote_tmux_start(tx, experiment)
    exp.remote_tmux_start(rx, experiment, ssh_cfg=rx_ssh_cfg)
    fgenrx = exp.FileGenerator(experiment, rx, clean=True, ssh_cfg=rx_ssh_cfg)
    fgentx = exp.FileGenerator(experiment, tx, clean=True)
    fgenrx.upload_script("../meson.build")
    fgenrx.upload_script("../regex-test.c")
    fgenrx.upload_script("../regex-test.h")
    fgenrx.upload_script("../rgx_stats.c")
    fgenrx.upload_script("../rgx_stats.h")
    fgenrx.upload_script("../helpers.c")
    fgenrx.upload_script("../helpers.h")
    fgenrx.upload_script("../util-hs.c")
    fgenrx.upload_script("../util-hs.h")

    fgenrx.upload_script("../data/emerging-all-fixed-filtered.rules")
    fgenrx.upload_script("../data/rule_sampler.py")
    fgenrx.upload_script("../data/rof2_extractor.py")
    os.remove(rx_out_file)
    os.remove(tx_out_file)
    log_msg(True, f"Start of {rx} log", "w")
    log_msg(False, f"Start of {tx} log", "w")
    return fgenrx, fgentx

def teardown():
    exp.remote_tmux_stop(tx)
    exp.remote_tmux_stop(rx)
def validate_results(results) -> bool:
    """
    Results: dict{str:[str .. str]}
    """
    return "bs8_enq_brst_cnt" in results.keys() 

init_config = {
    "n_queues":                     "8",
    "pkt_size":                     "256",
    "host_tx":                      "10.100.0.1",
    "mac_tx":                       "04:3f:72:dc:4a:65",
    "tx_pci":                       "0000:01:00.0",
    "host_rx":                      "10.100.0.2",
    "mac_rx":                       "08:c0:eb:bf:ef:92",
    "rx_pci":                       "0000:03:00.0",
    "pktgen_lag":                   "1.5",
    "enable_latency":               "0",
    "latency_rate":                 "0",
    "n_latency_samples":            "0",
    "latency_samples_per_second":   "0",
    "fixed_seed":                   "1",
    "rx_timeout":                   "10",
    "enable_latency":               "1",
    "latency_rate":                 "10000",
    "jumbo_frames":                 "0"
    
}

def main():

    data = exp.DataManager(expected_colums=[])
    exparams_loaded = exp.ParameterHandler.load_state(save_file)
    exparams = exp.ParameterHandler([
        ("n_rules", [64]),
        ("target_tp", [1]),
        ("pkt_size", [256]),
        ("lcores", ['0-1']),
        ("nb_rgx_desc", [24])
    ], 10)
    exparams.start()



    fgenrx, fgentx = setup()


    
    params_evts = exp.ParameterEventManager(trigger_on_blank=True)
        
    params_evts.register_parameter_event(
        ["n_rules"], 
        lambda p, curr_cfg: log_cmd( 
            True,
            exp.remote_tmux_launch_script(
                rx, experiment, "prep_rules.sh", curr_cfg, verbose=False, ssh_cfg=rx_ssh_cfg
            )
        )
    )
    

    run_cntr = 0
    n_exp = 0
    tot_dt = 0
    t0 = time()
    dt = 0
    print(f"Preparing to run {exparams.get_total_configs()} configs...")
    while exparams.peek_params() is not None:
        params = exparams.pop_params()
        print(f"{params=}")
        curr_cfg = deepcopy(init_config)
        curr_cfg.update(params)
        print(curr_cfg)
        print(params)
        params_evts.process_parameters(params, curr_cfg)
        valid = False
        while not valid: 

            print(f"Parameter set #: {exparams.get_configs_popped()} / {exparams.get_total_configs()}")
            t1 = time()
            dt = t1 - t0
            t0 = t1
            tot_dt += dt
            avg_dt = tot_dt / exparams.get_configs_popped()
            print(f"time left: {sec_to_hm((exparams.get_configs_left()) * avg_dt)}")


            log_msg(True, f"run {run_cntr}")
            log_msg(False, f"run {run_cntr}")
            result = {}
            rx_result = {}
            tx_result = {}
            tx_thread = thr.Thread(target=tx_run, args=(rx_result, curr_cfg))
            rx_thread = thr.Thread(target=rx_run, args=(tx_result, curr_cfg))
            tx_thread.start()
            rx_thread.start()

            print(f"Waiting for rx...")
            rx_thread.join()
            print(f"Waiting for tx...")
            tx_thread.join()
            print(f"Done")
            result.update(rx_result)
            result.update(tx_result)
            if not validate_results(result) or not data.add_entry(result, current_parameters=params):
                print(f"got invalid results !")
                log_msg(True, f"run {run_cntr} failed {result=}")
                log_msg(False, f"run {run_cntr} failed {result=}")
                continue
            data.show_last()
            valid = True
            run_cntr += 1
            data.export_csv(result_file)
            exparams.save_state(save_file)
            n_exp += 1
                        
    teardown()
    
if __name__ == "__main__":
    main()