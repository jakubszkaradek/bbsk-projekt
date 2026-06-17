#!/usr/bin/env python3
"""sprawdza czy hostapd config jest generowany i dlaczego hostapd nie startuje"""
from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info
import time, os

setLogLevel("info")

net = Mininet_wifi()
ap1 = net.addAccessPoint("ap1", ssid="TestCSA", mode="g", channel="6", failMode="standalone")
sta1 = net.addStation("sta1")
net.setPropagationModel(model="logDistance", exp=3.5)

info("=== BEFORE configureNodes ===\n")
info(f"AP class: {type(ap1).__name__}\n")
info(f"AP failMode: {ap1.failMode if hasattr(ap1, 'failMode') else 'N/A'}\n")

net.configureNodes()

info("=== AFTER configureNodes ===\n")
import subprocess
result = subprocess.run(["find", "/tmp", "-name", "*apconf", "-o", "-name", "*staconf"], 
                       capture_output=True, text=True)
info(f"Config files in /tmp: {result.stdout}\n")

net.addLink(ap1, sta1)
net.start()
time.sleep(5)

info("=== AFTER start ===\n")
result = subprocess.run(["find", "/tmp", "-name", "*apconf", "-o", "-name", "*staconf"], 
                       capture_output=True, text=True)
info(f"Config files in /tmp: {result.stdout}\n")

info("hostapd running: " + ap1.cmd("ps aux | grep hostap | grep -v grep || echo NOT_FOUND") + "\n")
info("AP iw dev: " + ap1.cmd("iw dev 2>&1 | head -10") + "\n")

net.stop()
