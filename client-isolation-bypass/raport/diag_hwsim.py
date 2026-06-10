#!/usr/bin/env python3
"""Debug: check Mininet-WiFi station wpa_supplicant behavior."""
from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info
import time, os

setLogLevel("info")

net = Mininet_wifi()

ap1 = net.addAccessPoint(
    "ap1", ssid="PMF_Lab_Secure", mode="g", channel="6",
    failMode="standalone", config="ieee80211w=1",
    passwd="LabTest123!", encrypt="wpa2",
)
sta1 = net.addStation(
    "sta1", passwd="LabTest123!", encrypt="wpa2", ieee80211w="1",
)

net.setPropagationModel(model="logDistance", exp=3.5)
net.configureNodes()
net.addLink(ap1, sta1)
net.start()
time.sleep(10)

# Check what's running in the station namespace
info("=== HOSTAPD AP-side ===\n")
info(ap1.cmd("ps aux | grep hostap | grep -v grep") + "\n")

info("=== WPA_SUPPLICANT STA-side (in namespace) ===\n")
info(sta1.cmd("ps aux | grep wpa | grep -v grep") + "\n")

info("=== STA wpa_supplicant.conf (Mininet generated) ===\n")
info(sta1.cmd("cat /tmp/mn*_sta1*.conf 2>/dev/null; cat /tmp/mn*sta1*.conf 2>/dev/null") + "\n")

info("=== STA link ===\n")
info(sta1.cmd("iw dev wlan0 link") + "\n")

info("=== STA scan (should see AP) ===\n")
info(sta1.cmd("iw dev wlan0 scan 2>&1 | grep -E 'SSID|signal|freq' | head -10") + "\n")

info("=== AP hostapd config ===\n")
info(ap1.cmd("cat /tmp/mn*ap1*.apconf 2>/dev/null") + "\n")

net.stop()
