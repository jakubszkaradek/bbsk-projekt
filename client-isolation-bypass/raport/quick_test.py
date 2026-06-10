#!/bin/bash
# Quick test wrapper for full_exploit.py
cd /mnt/hgfs/raport
echo "=== Testing syntax ==="
python3 -c "import ast; ast.parse(open('full_exploit.py').read()); print('Syntax OK')"
echo "=== Running exploit (no wmediumd) ==="
python3 full_exploit.py --hostapd-ver 2.6 --pmf 2 --no-wmediumd 2>&1
echo "EXIT: $?"
