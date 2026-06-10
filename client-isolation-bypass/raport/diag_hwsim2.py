#!/usr/bin/env python3
"""Quick diagnostic: test hostapd + wpa_supplicant directly on hwsim without mininet."""
import subprocess, time, sys, os

def run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def sudo(cmd, timeout=10):
    return run(f"sudo {cmd}", timeout=timeout)

print("=== 1. Load hwsim ===")
sudo("modprobe -r mac80211_hwsim 2>/dev/null || true")
time.sleep(1)
sudo("modprobe mac80211_hwsim radios=4")
time.sleep(2)
out, _, _ = sudo("iw dev 2>&1")
ifaces = [l.split()[1] for l in out.split("\n") if l.strip().startswith("Interface ")]
print(f"Interfaces: {ifaces}")

# Ensure we have enough
if len(ifaces) < 3:
    print("ERROR: need >= 3 interfaces")
    sys.exit(1)

ap_if = ifaces[0]
sta_if = ifaces[1]
inj_if = ifaces[2]
print(f"AP={ap_if} STA={sta_if} INJ={inj_if}")

print("\n=== 2. Write hostapd config ===")
conf = f"""interface={ap_if}
driver=nl80211
ssid=TestCSA_Diag
hw_mode=g
channel=6
wpa=2
wpa_passphrase=TestPass123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=2
beacon_int=100
ctrl_interface=/var/run/hostapd
logger_stdout=-1
logger_stdout_level=2
"""
with open("/tmp/hostapd_diag.conf", "w") as f:
    f.write(conf)
print("Config written")

print("\n=== 3. Start hostapd (background, log to file) ===")
sudo(f"pkill -f hostapd 2>/dev/null || true")
time.sleep(0.5)
# Run hostapd in background, capture output
import subprocess as sp
hp = sp.Popen(f"sudo hostapd /tmp/hostapd_diag.conf", shell=True,
              stdout=sp.PIPE, stderr=sp.STDOUT, text=True)
time.sleep(3)

# Check if running
rc = hp.poll()
if rc is not None:
    out = hp.stdout.read()
    print(f"hostapd EXITED with code {rc}")
    print(f"Output: {out[:500]}")
else:
    print(f"hostapd RUNNING (PID={hp.pid})")

print("\n=== 4. Check AP interface ===")
out, _, _ = sudo(f"iw dev {ap_if} info")
for l in out.split("\n"):
    l = l.strip()
    if any(k in l for k in ["Interface", "type", "channel", "ssid"]):
        print(f"  {l}")

print("\n=== 5. Write wpa_supplicant config ===")
wpaconf = """ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=PL
network={
    ssid="TestCSA_Diag"
    psk="TestPass123"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=2
}
"""
with open("/tmp/wpa_diag.conf", "w") as f:
    f.write(wpaconf)

print("\n=== 6. Start wpa_supplicant ===")
sudo(f"pkill -f wpa_supplicant 2>/dev/null || true")
time.sleep(0.5)

wp = sp.Popen(
    f"sudo wpa_supplicant -i {sta_if} -c /tmp/wpa_diag.conf -D nl80211 -d 2>&1",
    shell=True, stdout=sp.PIPE, stderr=sp.STDOUT, text=True
)
time.sleep(5)

print("\n=== 7. Check association ===")
out, _, _ = sudo(f"iw dev {sta_if} link")
print(f"iw link: {out[:300]}")

out, _, _ = sudo(f"iw dev {sta_if} info")
for l in out.split("\n"):
    l = l.strip()
    if any(k in l for k in ["Interface", "type", "channel", "ssid"]):
        print(f"  {l}")

# Kill processes
print("\n=== 8. Cleanup ===")
hp.terminate()
wp.terminate()
time.sleep(1)
sudo("pkill -f hostapd 2>/dev/null || true")
sudo("pkill -f wpa_supplicant 2>/dev/null || true")
sudo("modprobe -r mac80211_hwsim 2>/dev/null || true")
print("Done.")