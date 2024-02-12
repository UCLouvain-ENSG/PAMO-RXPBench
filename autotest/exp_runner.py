import expelib as exp
import threading as thr
from time import time
import os
from copy import deepcopy
import argparse
from test_global_properties import *
n_reps = None #Should fail if n_reps is not specified
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
    
    exp.remote_tmux_launch_script(
        rx, experiment, "rx.sh", cfg, verbose=False, ssh_cfg=rx_ssh_cfg, blocking=False, method="source"
    )
    exp.wait_for_remote_event(tx, "stopped-tx", timeout=60)
    exp.remote_tmux_send(rx, "sudo pkill regex-test && while pgrep -x regex-test > /dev/null; do sleep 1; done")
    output = exp.remote_tmux_send(rx, "cd $EXPATH/builddir && cat rgx_output")
    #Sometimes, the prompt does not reappear after killing, we need to press enter, so we type a useless commad
    log_cmd(True, output)
    aggregator.update(exp.host_parse_single_result(output))
    aggregator["error"] = exp.output_scan_error(output)
    print("RX done.")

def tx_run(aggregator, cfg):
    cfg['gen_lua'] = exp.remote_upload_rendered_script(tx, experiment, "gen_pkts.lua", cfg)

    print("Waiting for starting-rx...")
    if not exp.wait_for_remote_event(rx, "starting-rx", timeout=60):
        aggregator["error"] = "Timeout reached for starting rx"
        return
    print("Got event !")
<<<<<<< HEAD
    output = exp.remote_tmux_launch_script(tx, experiment, "launch_pktgen.sh", cfg, verbose=False, method="source")
=======
    output = exp.remote_tmux_launch_script(tx, experiment, "launch_pktgen.sh", cfg, verbose=False, method="bash")
>>>>>>> c13a4b0 (explib: fix tests, add bash running method, render aliases from .bashrc in the scripts)
    log_cmd(False, output)

    aggregator.update(exp.host_parse_single_result(output))
    aggregator["error"] = exp.output_scan_error(output)

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
    fgenrx.upload_scripts([
        "../meson.build", "../*.c", "../*.h",
        "../data/working_set.rules", "../data/prefixes_4b_64k.rules", "../data/prefixes_8b_1M.rules",
        "../data/*.py"
    ])

    os.remove(rx_out_file)
    os.remove(tx_out_file)
    log_msg(True, f"Start of {rx} log", "w")
    log_msg(False, f"Start of {tx} log", "w")
    
    exp.check_error(exp.remote_tmux_launch_script(
        rx, experiment, "build_rgxtest.sh", init_config, verbose=False, ssh_cfg=rx_ssh_cfg, method="sh"
    ))
    return fgenrx, fgentx
def precompile_rxpc(exparams: exp.ParameterHandler, config, ssh_cfg):
    print(f"start of relevant parameters")
    for _ in range(5):
        print(f"{'-' * 80}")
    temp_params = exp.ParameterHandler([
        ("n_rules", exparams.get_param_vals("n_rules")),
        ("pattern_db", exparams.get_param_vals("pattern_db")),
        ("rules_use_content_kw", exparams.get_param_vals("rules_use_content_kw")),
        ("rules_use_pcre_kw", exparams.get_param_vals("rules_use_pcre_kw")),
        ("rules_patlen_greaterthan", exparams.get_param_vals("rules_patlen_greaterthan")),
        ("rgx_enabled", ["1"]),
        ("hs_enabled", ["0"]),
        ("fixed_seed", [config["fixed_seed"]])
    ], 1)
    temp_params.start()
    uploader = exp.BatchedUploader(experiment)

    cfgs = []
    while temp_params.peek_params() is not None:
        print(f"n_rules={temp_params.peek_params()['n_rules']}")
        cfgs.append(temp_params.pop_params())
    precompile_scripts = [
        uploader.add_rendered_script(
            "prep_rules.sh", cfg
        )
        for cfg in cfgs
    ]
    uploader.upload(rx, ssh_cfg=ssh_cfg)
    precompile_commands = [f"sh {script}" for script in precompile_scripts]
    cmd = " & ".join(precompile_commands) + " && wait"
    out = exp.remote_tmux_send(rx, cmd)
    log_cmd(True, out)


