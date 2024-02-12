#!/usr/bin/python3
import argparse
from random import seed, sample, randint
from time import time
from suricataparser import parse_rule, Rule
from rule_lib import *
import re
import sys
import itertools as it
import math
from trieregex import TrieRegEx as TRE
from typing import List
NO_INPUT_FILE="-"
def count_lines(file_path):
    """Count the number of lines in a file."""
    with open(file_path, 'r') as f:
        lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]
    return len(lines)

re_imcomplete_port = re.compile("\d{1,5}:$")
re_http_fix = re.compile('http[\._](.*)')
allowed_http_options = [
    "uri", "cookie", "host", "server",
    "referer", "content_type", "location", "request_body",
    "response_body", "user_agent"
]
content_kw = ["content", "pcre"]
prefix_content_modifier_before = ["http.", "dns."]
def clean_and_fix(file_path, keep_original=True):
    #remove comments and metadata
    with open(file_path, 'r') as f:
        lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]
    res = []
    for l in lines:
        rule = parse_rule(l)
        rule.pop_option("bsize")

        #Remove unsupported pptions
        filter_options(rule, lambda opt: opt.name not in [
            "metadata", "reference", "classtype", "target",
            "isdataat", "bsize"
        ])
        #remove negative content. We have to do it manually as we have to remove all the modifiers etc related to a content
        new_options = []
        options = rule.options
        idx = 0
        while idx < len(rule.options):
            curr_opt = options[idx]

            if (curr_opt.name == "content" and curr_opt.value.startswith("!")) or curr_opt.name == "pcre":
                back_idx = 1
                while not new_options[-back_idx].name in content_kw and back_idx <= len(new_options) - 1:
                    for prefix in prefix_content_modifier_before:
                        if new_options[-back_idx].name.startswith(prefix):
                            del new_options[-back_idx]
                    back_idx += 1
                idx += 1
                while options[idx].name not in ["sid", "content", "pcre"] and not options[idx].name.startswith("http."):
                    idx += 1
            else:
                new_options.append(curr_opt)
                idx += 1
        rule._options = new_options
        rule.build_rule()

        #fix flow not supporting commas
        def fix_flow(val):
            flow_vals = val.split(",")
            for v in flow_vals:
                stripped = v.strip()
                if stripped in ["from_client", "to_client", "from_server", "to_server"]: 
                    return stripped
        transform_options(rule, "flow", fix_flow)
        replace_option(rule, "dns_query", "dns.query")
        replace_option(rule, "tls_sni", "tls.sni")         
        #fix header with implicit max higher port
        if re_imcomplete_port.search(rule.header):
            rule._header = rule.header + '65535'
        #only accepts http options that are legal according to the doca doc
        for opt in rule.options:
            match = re_http_fix.search(opt.name)
            if match and match.group(1) not in allowed_http_options: 
                filter_options(rule,
                    lambda x: x.name != opt.name
                )
        #Fix tcp-pkt and tcp-stream not supported
        rule._header = rule.header.replace("tcp-pkt", "tcp")
        rule._header = rule.header.replace("tcp-stream", "tcp")
        clean_dangling_modifiers(rule)
        res.append(rule.build_rule())
    return res

def clean_dangling_modifiers(rule: Rule):
    
    for opt in rule.options:
        if opt.name == "content":
            return
        if opt.name in content_modifiers:
            rule.pop_option(opt.name)
    
def preview_file(file_path, num_lines=5):
    """Print the first few lines of a file."""
    with open(file_path, 'r') as file:
        for _ in range(num_lines):
            line = file.readline()
            if not line:
                break
            print(line.strip())

def sampleX(inputs: List | str, X, fixed_seed=0):
    if seed:
        seed(fixed_seed)
    else:
        seed(time())
    return sample(provide_lines(inputs), X)

re_tls_opt = re.compile('tls[\._](.*)')

