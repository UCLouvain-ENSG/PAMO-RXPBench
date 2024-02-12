#!/bin/bash
#we use all database defining variables for the curr id name
curr_id=nr{{n_rules}}_patlengte{{rules_patlen_greaterthan}}_ct{{rules_use_content_kw}}_pcre{{rules_use_pcre_kw}}_subsets{{rule_subset_ratio}}
curr_id_uniq=""
extract_pcres() {
    python3 rule_sampler.py --output_file $EXPATH/$curr_id.pcres $EXPATH/$curr_id.rules extract_pcres
    sort $EXPATH/$curr_id.pcres | uniq > $EXPATH/$curr_id_uniq.pcres.tmp
{% if rules_patlen_greaterthan | int > 0 %}
    # filter out rules to only include pattern length greater than {{rules_patlen_greaterthan}}
    PATLEN={{ rules_patlen_greaterthan }}
    grep -E "^.{$PATLEN,}$" "$EXPATH/$curr_id_uniq.pcres.tmp" > "$EXPATH/$curr_id_uniq.pcres"
{% endif %}

    echo "RESULT-rules_pcres_cnt $(wc -l $EXPATH/$curr_id_uniq.pcres | awk '{print $1}')" >> /tmp/rgx_cnt
    cat $EXPATH/$curr_id_uniq.pcres >> $EXPATH/$curr_id_uniq.regexes
}


extract_contents() {
    python3 rule_sampler.py $EXPATH/$curr_id.rules extract_content --output_file $EXPATH/$curr_id.contents
    sort $EXPATH/$curr_id.contents | uniq > $EXPATH/$curr_id_uniq.contents.tmp
{% if rules_patlen_greaterthan | int > 0 %}
    # filter out rules to only include pattern length greater than {{rules_patlen_greaterthan}}
    PATLEN={{ rules_patlen_greaterthan }}
    grep -E "^.{$PATLEN,}$" "$EXPATH/$curr_id_uniq.contents.tmp" > "$EXPATH/$curr_id_uniq.contents"
{% endif %}
    echo "RESULT-rules_contents_cnt $(wc -l $EXPATH/$curr_id_uniq.contents | awk '{print $1}')" >> /tmp/rgx_cnt
    cat $EXPATH/$curr_id_uniq.contents >> $EXPATH/$curr_id_uniq.regexes
}

# main fn
cd $RENDIR
echo "RENDIR=$RENDIR"
cp $RENDIR/{{pattern_db}} $EXPATH/{{pattern_db}}
pip3 install suricataparser trieregex

python3 rule_sampler.py $RENDIR/{{pattern_db}} sample --arg0 {{n_rules}} \
{% if fixed_seed | int > 0 %} --arg1 1 {% endif %}\
--output_file $EXPATH/$curr_id.rules
#delete leftovers from previous runs, 
#$curr_id_uniq.regexes serves as the compiler input
rm -f $EXPATH/$curr_id_uniq.regexes
rm -f /tmp/rgx_cnt
    
{% if rules_use_content_kw | int == 0 and rules_use_pcre_kw | int == 0 %}
echo "EXPRUN-FAILED: Likely a wrong configuration, both content and pcre keywords are disabled"
exit 1
{% endif %}

{% if rules_use_content_kw | int == 1 %}
#send uniqd contents to $curr_id_uniq.regexes
extract_contents
{% endif %}

{% if rules_use_pcre_kw | int == 1 %}
#send uniqd regexes to $curr_id_uniq.regexes
extract_pcres
{% endif %}

{% if rgx_enabled | int == 1 %}
# RXP specific
awk '{print NR "," $0}' $EXPATH/$curr_id_uniq.regexes > $EXPATH/$curr_id_uniq.rxpc

{% if rule_subset_ratio is defined %}
mv $EXPATH/$curr_id_uniq.rxpc $EXPATH/$curr_id_uniq.rxpc.orig
python3 rule_sampler.py $EXPATH/$curr_id_uniq.rxpc.orig rules_to_subsets --arg0 {{rule_subset_ratio}} --output_file $EXPATH/$curr_id_uniq.rxpc
{% endif %}
# check if the precompiled version can be found
precompiled=precompiled_$curr_id
if test -f $EXPATH/$precompiled; then
  echo "Using precompiled rof2...$precompiled"
  cp $EXPATH/$precompiled $EXPATH/current.rof2.binary
else
    # -o is the base filename, the real output is in .rof2.binary for BF test
    cp $EXPATH/$curr_id_uniq.rxpc /tmp/$curr_id_uniq.rxpc
    rxpc -f $EXPATH/$curr_id_uniq.rxpc -a -F -t 1 -o $EXPATH/$curr_id
    cp $EXPATH/$curr_id.rof2.binary $EXPATH/$precompiled
    cp $EXPATH/$curr_id.rof2.binary $EXPATH/current.rof2.binary

fi

# -o is the base filename, the real output is in .rof2.binary for BF test
rxpc -f $EXPATH/working_set_uniq.rxpc -a -F -t 1 -o $EXPATH/working_set_compiled

{% elif hs_enabled | int == 1 %}
# Hyperscan specific
python3 rule_sampler.py $EXPATH/$curr_id_uniq.regexes to_hyperscan --output_file $EXPATH/current.hyperscan
{% endif %}
