import re
event_regex = re.compile("EVENT (?P<name>[\w\d-]+)")
test_case = """
ubuntu@bf2-dormeur:~$ source ~/rgx-benchmark-colin/renders/rx_1713653422.sh
RESULT-rules_contents_cnt 3272
RESULT-rules_pcres_cnt 50
ubuntu@bf2-dormeur:~/rgx-benchmark-colin/builddir$ EAL: 122 hugepages of size 209
7152 reserved, but no mounted hugetlbfs found for that size
clear
ubuntu@bf2-dormeur:~/rgx-benchmark-colin/builddir$ mlx5_net: Cannot retrieve PCI
address of IB device mlx5_2
TELEMETRY: No legacy callbacks, legacy socket not created
EVENT starting-rx
lcore 2  port queue 1   ready to receive pkts
lcore 5  port queue 4   ready to receive pkts
lcore 4  port queue 3   ready to receive pkts
lcore 6  port queue 5   ready to receive pkts
lcore 7  port queue 6   ready to receive pkts
lcore 1  port queue 0   ready to receive pkts
lcore 3  port queue 2   ready to receive pkts
"""
match = event_regex.search(test_case)
print(match.group('name') == "starting-rx")