re_content_hex = re.compile('.*".*\|([0-9a-fA-F]{2} {0,1})+\|.*".*')
def filter_rule(line: str):
    rule = parse_rule(line)
    
    contents = rule.pop_option("content")
    neg_contents = 0
    for c in contents:
        value = c.value
        if value.startswith("!"):
            neg_contents += 1
            continue
        rule.add_option("content", c)
        # Apparently hex is supported
        # if re_content_hex.search(value) is not None: 
        #     return -1
    if neg_contents == len(contents):
        return -1
    #TODO transform tls_sni into tls_sni
    for err, opt in [
        (-2, "endswith"), (-3, "offset"), (-4, "distance"),
        (-5, "threshold"), (-6, "depth"), (-7, "flowbits"),
        (-8, "within"), (-9, "urilen"), (-10, "ja3_hash"),
        (-11, "byte_test"), (-12, "byte_math"), (-13, "byte_jump"),
        (-14, "stream_size"), (-15, "ja3.hash")
        ]:
        if len(rule.get_option(opt)):
            return err
    for opt in rule.options:
        match = re_tls_opt.search(opt.name)
        if match and match.group(1) != "sni": 
            return -19
    #Exclude headers which contain some grouping
    #We should try finding a workaround
    if "[" in rule.header:
        return -20
    for err, prot in [(-21, "smtp"), (-22, "ftp")]:
        if prot in rule.header:
            return err

    return 0




def doca_filter(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    lines = filter_whitespace(lines)
    hist = {}
    filtered = []
    for l in lines:
       err = filter_rule(l)
       if err == 0:
           filtered.append(l)
       hist[err] = hist.get(err, 0) + 1
    return filtered    

def analyze(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    lines = filter_whitespace(lines)
    if len(lines) ==0:
        print("Nothing to do in empty file.")
        return
    if len(lines) > 1:
        print("Analyze will only analyze the first rule of the file !")
    rule = parse_rule(lines[0])
    print(f"Rule header = {rule.header}")
    if re_imcomplete_port.search(rule.header):
        print(f"Problematic header:{rule.header}")
        print(f"Fixed header:{rule.header+'65535'}")

            #only accepts http options that are legal according to the doca doc
    for opt in rule.options:
        match = re_http_fix.search(opt.name)
        if match and match.group(1) not in allowed_http_options: 
            print(f"Option {opt.name} not allowed !")
            print(f"{rule.pop_option(opt.name)[0].name=}")




def to_hyperscan(file_path: str, from_patterns=True, to_hs_tools=False, return_sid_map=False, ):
    # By default, will use a file with one line per pattern as input
    # If from_patterns is false, it will be read from a rule file with suricata rule format
    # Function to escape ^ { } $ inside the smallest character groups
    def escape_chars(match):
        group_content = match.group(0)
        for char in "^{}$":
            # Use a regular expression to find instances of the character not preceded by a backslash
            # The pattern uses a negative lookbehind assertion to ensure the char is not escaped
            group_content = re.sub(r'(?<!\\)' + re.escape(char), r'\\' + char, group_content)
        return group_content

    with open(file_path, "r") as f:
        if not from_patterns:
            lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]
        else:
            lines = f.readlines()
    if not from_patterns:
        patterns = []
        i = 0
        id2sid = {}
        for l in lines:
            r = parse_rule(l)
            sid = r.get_option('sid')[0].value
            pcres = [unquote(el.value) for el in r.get_option("pcre")]
            literals = [f"/{suricata_content_to_regex(unquote(el.value))}/" for el in r.get_option("content")]
            for _ in pcres:
                id2sid[i] = sid
                i += 1
            for _ in literals:
                id2sid[i] = sid
                i += 1
            patterns += pcres + literals
        lines = patterns
    else:
        lines = filter_whitespace(lines)

    hs_escaped_lines = []
    pattern = re.compile(r'^/(.*)/')

    for i, line in enumerate(lines):
        match = pattern.search(line)
        matched_pattern = match.group(1) if match else line
        fixed_pattern = re.sub(r'\[[^\]]*]', escape_chars, matched_pattern)
        # Use regular expression to find and replace the smallest character groups
        if match and to_hs_tools:
            ends = line.split(matched_pattern)
            hs_escaped_lines.append(
                f"{i + 1}:{ends[0]}{fixed_pattern}{ends[1]}"
            )
        else:
            hs_escaped_lines.append(fixed_pattern)
    if return_sid_map:
        return hs_escaped_lines, id2sid
    else:
        return hs_escaped_lines
def filter_hyperscan(db_in: str, db_out: str):
    lines, id2sid = to_hyperscan(db_in, from_patterns=False, to_hs_tools=True, return_sid_map=True)
    with open("temp.hst", "w") as f:
        f.writelines([f"{l}\n" for l in lines])
    command = \
        f'hscheck -e {os.getcwd()}/temp.hst'
    ran = sp.run(command, shell=True, capture_output=True)
    if ran.returncode != 0:
        print(f"Error while running command:\n{command}", file=sys.stderr)
        exit(-1)
    out = ran.stdout.decode()
    lines = out.split(os.linesep)
    excluded_sids = set()
    for l in lines:
        els = l.split(":")
        if len(els) <= 3:
            continue
        if els[0] not in ["OK", "SUMMARY"]:
            rule_id = int(els[1].strip())
            excluded_sids.add(id2sid[rule_id])
    with open(db_in, 'r') as f:
        db_in_lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]
    db_out_lines = []
    for l in db_in_lines:
        r = parse_rule(l)
        sid = r.get_option('sid')[0].value
        if sid not in excluded_sids:
            db_out_lines.append(f"{l}\n")
    with open(db_out, "w") as f:
        f.writelines(db_out_lines)


