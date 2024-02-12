from suricataparser import parse_rule, Rule
import os
import subprocess as sp
import re
from typing import List
content_modifiers = [
    "nocase", "depth", "startswith", "endswith",
    "offset", "distance", "within", "rawbytes",
    "isdataat", "bsize", "dsize", "byte_test",
    "byte_math", "byte_jump", "byte_extract",
    "rpc", "replace", "pcre", "fast_pattern"
]
def write_to_file_or_print(output, message):
    """Write message to a file if output is specified, otherwise print."""
    if output:
        with open(output, 'w') as file:
            file.write(message + "\n")
    else:
        print(message)

def bool_parse(s: str):
    lc = s.lower()
    if lc == "true":
        return True
    elif lc == "false":
        return False
    elif int(lc) > 0:
        return True
    elif int(lc) == 0:
        return True
    return None
def unquote(s: str):
    if len(s) < 2:
        return f"{s}"
    if s[0] == '"' and s[-1] == '"':
        return f"{s[1:-1]}"
    return f"{s}"
def filter_options(rule: Rule, filter_func):
    options = []
    for opt in rule._options:
        if filter_func(opt):
            options.append(opt)
    rule._options = options
    rule.build_rule()
def transform_options(rule: Rule, name, trans_func):
    options = []
    for opt in rule._options:
        if opt.name == name:
            opt.value = trans_func(opt.value)
        options.append(opt)
    rule._options = options
    rule.build_rule()
def replace_option(rule: Rule, name1, name2):
    options = []
    for opt in rule._options:
        if opt.name == name1:
            opt.name = name2
        options.append(opt)
    rule._options = options
    rule.build_rule()
def filter_whitespace(lines):
    return [l.replace("\n", "") for l in lines if not l.strip() == "\n" and not len(l.strip()) == 0]

def to_rxpc(file_path: str, uniqify=False, only_content=False, only_pcre=False):
    contents = extract_content_strings(file_path) if not only_pcre else []
    pcres = extract_pcres(file_path, rxpc_compatible=False) if not only_content else []
    if uniqify:
        patterns = list(set(pcres + contents))
    else:
        patterns = pcres + contents
    ret = [
        f"{i + 1}, {p}"
        for i,p in enumerate(patterns)
    ]
    return ret
def extract_pcres(file_path: str, rxpc_compatible=True):
    with open(file_path, 'r') as f:
        lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]

    lines = filter_whitespace(lines)
    ret = []
    rgx_idx = 1
    for l in lines:
        r = parse_rule(l)

        opt_list = r.get_option("pcre")

        if opt_list:
            for rgx in opt_list:
                pcre_str = unquote(rgx.value)
                if rxpc_compatible:
                    ret.append(f"{rgx_idx}, {pcre_str}")
                else:
                    ret.append(pcre_str)
                rgx_idx += 1
                
    return ret 
def suricata_content_to_regex(content):
    # Split the content on '|', but keep the '|' characters for clarity
    parts = content.split('|')
    regex_parts = []

    # Flag to indicate if we are inside a hex block
    in_hex_block = False

    for part in parts:
        if in_hex_block:
            part = part.replace(" ", "")
            # Convert hex sequence to binary regex
            regex_parts.append(''.join(f'\\x{part[i:i+2]}' for i in range(0, len(part), 2)))
        else:
            # Convert non-hex part directly, escaping special regex characters as needed
            for char in part:
                if char in ',.^$*+?{}[]\\|()/':
                    regex_parts.append(f'\\{char}')
                else:
                    regex_parts.append(char)

        # Toggle hex block flag
        in_hex_block = not in_hex_block

    return ''.join(regex_parts)

def extract_content_strings(file_path):
    """Extract and return all content strings from the rules in the file."""
    content_strings = []

    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            rule = parse_rule(line)
            for opt in rule.options:
                if opt.name == "content":
                    content_val = opt.value.strip('"')
                    content_regex = suricata_content_to_regex(content_val)
                    content_strings.append(content_regex)

    return content_strings
