#!/usr/bin/env python3
"""test parametrow pmf w Mininet-WiFi AP"""
from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info
import time

setLogLevel("info")

net = Mininet_wifi()

# proba przekazania pmf przez parametr config Mininet-WiFi
ap1 = net.addAccessPoint(
    "ap1",
    ssid="PMF_Lab_Secure",
    mode="g",
    channel="6",
    failMode="standalone",
    config="ieee80211w=1",  # pmf opcjonalny (pozwala na klienty pmf i non-pmf)
    passwd="LabTest123!",
    encrypt="wpa2",
)

sta1 = net.addStation(
    "sta1",
    passwd="LabTest123!",
    encrypt="wpa2",
    ieee80211w="1",  # pmf opcjonalny
)

net.setPropagationModel(model="logDistance", exp=3.5)
net.configureNodes()
net.addLink(ap1, sta1)
net.start()
time.sleep(15)

info("STA link: " + sta1.cmd("iw dev wlan0 link") + "\n")
info("STA IP: " + str(sta1.IP()) + "\n")

# sprawdz pmf po stronie stacji
info("STA iw info: " + sta1.cmd("iw dev wlan0 info 2>&1 | head -5") + "\n")

net.stop()