def full_rxpc_filter(db_in: str, db_out: str, iterative:bool=False, max_rules:int=0xFFFFFFFF):
    out_name = os.path.basename(db_out).split(os.path.extsep)[0]
    filter_rxpc(db_in, db_out, "temp.rgx", out_name, True, True, max_rules=max_rules)
    n_it = 1
    while iterative and rxcp_get_n_uncompiled(out_name) > 0:
        filter_rxpc(db_out, db_out, "temp.rgx", out_name, True, True, max_rules=max_rules)
        n_it += 1
    print(f"Generated working set in {n_it} iterations !")
def analyze_docaflow(db_in: str):
    with open(db_in, 'r') as f:
        lines = [l.strip() for l in  filter_whitespace(f.readlines()) if not l.strip().startswith("#")]
    k1 = "startswith"
    k2 = "offset+depth"
    k3 = "bytetest"
    k4 = "total"
    stats = {k1: 0, k2:0, k3:0, k4:0}
    for l in lines:
        r = parse_rule(l)
        #remove contents with negative match
        contents = r.get_option("content")
        neg = False
        for c in contents:
            if c.value.startswith("!"):
                neg = True
                break
        stats[k4] += len(contents)
        if neg: continue
        stats[k1] += len(r.get_option("startswith"))
        stats[k2] += len(r.get_option("offset")) + len(r.get_option("depth"))
        stats[k3] += len(r.get_option("byte_test"))
    return f"Stats of rules for flow acceleration potential {str(stats)}"
def gen_prefixes(prefix_size: int=4, max_prefixes: int=32000):
    alphabet = [chr(i) for i in range(ord('a'), ord('z') + 1)]
    alphabet += [a.upper() for a in alphabet]
    prefixes = [
        comb for i, comb in enumerate(it.combinations(alphabet, prefix_size))
        if i < max_prefixes
    ]
    if len(prefixes) < max_prefixes:
        print(
            f"Could not find enough prefixes !\n"+\
            f"Required {max_prefixes} found only {len(prefixes)}"
        )
    return [''.join(t) for t in prefixes] 
    
def rules_from_patterns(in_file: str):
    with open(in_file, "r") as f:
        lines = f.readlines()
    patterns = [l.strip() for l in  filter_whitespace(lines) if not l.strip().startswith("#")]
    rules = []
    for i, p in enumerate(patterns):
        rule = Rule(True, "alert", "tcp any any -> any any", [])
        rule.add_option("content", p)
        rule.add_option("sid", i)
        rules.append(str(rule))
    return rules
def compress_patterns(in_file: str, factor: int=10):
    with open(in_file, "r") as f:
        lines = f.readlines()
    rules = [parse_rule(l.strip()) for l in  filter_whitespace(lines) if not l.strip().startswith("#")]
    patterns = []
    for r in rules:
        contents = r.get_option("content")
        for c in contents:
            patterns.append(unquote(c.value))
    n_patterns_0 = len(patterns)
    patterns = list(set(patterns))
    n_patterns_1 = len(patterns)
    groups = [
        [patterns[i:i+factor]]
        for i in range(0, len(patterns), factor)
    ]
    compressed_patterns = [TRE(*g).regex() for g in groups]
    n_patterns_2 = len(compressed_patterns)
    print(f"Compression stages: {n_patterns_0}, {n_patterns_1}, {n_patterns_2}")
    return compressed_patterns
    