rxcp_modifiers = ["/i", "/m", "/s", "/x"]
def filter_rxpc(
        db_in: str, db_out: str, temp_rgx_file: str,
        rof2_out: str, include_pcres: bool, include_literals: bool,
        max_rules: int=0xFFFFFFF
    ):
    with open(db_in, 'r') as f:
        db_in_lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]
    in_rgxs = []
    i = 1
    id2sid = {} #We need that because having the same id for multiple instances makes the regex compilation crash
    uncompiled_idxs = set()
    excluded_sids = set()
    initial_sids = set()
    for l in db_in_lines:
        if i >= max_rules:
            break
        r = parse_rule(l)
        sid = r.get_option('sid')[0].value 
        initial_sids.add(sid)
        if include_literals:
            opt_list = r.get_option("content")
            if opt_list:
                illegal_cntnt = False
                for cntnt in opt_list:
                    if cntnt.value.startswith("!"):
                        print(f"Ignoring negative   content: {cntnt.value}")
                        illegal_cntnt = True
                        break
                    cntnt = suricata_content_to_regex(unquote(cntnt.value))
                    #ret.append(f"{r.get_option('sid')[0].value}, {unquote(rgx.value)}\n")
                    in_rgxs.append(f"{i}, {cntnt}\n")
                    id2sid[i] = sid
                    i += 1
                if illegal_cntnt:
                    print(f"Added {sid=} to excluded sids.")
                    excluded_sids.add(sid)
        if include_pcres:
            opt_list = r.get_option("pcre")
            if opt_list:
                for rgx in opt_list:
                    #ret.append(f"{r.get_option('sid')[0].value}, {unquote(rgx.value)}\n")
                    val = unquote(rgx.value)
                    stripped = val.strip()
                    illegal_rgx = True
                    for m in rxcp_modifiers:
                        if stripped.endswith(m):
                            illegal_rgx = False
                            break
                    if illegal_rgx:
                        excluded_sids.add(sid)
                        break

                    in_rgxs.append(f"{i}, {unquote(rgx.value)}\n")
                    id2sid[i] = sid
                    i += 1
            
    with open(temp_rgx_file, 'w') as outf:
        outf.writelines(in_rgxs)
    #run the rxpc compiler
    command = \
        f'rxpc -F -s --file={os.getcwd()}/{temp_rgx_file} -o {os.getcwd()}/{rof2_out}'
    print(command)
    ran = sp.run(command, shell=True)
    #find out which rules could not be compiled
    uncompiled_file = f"{rof2_out}_uncompiled_rules.log"
    rgx_rule_idx = re.compile("(Rule_index|rule_id):\s*(?P<id>\d+)")
    with open(uncompiled_file, "r") as f:
        uncompiled_lines = f.readlines()
    for l in uncompiled_lines:
        match = rgx_rule_idx.search(l)
        if match:
            rule_id = int(match.group('id'))
            uncompiled_idxs.add(rule_id)
    print(f"{len(uncompiled_idxs)} rules could not be compiled")
    #convert back the ids to sids
    excluded_sids.update({id2sid[i] for i in uncompiled_idxs})
    #filter the original rule file with rules that could be compiled
    db_out_lines = []
    for l in db_in_lines:
        r = parse_rule(l)
        sid = r.get_option('sid')[0].value
        if sid not in excluded_sids and sid in initial_sids:
            db_out_lines.append(f"{l}\n")
    with open(db_out, "w") as f:
        f.writelines(db_out_lines)
    target = "pcre" if include_pcres else ""
    target += "+literals" if include_literals else ""
    print(
f"""
Report:
{'-'*40}
Input: {db_in}
    rules: {len(db_in_lines)}
    {target}: {len(in_rgxs)}
Output: {db_out}
    rules: {len(db_out_lines)}
    uncompiled_{target}: {len(uncompiled_idxs)}
    {target}: {len(in_rgxs) - len(uncompiled_idxs)}
{'-'*40}
"""
    )
def rxcp_get_n_uncompiled(rof2_name: str):
    extractor = re.compile("Total number of uncompiled rules,(?P<nuncompiled>\d+)")
    with open(f"{rof2_name}_uncompiled_rules_summary.csv") as f:
        lines = f.readlines()
    m = extractor.search(lines[-1])
    if m:
        return int(m.group('nuncompiled'))
    else:
        raise RuntimeError(f"Cannot parse {rof2_name}_uncompiled_rules_summary.csv")
def provide_lines(line_source: List | str, clean_first: bool = True) -> List[str]:
    """
    Returns a list of lines from the given line_source.

    Args:
        line_source (List | str): The source of lines. It can be either a list of strings or a file path.
        clean_first (bool, optional): Indicates whether to clean the lines by removing leading/trailing whitespace and comments. Defaults to True.

    Returns:
        List[str]: The list of lines.

    Raises:
        FileNotFoundError: If the file specified by line_source does not exist.

    """
    if isinstance(line_source, List):
        return line_source
    
    if isinstance(line_source, str):
        with open(line_source, "r") as f:
            lines = f.readlines()
        if clean_first:
            return [
                l.strip()
                for l in filter_whitespace(lines)
                if not l.strip().startswith("#")
            ]
        else:
            return lines
        