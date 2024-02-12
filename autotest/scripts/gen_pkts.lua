local exp_framework_path = os.getenv("EXP_FRAMEWORK_PATH")
print(string.format("exp_framework_path=%s", exp_framework_path))
local pktgen_version = "23.06.1"
local pktgen_path = string.format("%s/pktgen/pktgen-%s", exp_framework_path, pktgen_version)
print(string.format("pktgen_path=%s\n", pktgen_path))
local pktgen_extra_package_path =
    string.format(
    ";%s/?.lua;%s/test/?.lua;%s/app/?.lua;%s/../?.lua",
    pktgen_path,
    pktgen_path,
    pktgen_path,
    pktgen_path
)
package.path = package.path .. pktgen_extra_package_path

require "Pktgen"

print("Loaded Pktgen.\n")

-- Set random seed
math.randomseed(os.time())
local first_byte = math.random(1, 255)
local second_byte = math.random(1, 255)
local third_byte = math.random(1, 255)
-- Generate a random source IP address
local first_byte = math.random(1, 255)
local second_byte = math.random(1, 255)
local third_byte = math.random(1, 255)
local fourth_byte = math.random(1, 255)


sendport = 0
PKT_SIZE = {{pkt_size}}
local dstip = "{{host_rx}}"
local srcip = "{{host_tx}}"
local srcmac = "{{mac_tx}}"
local dstmac = "{{mac_rx}}"

-- GEN INFO --
pktgen.ports_per_page(1)

pktgen.range.dst_mac("0", "start", dstmac)
pktgen.range.src_mac("0", "start", srcmac)

pktgen.set_range("0", "on")

pktgen.range.src_ip("0", "start", "1.2.3.4")
pktgen.range.src_ip("0", "min", "0.0.0.0")
pktgen.range.src_ip("0", "inc", "0.0.0.1")
pktgen.range.src_ip("0", "max", "255.255.255.255")

pktgen.range.dst_ip("0", "start", "5.6.7.8")
pktgen.range.dst_ip("0", "min", "0.0.0.0")
pktgen.range.dst_ip("0", "inc", "0.1.1.1")
pktgen.range.dst_ip("0", "max", "255.255.255.255")

pktgen.range.ip_proto("0", "udp")

pktgen.set("all", "size", PKT_SIZE);
pktgen.range.pkt_size("0", "start", PKT_SIZE)
pktgen.range.pkt_size("0", "inc", 0)
pktgen.range.pkt_size("0", "min", PKT_SIZE)
pktgen.range.pkt_size("0", "max", PKT_SIZE)

pktgen.range.dst_port("0", "start", 1024)
pktgen.range.dst_port("0", "inc", 1)
pktgen.range.dst_port("0", "min", 1024)
pktgen.range.dst_port("0", "max", 1500)

pktgen.range.src_port("0", "start", 2048)
pktgen.range.src_port("0", "inc", 1)
pktgen.range.src_port("0", "min", 2048)
pktgen.range.src_port("0", "max", 2048)

pktgen.set("0", "rate", {{target_tp}})
pktgen.set(sendport, "burst", {{tx_burst_size}})

pktgen.latency(sendport, "enable");
pktgen.latency(sendport, "rate", {{latency_rate}});
pktgen.latency(0, "entropy", 8);

pktgen.delay(1 * 1000)
pktgen.delay(100)

pktgen.start("0")
sleep({{rx_timeout | int}})
pktgen.stop("0")

pktgen.delay(1000)

--statRx = pktgen.portStats(0, "port")[0]
--num_rx = statRx.ipackets
--num_tx = statRx.opackets
--ibytes_rx = statRx.ibytes

--mbps_rx = ((num_rx * 24) + ibytes_rx) / TIME * 8 / 1000000

--pkt_stats = pktgen.pktStats(0)
--avg_cycles = pkt_stats[0].latency.avg_cycles
--avg_us = pkt_stats[0].latency.avg_us

--print(" RESULT-RX-RATE-PPS " .. math.floor(num_rx / TIME))
--print(" RESULT-RX-RATE-MBPS " .. mbps_rx)
--print(" RESULT-LOSE-RATE " .. 1-(num_rx / (num_tx)) .. "")
--print(" RESULT-AVG-LAT " .. avg_us .. "us")
--rate = pktgen.portStats(0, "rate")[0]
--print(" RESULT-RX-GOODPUT-MBPS-PKTGEN " .. rate.mbits_rx .. "")
--print(" RESULT-RX-GOODPUT-GBPS-PKTGEN " .. (rate.mbits_rx // 1000) .. "")

pktgen.screen("off")
prints("portStats", pktgen.portStats("all", "port"))

local port_stats = pktgen.pktStats(0)
-- // 1 floors the result
print(
        "RESULT-tx_p" ..
            sendport .. "_b2b_latency_us_min " .. math.floor(port_stats[sendport].latency.min_us) .. " us\n"
    )
print(
        "RESULT-tx_p" ..
            sendport .. "_b2b_latency_us_avg " .. math.floor(port_stats[sendport].latency.avg_us) .. " us\n"
    )
print(
        "RESULT-tx_p" ..
            sendport .. "_b2b_latency_us_max " .. math.floor(port_stats[sendport].latency.max_us) .. " us\n"
    )
print(
        "RESULT-tx_p" ..
            sendport .. "_b2b_latency_cycles_min " .. math.floor(port_stats[sendport].latency.min_cycles) .. " cycles\n"
    )
print(
        "RESULT-tx_p" ..
            sendport .. "_b2b_latency_cycles_avg " .. math.floor(port_stats[sendport].latency.avg_cycles) .. " cycles\n"
    )
print(
        "RESULT-tx_p" ..
            sendport .. "_b2b_latency_cycles_max " .. math.floor(port_stats[sendport].latency.max_cycles) .. " cycles\n"
    )




pktgen.quit()

