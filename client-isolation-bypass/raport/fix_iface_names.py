#!/usr/bin/env python3
"""poprawia nazwy interfejsow w skryptach testowych: sta1-wlan0 -> wlan0 wewnatrz namespace Mininet"""
import glob, re

files = [
    "pmf-bypass-lab-infra/baseline/test_pmf.py",
    "pmf-bypass-lab-infra/baseline/test_isolation.py",
]

for fpath in files:
    with open(fpath, 'r') as f:
        content = f.read()
    
    # zamien {sta.name}-wlan0 -> wlan0 w f-stringach
    original = content
    content = re.sub(r'\{(\w+)\.name\}-wlan0', r'wlan0', content)
    
    if content != original:
        with open(fpath, 'w') as f:
            f.write(content)
        print(f"Fixed: {fpath}")
    else:
        print(f"No changes: {fpath}")