def teardown():
    exp.remote_tmux_stop(tx)
    exp.remote_tmux_stop(rx)
def validate_results(results) -> bool:
    """
    Results: dict{str:[str .. str]}
    """
    return "rgx_bs8_enq_brst_cnt" in results.keys() or "hs_avg_scan_time_cycles" in results.keys()

def main(test_params, param_filters, save=None, precompile=False):

    data = exp.DataManager(expected_colums=[])
    if save is not None:
        exparams_loaded = exp.ParameterHandler.load_state(save)
    exparams = exp.ParameterHandler(test_params, n_reps)
    for pf in param_filters:
        exparams.add_param_filter(pf)
    loaded_from_save = False
    if save and exparams_loaded and hash(exparams_loaded) == hash(exparams):
        print(f"Loaded experiment from files !")
        exparams = exparams_loaded
        data.load_from_csv(result_file)
        loaded_from_save = True
    else:
        exparams.start()
        



    fgenrx, fgentx = setup()
    precompile_rxpc(exp.ParameterHandler(exp_params, 1), init_config, rx_ssh_cfg)

    params_evts = exp.ParameterEventManager(trigger_on_blank=not loaded_from_save)
    params_evts.register_parameter_event(
        ["n_rules", "rgx_enabled", "rule_subset_ratio"], 
        lambda p, curr_cfg: log_cmd( 
            True,
            exp.remote_tmux_launch_script(
                rx, experiment, "prep_rules.sh", curr_cfg, verbose=False, ssh_cfg=rx_ssh_cfg, method="source"
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
            tx_thread = thr.Thread(target=tx_run, args=(rx_result, curr_cfg),)
            rx_thread = thr.Thread(target=rx_run, args=(tx_result, curr_cfg))
            tx_thread.start()
            rx_thread.start()

            print(f"Waiting for rx...")
            rx_thread.join()
            print(f"Waiting for tx...")
            tx_thread.join()
            print(f"Done")
            if rx_result["error"] is not None:
                print(f"Error at RX: {rx_result['error']}")
                continue
            if tx_result["error"] is not None:
                print(f"Error at RX: {tx_result['error']}")
                continue
            result.update(rx_result)
            result.update(tx_result)
            del result["error"]
            print(f"{'-' * 80}\n{result=}\n{'-' * 80}")
            if not validate_results(result) or not data.add_entry(result, current_parameters=params, force=True):
                print(f"got invalid results - invalid result {not validate_results(result)} cannot add data entry {not data.add_entry(result, current_parameters=params)} !")
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
    exp.script_get_depending_variables("prep_rules.sh")
    parser = argparse.ArgumentParser(description="Launch an experiment")
    parser.add_argument("exp_params", type=str, help="File specifiying exeperiment parameters")
    parser.add_argument("--from_save", type=str, help="load experiment state from this file")
    parser.add_argument("--cache_rxp", type=str, help="First argument of action")
    args = parser.parse_args()
    param_file = args.exp_params.split(".")[0]
    #Please don't judge me
    exp_params = None
    param_filters = None 
    exec(
f"""
import {param_file} as params
exp_params = params.g_test_parameters
param_filters = params.g_param_filters
n_reps = params.g_nreps
"""
    )
    if exp_params is not None and param_filters is not None:
        print("Succesfully loaded parameters !")
    else:
        raise RuntimeError(f"Could not load parameters from file {args.exp_params}")
    main(exp_params, param_filters, save=args.from_save if args.from_save else None, precompile=True)
    
    