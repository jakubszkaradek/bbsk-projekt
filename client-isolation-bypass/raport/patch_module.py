#!/usr/bin/env python3
"""latka na Mininet-WiFi link.py naprawiajaca wintfs[0].mac=None"""
import re

path = '/opt/mininet-wifi/mn_wifi/link.py'
with open(path, 'r') as f:
    content = f.read()

old = 'if not intf.mac:\n                    intf.mac = node.wintfs[0].mac[:-1] + str(id)'
new = '''if not intf.mac:
                    try:
                        base = node.wintfs[0].mac
                        if base is None:
                            raise AttributeError('mac is None')
                        intf.mac = base[:-1] + str(id)
                    except (TypeError, AttributeError):
                        r = node.cmd('iw dev 2>&1')
                        m = re.search(r'addr ([0-9a-f:]+)', r)
                        base_mac = m.group(1) if m else '02:00:00:00:00:00'
                        intf.mac = base_mac[:-1] + str(id)'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('PATCHED link.py - wintfs[0].mac fallback added')
else:
    print('ALREADY PATCHED or pattern not found')
    # sprawdz co tam jest
    idx = content.find('if not intf.mac')
    if idx >= 0:
        print('Found at offset', idx)
        print(content[idx:idx+200])
