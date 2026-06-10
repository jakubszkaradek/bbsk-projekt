#!/bin/bash
# Phase 2: Source Code Analysis
# Determine if module-only patch is viable by examining nl80211.c

echo "=== PHASE 2: SOURCE CODE ANALYSIS ==="

KVER=$(uname -r)
echo "Kernel: $KVER"

# Check if kernel source already exists
if [ -d "/usr/src/linux-source-*" ] || [ -d "/root/linux-*" ] || [ -f "/boot/config-${KVER}" ]; then
    echo "Kernel config exists, checking for source..."
fi

# Get kernel source
echo ""
echo "[1] Getting kernel source..."
cd /tmp
if [ -d "linux-source-analysis" ]; then
    echo "  Source already extracted, reusing..."
else
    echo "  Installing linux-source package..."
    apt-get install -y linux-source-6.19 2>/dev/null || apt-get install -y linux-source 2>/dev/null || true
    
    if [ -f "/usr/src/linux-source-6.19.tar.xz" ]; then
        echo "  Extracting source..."
        mkdir -p /tmp/linux-source-analysis
        tar xf /usr/src/linux-source-6.19.tar.xz -C /tmp/linux-source-analysis/ 2>/dev/null &
        PID=$!
        # Wait up to 30s
        for i in $(seq 1 30); do
            if ! kill -0 $PID 2>/dev/null; then break; fi
            sleep 1
        done
        wait $PID 2>/dev/null
    fi
fi

# Find the actual source directory
SRCDIR=$(find /tmp/linux-source-analysis -name "nl80211.c" -path "*/net/wireless/*" 2>/dev/null | head -1 | xargs dirname)
if [ -z "$SRCDIR" ]; then
    echo "  WARNING: No extracted source found. Trying apt source..."
    cd /tmp
    rm -rf linux-*
    apt-get source linux-image-${KVER} 2>&1 | tail -3
    SRCDIR=$(find /tmp/linux-* -name "nl80211.c" -path "*/net/wireless/*" 2>/dev/null | head -1 | xargs dirname)
fi

if [ -z "$SRCDIR" ]; then
    echo "  ERROR: Could not find kernel source. Attempting to download from kernel.org..."
    # Fallback: use gitweb or similar
    echo "  This will need manual intervention."
    exit 1
fi

BASE=$(dirname $(dirname "$SRCDIR"))
echo "  Source found at: $BASE"

# === CRITICAL ANALYSIS ===

echo ""
echo "[2] === nl80211_channel_switch() analysis ==="
echo "    Searching for CERTIFICATION_ONUS in nl80211.c..."
grep -n "CERTIFICATION_ONUS\|certification_onus" $SRCDIR/nl80211.c | head -20

echo ""
echo "    Searching for NL80211_CMD_CHANNEL_SWITCH handler..."
grep -n "NL80211_CMD_CHANNEL_SWITCH\|nl80211_channel_switch\|nl80211_switch_channel\|CHANNEL_SWITCH" $SRCDIR/nl80211.c | head -20

echo ""
echo "    Searching for EOPNOTSUPP near channel switch code..."
grep -n -B3 -A3 "EOPNOTSUPP\|OPNOTSUPP" $SRCDIR/nl80211.c | grep -B3 -A3 -i "switch\|channel" | head -30

echo ""
echo "[3] === Checking for iftype restriction ==="
echo "    Searching for NL80211_IFTYPE_STATION near channel switch..."
grep -n -B5 -A5 "IFTYPE\|iftype" $SRCDIR/nl80211.c | grep -B5 -A5 -i "channel\|switch" | head -30

echo ""
echo "[4] === mac80211_hwsim channel switch registration ==="
HW_SRC=$(find $BASE -name "mac80211_hwsim.c" -path "*/wireless/*" | head -1)
if [ -n "$HW_SRC" ]; then
    echo "  Found at: $HW_SRC"
    echo ""
    echo "  --- Channel switch interface types ---"
    grep -n -B5 -A5 "NL80211_IFTYPE\|channel_switch\|ch_switch\|CHANNEL_SWITCH\|wiphy.*iface_combinations\|can_channel_switch" $HW_SRC | head -40
    
    echo ""
    echo "  --- hwsim wiphy registration ---"
    grep -n "wiphy->\|hw->wiphy" $HW_SRC | grep -i "feature\|iface\|channel\|switch\|flag" | head -20
fi

echo ""
echo "[5] === cfg80211 helper functions ==="
CFG_DIR=$(dirname "$SRCDIR")
echo "  Searching for cfg80211_is_allowed or similar gating functions..."
grep -rn "certification_onus\|CERTIFICATION_ONUS\|is_allowed.*channel\|cfg80211_reg_can_beacon" $CFG_DIR/ --include="*.c" --include="*.h" | head -30

echo ""
echo "[6] === Config check ==="
grep "CERTIFICATION_ONUS" /boot/config-${KVER}

echo ""
echo "=== PHASE 2 COMPLETE ==="
echo ""
echo "Decision needed: check the above output to determine if module-only patch is viable."