# https://docs.nvidia.com/doca/archive/doca-v2.2.0/rxp-compiler/index.html#subset-ids
def rules_to_subsets(input_file: str, output_file: str, ratio_str: str):
    """_summary_
    arg0 is list of ratios (equal to 1.0) - e.g. "0.1:0.2:0.7"
    input file is list of RXPC rules
    output file is list of RXPC rules with rules divided into subsets per specified ratios
    
    input file:
    1,000
    2,0001aodwyr
    3,0005s5
    4,0006
    5,0007zbu
    6,0009firv
    7,000b9z3vj
    8,000cg
    9,000f32zp5e
    10,000jphiaky
    
    arg0: 
    "0.1:0.2:0.7"

    output file:
    subset_id=1
    1,000
    subset_id=2
    2,0001aodwyr
    3,0005s5
    subset_id=3
    4,0006
    5,0007zbu
    6,0009firv
    7,000b9z3vj
    8,000cg
    9,000f32zp5e
    10,000jphiaky
    

    Args:
        input_file (str): _description_
        output_file (str): _description_
        ratio_str (str): _description_

    Raises:
        ValueError: _description_
    """
    ratios = list(map(float, ratio_str.split(':')))
    if math.fsum(ratios) != 1:
        raise ValueError(f"Ratios must sum to 1, current {math.fsum(ratios)}.")

    with open(input_file, 'r') as file:
        rules = file.readlines()
    total_rules = len(rules)
    if (total_rules <= len(ratios)):
        raise ValueError("Number of rules must be greater than number of ratios.")
    rule_counts = [int(ratio * total_rules) for ratio in ratios]
    
    # Handle rounding issues by adjusting the last group
    rule_counts[-1] += total_rules - sum(rule_counts)

    start_idx = 0
    with open(output_file, 'w') as file:
        for i, count in enumerate(rule_counts, start=1):
            file.write(f'subset_id={i}\n')
            for rule in rules[start_idx:start_idx + count]:
                file.write(rule)
            start_idx += count

def compress_patterns(inputs: List | str, factor: int=10):
    rules = [parse_rule(l) for l in provide_lines(inputs)]
    patterns = []
    for r in rules:
        contents = r.get_option("content")
        for c in contents:
            patterns.append(unquote(c.value))
    n_patterns_0 = len(patterns)
    patterns = list(set(patterns))
    n_patterns_1 = len(patterns)
    groups = [
        [patterns[i:i+factor]]
        for i in range(0, len(patterns), factor)
    ]
    compressed_patterns = [TRE(*g).regex(do_escape=False) for g in groups]
    #unescape special characters ? and |
    #These characters are replaced by \\? and \\| in the compressed patterns
    #We need to replace them back to ? and |
    print(f"Compressed patterns:\n {compressed_patterns}")
    n_patterns_2 = len(compressed_patterns)
    print(f"Compression stages: {n_patterns_0}, {n_patterns_1}, {n_patterns_2}")
    return compressed_patterns


def rgx_list_to_rxpc(inputs: List | str):
    return [f"{i+1}, /{rgx}/" for i,rgx in enumerate(provide_lines(inputs))]
    
