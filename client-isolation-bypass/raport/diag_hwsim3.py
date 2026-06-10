#!/usr/bin/env python3
"""Diag #3: longer wait, scan test, log to files."""
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
ap_if, sta_if = ifaces[0], ifaces[1]
print(f"AP={ap_if} STA={sta_if}")

print("\n=== 2. Start hostapd ===")
sudo("pkill -f hostapd 2>/dev/null || true")
time.sleep(0.5)
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
with open("/tmp/hostapd_diag.conf", "w") as f: f.write(conf)
hp = subprocess.Popen(f"sudo hostapd /tmp/hostapd_diag.conf 2>/tmp/hostapd_diag.log",
                      shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(3)
print(f"hostapd PID={hp.pid}, rc={hp.poll()}")

print("\n=== 3. Scan from STA ===")
out, _, _ = sudo(f"iw dev {sta_if} scan 2>&1 | head -30", timeout=15)
print(out[:500])

print("\n=== 4. Start wpa_supplicant (log to file) ===")
sudo("pkill -f wpa_supplicant 2>/dev/null || true")
time.sleep(0.5)
wpaconf = f"""ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=PL
network={{
    ssid="TestCSA_Diag"
    psk="TestPass123"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=2
}}
"""
with open("/tmp/wpa_diag.conf", "w") as f: f.write(wpaconf)
wp = subprocess.Popen(
    f"sudo wpa_supplicant -i {sta_if} -c /tmp/wpa_diag.conf -D nl80211 2>/tmp/wpa_diag.log",
    shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
)
time.sleep(3)
print(f"wpa_supplicant PID={wp.pid}, rc={wp.poll()}")

print("\n=== 5. Wait for association (up to 15s) ===")
deadline = time.time() + 15
while time.time() < deadline:
    out, _, _ = sudo(f"iw dev {sta_if} link")
    if "Connected to" in out:
        print(f"ASSOCIATED: {out[:200]}")
        break
    time.sleep(1)
else:
    out, _, _ = sudo(f"iw dev {sta_if} link")
    print(f"TIMEOUT: {out[:200]}")

print("\n=== 6. wpa_supplicant log (last 30 lines) ===")
run("tail -30 /tmp/wpa_diag.log 2>/dev/null || echo 'no log'")

print("\n=== 7. hostapd log (last 20 lines) ===")
run("tail -20 /tmp/hostapd_diag.log 2>/dev/null || echo 'no log'")

print("\n=== 8. Cleanup ===")
hp.terminate()
wp.terminate()
time.sleep(1)
sudo("pkill -f hostapd 2>/dev/null || true")
sudo("pkill -f wpa_supplicant 2>/dev/null || true")
sudo("modprobe -r mac80211_hwsim 2>/dev/null || true")
print("Done")