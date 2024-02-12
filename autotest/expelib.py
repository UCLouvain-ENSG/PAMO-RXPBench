import subprocess as sp
import os
from pathlib import Path
from time import sleep
import jinja2 as jj
from jinja2 import meta

from datetime import datetime
from typing import Dict, List, Tuple, Any, Callable, Set
import re
from time import time
import zipfile
from itertools import product
import pickle
import csv
from dataclasses import dataclass
import shlex
from glob import glob
import logging
from logging.handlers import RotatingFileHandler
from math import pow
from random import randint
# Setup a specific logger for your library
logger = logging.getLogger('expelib')
logger.setLevel(logging.INFO)

# Setup log format
formatter = logging.Formatter('[%(asctime)s]: %(message)s', datefmt='%H:%M:%S')

# Setup StreamHandler to output to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Optionally, setup FileHandler to output logs to a file
file_handler = RotatingFileHandler('expelib.log', maxBytes=1048576, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
#Constants
EXPELIB_MAIN_SESSION="exepelib_main"
EXPELIB_DIR="expelib"
SCRIPTS_DIR="scripts"
REMOTE_RENDERS_DIR="renders"
HOST_RENDERS_DIR="renders"
TMUX_EXPE_LIB_CHANNEL="expelib"
TMUX_SCROLLBACK_BUFFER_SIZE=10000
EVT_CONJUNCTION = "conjunction"
EVT_DISJUNCTION = "disjunction"
LOCALHOST="local"
TMUX_DEFAULT_SIZE="240x48"
#jinja stuff
jj_env = jj.Environment(loader=jj.FileSystemLoader(f"{SCRIPTS_DIR}/"))
#Regexes
prompt_regex = re.compile("[-\w\d]+@[-\w\d]+:[~\/\w\d-]+[\$#]")
#TODO ADD SUPPORT FOR COMMAS AS DECIMAL SEPARATORS
result_regex = re.compile("RESULT-(?P<field>[\.\w\d-]+)\s+(?P<value>[\.\d]+)(?P<unit>[a-zA-Z]*)")
result_empty_regex = re.compile("RESULT-(?P<field>[\.\w\d-]+)\s+")
experiment_failed_rgx = re.compile("EXPRUN-FAILED:(?P<reason>[\.\w\d\-\s,]+)")
new_data_entry_kw = "NEW_DATA_ENTRY"
event_regex = re.compile("EVENT (?P<name>[\w\d-]+)")
#DataTypes
DataEntry = Dict[str, List[Any]]
ParameterCallback = Callable[[Dict[str, str], Dict[str, str]], Any]
EventTrigger = Tuple[str, Set] # (mode (conjunction/disjunction), Set of fields)
ParamSet = Dict[str, Any]
ParamSetFilter = Callable[[ParamSet], bool]
#timestamping stuff
ts_period_default = 1000000 #how many second before we cycle through the same timestamps (rhoughly 11 days)



@dataclass
class SSHConfig:
    identity:str 
    user:str
    host_address:str

def timestamp(rand_ext_size=4, ts_period=ts_period_default) -> int:
    """
    Returns the current timestamp as an integer value, rounded to the nearest integer using the 
    `round()` function.

    Parameters:
        rand_ext_size (int): The number of digits to generate for the random extension.
        ts_period (int): The time period to use for calculating the timestamp modulo.

    Returns:
        int: The generated timestamp.

    """
    now = int(round(datetime.now().timestamp()))
    now_period = now % ts_period
    return now_period * (10**rand_ext_size) + randint(0, (10**rand_ext_size) - 1)



def remote_tmux_session_name(remote: str) -> str:
    """
    Generate a unique session name for a remote tmux session.

    Args:
        remote (str): The name of the remote.

    Returns:
        str: The generated session name.
    """
    return f"expelib-tmux-{remote}"

def remote_tmux_check(remote: str) -> bool:
    """
    Check if a remote tmux session exists.

    Args:
        remote (str): The name of the remote machine.

    Returns:
        bool: True if the remote tmux session exists, False otherwise.
    """
    return sp.run(["tmux", "has-session", "-t", remote_tmux_session_name(remote)]).returncode == 0

def remote_tmux_get_output(remote: str) -> str:
    """
    Retrieves the output from a remote tmux session.

    Args:
        remote (str): The name of the remote session.

    Returns:
        str: The output captured from the remote tmux session.
    """
    sp.run(["tmux", "capture-pane", "-b", remote, "-S", f"-{TMUX_SCROLLBACK_BUFFER_SIZE}", "-t", remote_tmux_session_name(remote)])
    return sp.run(["tmux", "show-buffer", "-b", remote], capture_output=True, text=True).stdout

def remote_tmux_wait_for_prompt(remote: str, interval=1, print_waiting=False, waits_before_verbose=15):
    """
    Waits for a command prompt on the remote machine.

    Args:
        remote (str): The remote machine to wait for the prompt on.
        interval (float, optional): The interval between each check for the prompt. Defaults to 1.
        print_waiting (bool, optional): Whether to print waiting messages. Defaults to False.
        waits_before_verbose (int, optional): The number of waits before printing a waiting message. Defaults to 15.
    """
    sleep(0.1)
    n_waits = 0
    while True:
        output = remote_tmux_get_output(remote)
        lines = list(filter(lambda x: len(x) > 0, output.split("\n")))
        last_line = lines[-1].strip()
        # Check whether we have a command prompt waiting for us
        match = prompt_regex.search(last_line)
        if match and last_line.endswith(match.group()):
            break
        else:
            sleep(interval)
            n_waits += 1
        if print_waiting and n_waits >= waits_before_verbose:
            logger.info(f"Waiting for output on {remote}...")

def wait_for_remote_event(remote: str, event: str, refresh=0.05, timeout=3600):
    """
    Waits for a specific event to occur on a remote machine.

    Args:
        remote (str): The name of the remote machine.
        event (str): The name of the event to wait for.
        refresh (float, optional): The refresh rate in seconds to check for the event. Defaults to 0.05.
        timeout (int, optional): The maximum time in seconds to wait for the event. Defaults to 3600.

    Returns:
        bool: True if the event is detected and matched, False otherwise.
    """
    tot_time = 0
    t0 = time()
    while tot_time < timeout:
        output = remote_tmux_get_output(remote)
        match = event_regex.search(output)
        t1 = time()
        delta = t1 - t0
        tot_time += delta
        t0 = t1
        if match:
            if match.group("name") == event:
                return True
            else:
                logger.info(f"Event detected but not matched: {match.group('name')=}")

        else:
            sleep(refresh)
    logger.info(
        f"Could not find event {event} !\n" +\
        f"output = {remote_tmux_get_output(remote)}"
    )
    return False

def remote_tmux_send(
        remote: str, cmd: str, return_stdout=True, blocking=True,
        verbose=True, inter_cmd_sleep=0.2
    ):
    """Sends a command to the tmux session and retrieves its output.

    Args:
        remote (str): The name of the remote host.
        cmd (str): The command to send.
        return_stdout (bool, optional): Whether to return the command's output. Defaults to True.
        blocking (bool, optional): Whether to block until the command execution finishes. Defaults to True.
        verbose (bool, optional): Whether to print verbose output. Defaults to True.
        inter_cmd_sleep (float, optional): Time interval between command sends. Defaults to 0.2.
    """
    sess_name  = remote_tmux_session_name(remote)
    if not remote_tmux_check(remote):
        raise RuntimeError(f"No tmux session on {remote}.")
    
    sp.run(["tmux", "send", "-t", sess_name, "clear", "C-m"])
    sp.run(["tmux", "clear-history", "-t", sess_name])
    sleep(inter_cmd_sleep)
    sp.run(["tmux", "send", "-t", sess_name, cmd, "C-m"])
    sleep(inter_cmd_sleep)

    if blocking:
        remote_tmux_wait_for_prompt(remote, interval=1, print_waiting=True, waits_before_verbose=30)
    if not return_stdout:
        return
    
    output = remote_tmux_get_output(remote)
    sp.run(["tmux", "send", "-t", sess_name, "clear", "C-m"])
    sp.run(["tmux", "clear-history", "-t", sess_name])
    sleep(inter_cmd_sleep)
    lines = list(filter(lambda x: len(x) > 0, output.split("\n")))
    output = "\n".join(lines[1:len(lines) - 1])

    if verbose:
        logger.info(f"> {cmd}")
        logger.info(output)

    return output

def output_scan_error(output: str):
    """
    Scans the output string for any error messages and returns the reason for the failure.
    One can send an error from the remote machine by outputing a string in the following format:
    `EXPRUN-FAILED:<reason>`
    Args:
        output (str): The output string to scan for error messages.

    Returns:
        str or None: The reason for the failure if an error message is found, None otherwise.
    """
    match = experiment_failed_rgx.search(output)
    if match:
        return match.group('reason')
    else:
        return None
    
def check_error(output: str):
    """
    Checks if there is an error in the output.

    Args:
        output (str): The output to be checked.

    Raises:
        RuntimeError: If an error is found in the output.

    Returns:
        None
    """
    err = output_scan_error(output)
    if err:
        raise RuntimeError(err)
    
def remote_tmux_start(remote: str, experiment_path: str, ssh_cfg:SSHConfig=None) -> str:
    """Starts a tmux session on the specified remote host.
        This will provide the variables EXPATH and RENDIR to the remote session.
        These point to the experiment path and the renders directory respectively.
        Users should express their paths relative to these variables for portability.
    Args:
        remote (str): The name of the remote host, corresponding to an entry in your ssh config
        experiment_path (str): Sets a bash variable called EXPATH pointing to the folder containing the experiment.
        ssh_cfg (SSHConfig): If given, uses the provided SSH configuration to connect to the remote host.
    Returns:
        str: Output from the command.
    """
    session_name = remote_tmux_session_name(remote)
    has_session = sp.run(["tmux", "has-session", "-t", session_name], ).returncode == 0
    if has_session:
        logger.info(f"remote {remote} already had a session.")
    else:
        sp.run(["tmux", "set-option", "-g", "history-limit", f"{TMUX_SCROLLBACK_BUFFER_SIZE}"])
        sp.run(["tmux", "set-option", "-g", "default-size", f"{TMUX_DEFAULT_SIZE}"])
        sp.run(
            ["tmux", "new-session", "-d", "-s", session_name]
        )
        logger.info(f"Started tmux session {session_name}.")
        if remote.startswith(LOCALHOST):
            logger.info(f"Session {session_name} started in localhost !")
        else:
            logger.info(f"Connecting {session_name} to {remote} through ssh...")
            ssh_command = \
                f"ssh {'-i '+ ssh_cfg.identity if ssh_cfg else ''} " + \
                f"{ssh_cfg.user+'@' if ssh_cfg else ''}{ssh_cfg.host_address if ssh_cfg else remote}"
            logger.info(f"Connecting to {remote} using '{ssh_command}'")
            sp.run(["tmux", "send", "-t", session_name, ssh_command, "C-m"])
            remote_tmux_wait_for_prompt(remote)
            logger.info(f"Done.")
        remote_tmux_send(remote, f"cd $HOME", verbose=False)
        remote_tmux_ensure_dir(remote, experiment_path)
        remote_tmux_send(remote, f"cd {experiment_path}", verbose=False)
        remote_tmux_send(remote, f"export EXPATH=$PWD", verbose=False)
        remote_tmux_send(remote, f"export RENDIR=$EXPATH/{REMOTE_RENDERS_DIR}", verbose=False)

    return remote_tmux_send(remote, "echo $PWD")
    

def remote_tmux_stop(remote: str):
    """Stops the tmux session on the specified remote host.
    Args:
        remote (str): The name of the remote host.
    """
    session_name = remote_tmux_session_name(remote)
    has_session = sp.run(["tmux", "has-session", "-t", session_name], ).returncode == 0
    if not has_session:
        logger.info(f"remote {remote} has no session.")
    else:
        sp.run(["tmux", "kill-session", "-t", session_name])
        logger.info(f"Stopped tmux session {session_name}.")

def render_script(
        template_name: Path, values: Dict[str, str], do_timestamp=True,
        filename_prefix=None, name_extra:str=None
    ) -> str:
    """Renders a script using Jinja2 templating.

    Args:
        template_name (Path): The name of the template file.
        values (Dict[str, str]): Dictionary containing values for template rendering.
        do_timestamp (bool, optional): Whether to append a timestamp to the file name. Defaults to True.
        filename_prefix (str, optional): If given, the prefix of the filename to write the rendered script to. 
    Returns:
        str: The path of the rendered script.
    """
    template = jj_env.get_template(template_name)
    content = template.render(values)
    name, ext = os.path.splitext(template_name)
    name_extra =  f"_{name_extra}" if name_extra else ""
    if filename_prefix:
        filename_prefix = os.path.join(
            HOST_RENDERS_DIR,
            f"{os.path.splitext(filename_prefix)[0]}{'_'+str(timestamp()) if do_timestamp else ''}{name_extra}{ext}"
        )
    else:
        filename_prefix = os.path.join(
            HOST_RENDERS_DIR,
            f"{name}{'_'+str(timestamp()) if do_timestamp else ''}{name_extra}{ext}"
        )
    with open(filename_prefix, "w") as f:
        f.write(content)
        
    return os.path.join(os.getcwd(), filename_prefix)

def remote_tmux_succeeded(remote: str) -> bool:
    """Checks if the last executed command in the tmux session succeeded.

    Args:
        remote (str): The name of the remote host.

    Returns:
        bool: True if the last command succeeded, False otherwise.
    """
    sess_name  = remote_tmux_session_name(remote)
    if not remote_tmux_check(remote):
        raise RuntimeError(f"No tmux session on {remote}.")
    sp.run(["tmux", "send", "-t", sess_name, "echo $?", "C-m"])
    sleep(0.1)
    sp.run(["tmux", "capture-pane", "-t", sess_name])
    res = sp.run(["tmux", "show-buffer"], capture_output=True, text=True)
    lines = list(filter(lambda x: len(x) > 0, res.stdout.split("\n")))
    return lines[-2] == "0"

def remote_tmux_ensure_dir(remote: str, directory: Path):
    """Ensures the existence of a directory on the host.

    Args:
        remote (str): The name of the remote host.
        directory (Path): The directory path to ensure.
    """
    remote_tmux_send(remote, "cd ~", return_stdout=False)
    remote_tmux_send(remote, f"mkdir -p {directory}", return_stdout=False)

def remote_tmux_dir_exists(remote: str, directory: Path):
    """Checks if a directory exists on the remote host.

    Args:
        remote (str): The name of the remote host.
        directory (Path): The directory path to check.

    Returns:
        bool: True if the directory exists, False otherwise.
    """
    remote_tmux_send(remote, "cd ~", return_stdout=False)
    remote_tmux_send(remote, f"test -d {directory}", return_stdout=False)
    return remote_tmux_succeeded(remote)

def remote_upload_file(
        remote: str, src: Path, dst: Path,
        max_retries:int = 3, inter_retry_time:float=10.0, ssh_cfg:SSHConfig=None
    ):
    """Uploads a file from the local machine to the remote host using SCP.

    Args:
        remote (str): The name of the remote host.
        src (Path): The path of the source file on the local machine.
        dst (Path): The destination path on the remote host.
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(f"Could not find remote src file {src}")
    src = os.path.abspath(src)
    succeeded = False
    n_retries = 0
    while not succeeded and n_retries < max_retries:
        if n_retries > 0:
            logger.warning(f"Waiting {inter_retry_time}s after upload failure...")
            sleep(inter_retry_time)
        if remote.startswith(LOCALHOST):
            dst = os.path.expanduser(dst)
            ret = sp.run(['cp', src, dst], capture_output=True).returncode
            if ret != 0:
                logger.info(f"Could not copy local file {src} to {dst}")
            else:
                succeeded = True
        else:
            scp_command = \
                f"scp {'-i' if ssh_cfg else ''} {' '+ssh_cfg.identity if ssh_cfg else ''} {src} " + \
                f"{ssh_cfg.user+'@' if ssh_cfg else ''}{ssh_cfg.host_address if ssh_cfg else remote}:{dst}"
            scp_command = f'tmux -c "{scp_command}"'
            logger.info(f"Uploading file using :'{scp_command}'")
            run_res = sp.run(shlex.split(scp_command), capture_output=True)
            if run_res.returncode != 0:
                logger.error(f"Could not upload file {src} to {remote}:{dst} -> errcode {run_res.returncode}")
                logger.error(f"File transfer output:\n{run_res.stderr}\n{run_res.stdout}")
            else:
                succeeded = True
        n_retries += 1
    if not succeeded:
            logger.error(
                f"Could not copy/upload file {src} to "+\
                f"{remote}:{dst} after {n_retries} retries"+\
                f" -> errcode {run_res.returncode}"
            )

def remote_upload_rendered_script(
        remote: str, experiment_path: Path, script_name: Path,
        config: Dict[str, str],
        do_timestamp=True, filename=None, name_extra: str=None, ssh_cfg:SSHConfig=None) -> str:
    """Uploads a rendered script to a remote host.

    Args:
        remote (str): The name of the remote host.
        experiment_path (Path): Path of the experiment on the remote host.
        script_name (Path): Name of the script/template file.
        config (Dict[str, str]): Configuration values for rendering the script.
        do_timestamp (bool, optional): Whether to append a timestamp to the file name. Defaults to True.

    Returns:
        str: The destination path of the uploaded script on the remote host.
    """
    remote_tmux_ensure_dir(remote, os.path.join(experiment_path, REMOTE_RENDERS_DIR))
    script_src = render_script(script_name, config, do_timestamp=do_timestamp, filename_prefix=filename, name_extra=name_extra)
    script_dst = os.path.join("~", experiment_path, REMOTE_RENDERS_DIR, os.path.basename(script_src))
    remote_upload_file(remote, script_src, script_dst, ssh_cfg=ssh_cfg)
    return script_dst

def remote_tmux_launch_script(
        remote: str, experiment_path: Path, script_name: Path,
        config: Dict[str, str], do_timestamp=True, verbose=False,
        filename=None, ssh_cfg=None, blocking=True, method="source"
    ) -> str:
    """Launches a script on a tmux session after uploading it.

    Args:
        remote (str): The name of the remote host.
        experiment_path (Path): Path of the experiment on the remote host.
        script_name (Path): Name of the script/template file.
        config (Dict[str, str]): Configuration values for rendering the script.
        do_timestamp (bool, optional): Whether to append a timestamp to the file name. Defaults to True.
        verbose (bool, optional): Whether to display verbose output. Defaults to False.

    Returns:
        str: Output from the command.
    """
    allowed_methods = ["source", "sh", "bash"]
    if method not in allowed_methods:
        raise RuntimeError(
            f"Unrecognized execution method: {method}."+\
            f"\nPlease use one of the following:\n{allowed_methods}"
        )
    script_dst = remote_upload_rendered_script(remote, experiment_path, script_name, config, do_timestamp=do_timestamp, filename=filename, ssh_cfg=ssh_cfg)
    #Looks stupid, but it is in prevision for adding more running methods.
    if method in ["source", "sh", "bash"]:
        command = f"{method} {script_dst}"
    return remote_tmux_send(remote, command, verbose=verbose, blocking=blocking)

def host_tmux_source_script(remote: str, experiment_path: Path, script_name: Path, config: Dict[str, str], verbose=False, filename=None) -> str:
    """Sources a script from the host using a tmux session.

    Args:
        remote (str): The name of the remote host.
        experiment_path (Path): Path of the experiment on the remote host.
        script_name (Path): Name of the script/template file.
        config (Dict[str, str]): Configuration values for rendering the script.
        verbose (bool, optional): Whether to display verbose output. Defaults to False.

    Returns:
        str: Output from the command.
    """
    script_src = render_script(script_name, config, filename_prefix=filename)
    with open(script_src, "r") as f:
        in_lines = f.readlines()
    remote_tmux_send(remote, f"cd ~/{experiment_path}", verbose=False)
    out_lines = []
    for l in in_lines:
        out_lines.append(remote_tmux_send(remote, l, verbose=False))
    return "\n".join(out_lines)

def host_parse_results(to_parse: str) -> List[DataEntry]:
    ret = []
    for entry in to_parse.split(new_data_entry_kw):
        ret.append(host_parse_single_result(entry))
    return ret
    
def host_parse_single_result(to_parse: str) -> DataEntry:
    """
    Parses the output string to retrieve specific result fields.
    if multiple results exists for the same field, they will be put in a list.

    Args:
        output (str): Output string to parse.

    Returns:
        Dict[str, List[Any]]: Parsed results in dictionary format.
    """
    results = result_regex.findall(to_parse)
    #result is a list of 2-tuples first elem is field name, second is value
    fields = list(set([el[0] for el in results]))
    ret = {
        f.lower():[el[1] for el in filter(lambda x: x[0] == f, results)]
        for f in fields
    }
    #We want to also parse malformed RESULTS-<x> with no values so that we
    #are aware of problems.
    results_empty = result_empty_regex.findall(to_parse)
    fields_empty = list(set([el for el in results_empty]))
    fields_empty = [f for f in fields_empty if f not in fields]
    ret.update({
        f.lower():["NaN"] for f in fields_empty
    })

    return ret

def has_invalid(result_line: DataEntry, invalid_token="NaN") -> bool:
    """Given a line of results, confirms whether the result line contain NaN
    Args:
        result_line (Dict[str, List[Any]]): Result line to check.

    Returns:
        bool: Whether the line contains any NaN.
    """
    has_invalid = False
    for k,v in result_line.items():
        if v[0] == invalid_token:
            logger.info(f"{k} is missing !")
            has_invalid = True

    return has_invalid

def fill_invalid(result_line: DataEntry, cols: List[str], invalid_token="NaN") -> DataEntry:
    dicopy = {k:v.copy() for k,v in result_line.items()}
    for c in cols:
        if c not in result_line:
            dicopy[c] = [invalid_token] 
    return dicopy

def results_to_matrix(results: List[DataEntry], header=True):
    """
    The method returns a matrix with dimensions `(len(self.results) + 1) x (len(columns))`. 
    The first row of the matrix is the header, if `header` is set to `True`, and the 
    remaining rows contain the data for each result in the `self.results` list. 
    Each row is a list containing the data for each column, with `NaN` values for any columns that are not present in a particular 
    result.
    """
    #collecting the feature set
    col_set=set()
    for r in results:
        col_set |= set(r.keys())
    cols = sorted(list(col_set))
    #Export the results to a matrix with following dims (len(results) + 1) x (len(columns))
    exported_results = [",".join(cols)] if header else []
    for r in results:
        line = []
        for c in cols:
            if c in r:
                line.append(r[c][0])
            else:
                line.append("NaN")
        exported_results.append(line)
    return exported_results

def results_to_csv(results: List[DataEntry], results_file: str, header: bool=True):
        """
        Reads the results aggregated in the results instance var and outputs these in a csv file
        csv_path: The path to the csv to be written
        header: Whether to print the headers as the first line
        """
        #write the results
        res = results_to_matrix(results, header=header)
        start_idx = 1 if header else 0
        stringified = [", ".join(map(str, l)) + "\n" for l in res[start_idx:]]
        with open(results_file, "w") as f:
            if header:
                f.write(f"{res[0]}\n")
            f.writelines(stringified)

def clean_renders(compress=True):
    if os.path.exists(HOST_RENDERS_DIR) and os.path.isdir(HOST_RENDERS_DIR):
    # List the contents of the directory using glob
        file_list = glob(f'{HOST_RENDERS_DIR}/*')
        if compress:
            # Create a zip file containing all the non-zip files
            with zipfile.ZipFile(f'{HOST_RENDERS_DIR}/{timestamp()}.zip', 'w') as zipf:
                for file in file_list:
                    if not file.endswith('.zip'):
                        zipf.write(file, os.path.basename(file))

        # Delete files not ending in .zip from the 'renders' directory
        for file in file_list:
            if not file.endswith('.zip'):
                os.remove(file)
    else:
        logger.info(f"The '{HOST_RENDERS_DIR}' directory doesn't exist or is not a directory.")

def update_cols(result_line: DataEntry, cols: List[str]) -> List[str]:
    new_cols = result_line.keys()
    ret = cols.copy()
    return list(set(ret).union(set(new_cols)))

def script_get_depending_variables(template_name: Path):
    with open(f"{SCRIPTS_DIR}/{template_name}", "r") as f:
        source = f.read()
    ast = jj_env.parse(source)
    return meta.find_undeclared_variables(ast)
    
class BatchedUploader:
    def __init__(self, experiment_path: str):
        self.experiment_path = experiment_path
        self.to_upload = []
        self.dsts = []
    def add_rendered_script(
            self, script_name: Path, config: Dict[str, str],
            do_timestamp=True, filename=None
        ) -> str:
        script_src = render_script(script_name, config, do_timestamp=do_timestamp, filename_prefix=filename)
        script_dst = os.path.join("~", self.experiment_path, REMOTE_RENDERS_DIR, os.path.basename(script_src))
        self.to_upload.append(script_src)
        self.dsts.append(script_dst)
        return script_dst
    def add_script(
            self, script_name: Path
        ) -> str:
        script_dst = os.path.join("~", self.experiment_path, REMOTE_RENDERS_DIR, os.path.basename(script_name))
        self.to_upload.append(script_name)
        self.dsts.append(script_dst)
        return script_dst
    
    def upload(self, remote: str, ssh_cfg:SSHConfig=None) -> List[str]:
        remote_tmux_ensure_dir(remote, os.path.join(self.experiment_path, REMOTE_RENDERS_DIR))
        if len(self.to_upload) == 0:
            raise RuntimeError("Cannot upload empty file list")
        dst_dir = os.path.join("~", self.experiment_path, REMOTE_RENDERS_DIR)
        for src in self.to_upload:
            if not os.path.isfile(src):
                raise FileNotFoundError(f"Could not find remote src file {src}")
        scp_command = \
            f"scp {'-i' if ssh_cfg else ''} {' '+ssh_cfg.identity if ssh_cfg else ''} {' '.join(self.to_upload)} " + \
            f"{ssh_cfg.user+'@' if ssh_cfg else ''}{ssh_cfg.host_address if ssh_cfg else remote}:{dst_dir}"
        scp_command = f'tmux -c "{scp_command}"'
        logger.info(f"Uploading files using :'{scp_command}'")
        ran = sp.run(shlex.split(scp_command), capture_output=True)
        if ran.returncode != 0:
            raise RuntimeError(f"Could not upload file list !\n{ran.stdout}\n{scp_command}")

        self.to_upload = []
        to_ret = self.dsts
        self.dsts = []
        return to_ret

class DataManager:
    columns: List[str] = [] 
    entries: List[DataEntry] = []
    row_idx: int = 0
    _metrics_to_compute: Dict[str, Callable[[DataEntry], float]] = {}
    _post_metrics_compute: Dict[str, Callable[[DataEntry], Any]] = {}
    def __init__(self, invalid_token="NaN", use_index=True, expected_colums=[], parameter_prefix: str="param_"):
        self.invalid_token = invalid_token
        self.use_index = use_index
        for ec in expected_colums:
            self.columns.append(ec)
        self.parameter_prefix = parameter_prefix
    
    def add_entry(self, entry: DataEntry, current_parameters:Dict[str, Any]=None, force=False, do_update_cols=True) -> bool:
        #update the columns
        if do_update_cols:
            self.columns = update_cols(entry, self.columns)
        entry = fill_invalid(entry, self.columns, invalid_token=self.invalid_token)
        if has_invalid(entry, self.invalid_token) and not force:
            return False
        if self.use_index:
            entry["index"] = [self.row_idx]
            self.row_idx += 1
        if current_parameters is not None:
            for k, v in current_parameters.items():
                entry[f"{self.parameter_prefix}{k}"] =[v]
        self._compute_metrics(entry)
        self.entries.append(entry)
        return True
    
    def validate_entry(self, entry: DataEntry) -> bool:
        entry = fill_invalid(entry, self.columns, invalid_token=self.invalid_token)
        if has_invalid(entry, self.invalid_token):
            return False
        return True
    def export_csv(self, csv_name: str, save_headers=True):
        results_to_csv(self.entries, csv_name, header=save_headers)

    def load_from_csv(self, csv_file: str):
        with open(csv_file, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                to_add = {k:[v] for k,v in row.items()}
                self.add_entry(to_add, do_update_cols=False)
    def add_computed_metric(self, name: str, compute: Callable[[DataEntry], float], post_compute:Callable[[DataEntry], Any]=None):
        self._metrics_to_compute[name] = compute
        if post_compute:
            self._post_metrics_compute[name] = post_compute 

    def _compute_metrics(self, entry: DataEntry):
        for k,v in self._metrics_to_compute.items():
            entry[k] = [v(entry)]
            if k in self._post_metrics_compute:
                self._post_metrics_compute[k](entry)

    def show_last(self, fields_per_line=2):
        if len(self.entries) == 0:
            logger.info("No data yet !")
            return
        last_line = self.entries[-1]
        to_show = ""
        for i, c in enumerate(self.columns):
            if c == "index":
                continue
            if i > 0 and i % fields_per_line == 0:
                to_show += "\n"
            to_show += f"{c} = {last_line[c][0]},\t\t"
        logger.info(to_show)

class ParameterHandler:
    
    def __init__(self, params: List[Tuple[str, List[str]]], n_repeats: int) -> None:
        self.n_repeats = n_repeats
        self.started: bool = False
        self.parameter_names: List[str] = []
        self.parameter_vals: List[List[Any]] = []
        self.params_sets: List[ParamSet] = []
        self.curr_params: ParamSet = None
        self._param_filters: List[ParamSetFilter] = []
        self._filtered_out_cnt: int = 0
        self._total_configs: int = 0
        for name, vals in params:
            self.add_param(name, vals)
        
    def add_param(self, name: str, vals: List[Any]):
        if self.started:
            raise RuntimeError("Cannot add parameters to a running experiment !")
        logger.info(f"Adding parameter {name} with vals: {vals}")
        self.parameter_names.append(name)
        self.parameter_vals.append(vals)

    def pop_params(self):
        if not self.started:
            self._build_configs()
        if len(self.params_sets) == 0:
            return None
        ret = self.params_sets.pop(0)
        self._configs_left -= 1
        self._configs_popped += 1
        self.curr_params = ret
        return ret
    
    def get_configs_popped(self):
        if not self.started:
            raise RuntimeError("Cannot get config popped if the experiment is not started !")
        return self._configs_popped
    
    def get_configs_left(self):
        if not self.started:
            raise RuntimeError("Cannot get configs left if the experiment is not started !")
        return self._configs_left

    def peek_params(self) -> ParamSet:
        if not self.started:
            self._build_configs()
        if len(self.params_sets) == 0:
            return None
        return self.params_sets[0]
    
    def start(self):
        if self.started:
            raise RuntimeError("Parameters handling can only be started once !")
        self._build_configs()

    def _build_configs(self):
        for p in product(*self.parameter_vals):
            cfg = {}
            for i, v in enumerate(p):
                cfg[self.parameter_names[i]] = v
            skip_param_set = False
            for f in self._param_filters:
                if not f(cfg):
                    skip_param_set = True
                    continue
            if skip_param_set:
                self._filtered_out_cnt += 1
                continue
            for _ in range(self.n_repeats):
                cfg_cpy = cfg.copy()
                self.params_sets.append(cfg_cpy)

        self._configs_left = len(self.params_sets)
        self._configs_popped = 0
        self._total_configs = self._configs_left
        self.started = True
        logger.info( 
            f"Found {self.get_nb_combs()} possible configs, "+\
            f"filtered out {self._filtered_out_cnt}, final={self._configs_left}"
        )
        

    def get_total_configs(self) -> int:
        return self._total_configs
    
    def get_nb_combs(self) -> int:
        ret = self.n_repeats
        for p in self.parameter_vals:
            ret *= len(p)
        return ret
    def get_param_vals(self, param: str) -> List[Any]:
        for i, param_name in enumerate(self.parameter_names):
            if param_name == param:
                return self.parameter_vals[i]
    def __hash__(self) -> int:
        h = 0
        for i, n in enumerate(self.parameter_names):
            h += hash(n) + hash(tuple(self.parameter_vals[i])) 
            h %= 15485863 # 1000000th prime number
        return h
    @classmethod
    def load_state(cls, file_path: str):
        """Load the state of the ParameterHandler from a file. 
           Return None if the file does not exist."""
        if not os.path.exists(file_path):
            logger.info(f"File '{file_path}' not found. Returning None.")
            return None
        with open(file_path, 'rb') as file:
            state = pickle.load(file)
            instance = cls([], state["n_repeats"])
            instance.started = state["started"]
            instance.parameter_names = state["parameter_names"]
            instance.parameter_vals = state["parameter_vals"]
            instance.params_sets = [state["curr_params"]] + state["params_sets"]
            instance._configs_left = state["_configs_left"]
            instance._configs_popped = state["_configs_popped"]
            instance.curr_params = None
            return instance
        
    def save_state(self, file_path: str):
        """Save the state of the ParameterHandler to a file."""
        with open(file_path, 'wb') as file:
            pickle.dump({
                "started": self.started,
                "parameter_names": self.parameter_names,
                "parameter_vals": self.parameter_vals,
                "params_sets": self.params_sets,
                "n_repeats": self.n_repeats,
                "_configs_left": self._configs_left,
                "_configs_popped": self._configs_popped,
                "curr_params": self.curr_params
            }, file)
    def add_param_filter(self, param_filter: ParamSetFilter):
        if self.started:
            raise RuntimeError("Cannot add filters to a running experiment !")
        self._param_filters.append(param_filter)
class ParameterEventManager:
    
    def __init__(self, trigger_on_blank=True):
        self.trigger_on_blank = trigger_on_blank
        self._callbacks: List[ParameterCallback] = []
        self._triggers: List[EventTrigger] = []
        self._previous_params: Dict[str, str] = None
    def register_parameter_event(self, trigger: List[str], callback: Callable, mode=EVT_DISJUNCTION):
        self._callbacks.append(callback)
        self._triggers.append((mode, set(trigger)))

    def _get_param_diff(self, new_params: Dict[str, str]) -> set:
        if self._previous_params is None:
            if self.trigger_on_blank:
                return {k for k in new_params.keys()}
            else: 
                return set([])
        else:
            diffs = []
            for k in self._previous_params.keys():
                if self._previous_params[k] != new_params[k]:
                    diffs.append(k)
            return set(diffs)
    def process_parameters(self, params: Dict[str, str], curr_config: Dict[str, str]):
        #Potentially modifies global_config
        curr_trigger = self._get_param_diff(params)
        logger.info(f"{curr_trigger=}")
        self._previous_params = params
        for i, evt_trigger in enumerate(self._triggers):
            mode, trigger = evt_trigger
            if mode == EVT_DISJUNCTION and len(curr_trigger.intersection(trigger)) > 0:
                logger.info(f"Processing disjunction triggers for {trigger}...")
                self._callbacks[i](params, curr_config)
                continue
            elif mode == EVT_CONJUNCTION and trigger.issubset(curr_trigger):
                logger.info(f"Processing conjunction triggers for {trigger}...")
                self._callbacks[i](params, curr_config)
                
class FileGenerator:
    def __init__(self, experiment_path: str, remote: str, clean: bool=False, ssh_cfg:SSHConfig=None):
        self.experiment_path = experiment_path
        self.remote = remote
        self.ssh_cfg = ssh_cfg
        if clean:
            self._clean()
        self.batcher = BatchedUploader(experiment_path)
    def _clean(self):
        script_dst = os.path.join("~", self.experiment_path)
        logger.info(f"Removing directory {script_dst}")
        if script_dst == "~" or script_dst == "~/" or script_dst == "~\\"  or script_dst == "." or script_dst == "./" or len(script_dst) == 0:
            logger.info("Tried to rm user directory !")
            return
        logger.info(remote_tmux_send(self.remote, f"rm -rf {script_dst}"))

    def render_script(self, file: str, config: Dict[str, Any]) -> str:
        return remote_upload_rendered_script(self.remote, self.experiment_path, file, config, ssh_cfg=self.ssh_cfg)

    def upload_script(self, file: str) -> str:
        remote_tmux_ensure_dir(self.remote, os.path.join(self.experiment_path, REMOTE_RENDERS_DIR))
        script_dst = os.path.join("~", self.experiment_path, REMOTE_RENDERS_DIR, os.path.basename(file))
        remote_upload_file(self.remote, file, script_dst, ssh_cfg=self.ssh_cfg)
        return script_dst
    
    def upload_scripts(self, files: List[str], use_glob=True) -> List[str]:
        for path in files:
            if use_glob and '*' in path:
                print(f"{glob(path)=}")
                for f in glob(path):
                    self.batcher.add_script(f)
            else:
                self.batcher.add_script(path)
        return self.batcher.upload(self.remote, ssh_cfg=self.ssh_cfg)
