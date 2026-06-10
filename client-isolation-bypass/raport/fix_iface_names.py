#!/usr/bin/env python3
"""Fix interface names in all test scripts: sta1-wlan0 → wlan0 inside Mininet namespaces."""
import glob, re

files = [
    "pmf-bypass-lab-infra/baseline/test_pmf.py",
    "pmf-bypass-lab-infra/baseline/test_isolation.py",
]

for fpath in files:
    with open(fpath, 'r') as f:
        content = f.read()
    
    # Replace {sta.name}-wlan0 → wlan0 in f-strings
    # Pattern: {something.name}-wlan0
    original = content
    content = re.sub(r'\{(\w+)\.name\}-wlan0', r'wlan0', content)
    
    if content != original:
        with open(fpath, 'w') as f:
            f.write(content)
        print(f"Fixed: {fpath}")
    else:
        print(f"No changes: {fpath}")