def main():
    parser = argparse.ArgumentParser(description="Process a file.")
    parser.add_argument("input_file", type=str, help="The file to process")
    parser.add_argument("action", type=str, choices=
                        [
                            "to_hyperscan", "to_rxpc", "count",
                            "preview", "cleanfix", "filter", "sample",
                            "analyze", "extract_content", "extract_pcres",
                            "gen_working_set", "filter_rxpc", "filter_hs",
                            "analyze_docaflow", "gen_prefixes", 
                            "rules_from_patterns", "rules_to_subsets",
                        ],
                        help="The action to perform on the file ('count' or 'preview')")
    parser.add_argument("--output_file", type=str, help="Optional output file")
    parser.add_argument("--arg0", type=str, help="First argument of action")
    parser.add_argument("--arg1", type=str, help="Second argument of action")
    
    args = parser.parse_args()
    if args.input_file != NO_INPUT_FILE and not os.path.exists(args.input_file):
        print(f"File {args.input_file} not found !", file=sys.stderr)
        exit(-1)
    if args.action == "count":
        line_count = count_lines(args.input_file)
        write_to_file_or_print(args.output_file, f"rule count: {line_count}")
    elif args.action == "preview":
        message = "Previewing the file..."
        write_to_file_or_print(args.output_file, message)
        preview_lines = preview_file(args.input_file)
        for line in preview_lines:
            write_to_file_or_print(args.output_file, line)
    elif args.action == "cleanfix":
        write_to_file_or_print(args.output_file, "\n".join(clean_and_fix(args.input_file)))
    elif args.action == "sample":
        n_samples = int(args.arg0)
        if args.arg1:
            fseed = int(args.arg1)
        else:
            fseed = None
        write_to_file_or_print(args.output_file, "\n".join(sampleX(args.input_file, n_samples, fixed_seed=fseed)))
    elif args.action == "filter":
        filtered = doca_filter(args.input_file)
        write_to_file_or_print(args.output_file, "\n".join(filtered))
    elif args.action == "analyze":
        analyze(args.input_file)
    elif args.action == "extract_content":
        content_strings = extract_content_strings(args.input_file)
        content_string_list = "\n".join(content_strings)
        write_to_file_or_print(args.output_file, content_string_list)
    elif args.action == "extract_pcres":
        pcres = extract_pcres(args.input_file, rxpc_compatible=False)
        write_to_file_or_print(args.output_file, "\n".join(pcres))
    elif args.action == "to_rxpc":
        kws = {}
        if args.arg0: kws['uniqify'] = bool_parse(args.arg0)
        if args.arg1: kws['only_content'] = bool_parse(args.arg1)
        merged = to_rxpc(args.input_file, **kws)
        write_to_file_or_print(args.output_file, "\n".join(merged))
    elif args.action == "to_hyperscan":
        #TODO Add support for per-expression flags
        print(f"WARNING: Skipping per-expression flags !", file=sys.stderr)
        kws = {}
        if args.arg0: kws['from_patterns'] = bool_parse(args.arg0)
        if args.arg1: kws['to_hs_tools'] = bool_parse(args.arg1) 
        merged = to_hyperscan(args.input_file, **kws)
        write_to_file_or_print(args.output_file, "\n".join(merged))
        print(f"WARNING: Hyperscan export does NOT currently support per-expression flags !", file=sys.stderr)
    elif args.action == "gen_working_set":
        kws = {}
        if args.arg0: kws['max_rules'] = int(args.arg0)
        if args.arg1: kws['iterative'] = bool_parse(args.arg1)
        full_rxpc_filter(args.input_file, args.output_file, **kws)
        filter_hyperscan(args.output_file, args.output_file)
        print(f"RXPC + HS filtered working set written to {args.output_file}")
    elif args.action == "filter_rxpc":
        kws = {}
        if args.arg0: kws['include_pcres'] = bool_parse(args.arg0)
        if args.arg1: kws['include_literals'] = bool_parse(args.arg1)
        rof2name = os.path.basename(args.output_file).split(os.path.extsep)[0]
        filter_rxpc(
            args.input_file, args.output_file, "temp.rgx", rof2name,
            **kws
        )
        print(f"RXPC filtered dataset written to {args.output_file}")
        print(f"Generated rof2 files: {rof2name}.rof2, {rof2name}.rof2.binary")
    elif args.action == "filter_hs":
        filter_hyperscan(args.input_file, args.output_file)
        print(f"HSCHECK filtered dataset written to {args.output_file}")
    elif args.action == "analyze_docaflow":
        output = analyze_docaflow(args.input_file)
        write_to_file_or_print(args.output_file, output)
    elif args.action == "rules_from_patterns":
        rules = rules_from_patterns(args.input_file)
        write_to_file_or_print(args.output_file, "\n".join(rules))
    elif args.input_file == NO_INPUT_FILE and args.action == "gen_prefixes":
        kws = {}
        if args.arg0: kws['prefix_size'] = int(args.arg0)
        if args.arg1: kws['max_prefixes'] = int(args.arg1)
        prefixes = gen_prefixes(**kws)
        write_to_file_or_print(args.output_file, "\n".join(prefixes))
    elif args.action == "rules_to_subsets":
        ratios = args.arg0
        rules_to_subsets(args.input_file, args.output_file, ratios)
    elif args.action == "compress_patterns":
        kws = {}
        if args.arg0: kws['factor'] = int(args.arg0)
        if args.arg1:
            n_rules = int(args.arg1)
            lines = sampleX(args.input_file, n_rules)
        else:
            lines = provide_lines(args.input_file)
        #if args.arg1: kws['max_prefixes'] = int(args.arg1)
        compressed = rgx_list_to_rxpc(compress_patterns(lines, **kws))
        write_to_file_or_print(args.output_file, "\n".join(compressed))


if __name__ == "__main__": 
    main()
