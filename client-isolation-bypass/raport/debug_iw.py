#!/usr/bin/env python3
"""test: sprawdza czy stacja widzi ap i moze probowac asocjacji"""
from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info
import time

setLogLevel("info")

net = Mininet_wifi()
ap1 = net.addAccessPoint("ap1", ssid="TestCSA", mode="g", channel="6", failMode="standalone")
sta1 = net.addStation("sta1")
net.setPropagationModel(model="logDistance", exp=3.5)
net.configureNodes()
net.addLink(ap1, sta1)
net.start()
time.sleep(5)

info("=== STA scan ===\n")
info(sta1.cmd("iw dev wlan0 scan 2>&1 | grep -E 'SSID|freq|signal' | head -10") + "\n")

info("=== STA iw link ===\n")
info(sta1.cmd("iw dev wlan0 link") + "\n")

info("=== STA connect attempt ===\n")
sta1.cmd("iw dev wlan0 connect TestCSA 2>&1")
time.sleep(3)
info("=== STA iw link after connect ===\n")
info(sta1.cmd("iw dev wlan0 link") + "\n")

info("=== STA get channel ===\n")
info(sta1.cmd("iw dev wlan0 info 2>&1 | grep -E 'channel|ssid|type'") + "\n")

net.stop()
