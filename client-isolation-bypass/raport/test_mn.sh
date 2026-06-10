#!/usr/bin/env python3
"""Test minimal wmediumd config."""
import subprocess, re, time

subprocess.run(["sudo", "modprobe", "mac80211_hwsim", "radios=4"], capture_output=True)
time.sleep(1)

ifaces = ["wlan0", "wlan1", "wlan2", "wlan3"]
ids = []
for i in ifaces:
    r = subprocess.run(["ip", "-c=never", "link", "show", i], capture_output=True, text=True)
    m = re.search(r'link/ether ([0-9a-f:]+)', r.stdout)
    ids.append(m.group(1) if m else "02:00:00:00:00:01")

# Try different config formats
configs = [
    # Format 1: Minimal
    f'ifaces : {{\n    ids = [\n{",\n".join(f"        \"{m}\"" for m in ids)}\n    ];\n}};\n',
    # Format 2: with model
    f'ifaces : {{\n    ids = [\n{",\n".join(f"        \"{m}\"" for m in ids)}\n    ];\n}};\nmodel_type = "probabilistic";\n',
    # Format 3: equals instead of colon
    f'ifaces = {{\n    ids = [\n{",\n".join(f"        \"{m}\"" for m in ids)}\n    ];\n}};\n',
]

for idx, cfg in enumerate(configs):
    path = f"/tmp/wmt_{idx}.cfg"
    with open(path, "w") as f:
        f.write(cfg)
    print(f"--- Config {idx} ({path}) ---")
    print(cfg[:150])
    r = subprocess.run(["sudo", "/usr/bin/wmediumd", "-c", path, "-l", "3"],
                       capture_output=True, text=True, timeout=3)
    err = r.stderr.strip() or r.stdout.strip()
    if "Error" in err:
        print(f"  FAIL: {err[:120]}")
    else:
        print(f"  OK: {err[:120]}")

subprocess.run(["sudo", "modprobe", "-r", "mac80211_hwsim"], capture_output=True)
