# https://rigtorp.se/low-latency-guide/

# run as sudo su

sudo apt install -y tuned tuna

echo off > /sys/devices/system/cpu/smt/control

echo "Verify HT disabled - should show 0"
cat /sys/devices/system/cpu/smt/active
read


tuned-adm profile latency-performance

echo "Verify CPU frequency - the range should be equal to the max frequency"
cpupower frequency-info
read

pgrep -P 2 | xargs -i taskset -p -c 0 {}
tuna --cpus=1-7 --isolate

echo "Verify CPU affinities for all threads - should stay away from 1-7"
tuna -P
read

find /sys/devices/virtual/workqueue -name cpumask  -exec sh -c 'echo 1 > {}' ';'

echo "Verify CPU affinities of work queues - should stay away from 1-7"
find /sys/devices/virtual/workqueue -name cpumask -print -exec cat '{}' ';'
read
echo "Verify low amount of context switches"
perf stat -e 'sched:sched_switch' -a -A --timeout 10000
read

sysctl vm.stat_interval=120

echo "Verify low amount of timer interrupts"
perf stat -e 'irq_vectors:local_timer_entry' -a -A --timeout 30000
read

irqbalance --foreground --oneshot

echo "Verify that cores don't receive interrupts"
echo "watch cat /proc/interrupts"
#PIDWATCH=$!
#sleep 10 && kill $PIDWATCH
#read

# turn off swap
swapoff -a
# disable transparent hpages
echo never > /sys/kernel/mm/transparent_hugepage/enabled
# disable
echo 0 > /proc/sys/kernel/numa_balancing

echo 0 > /sys/kernel/mm/ksm/run


echo "Welcome to the low latency setup"
