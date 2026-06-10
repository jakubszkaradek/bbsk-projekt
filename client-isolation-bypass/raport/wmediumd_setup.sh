#!/bin/bash
# Generate wmediumd config for hwsim interfaces and start it

echo "=== wmediumd setup ==="

# Get all wlan interfaces and their MACs
echo "Loading hwsim..."
modprobe mac80211_hwsim radios=4 2>/dev/null
sleep 2

echo "Interfaces:"
IFACE_COUNT=0
declare -a IFACES
declare -a MACS

for iface in wlan0 wlan1 wlan2 wlan3; do
    if [ -d "/sys/class/net/$iface" ]; then
        MAC=$(ip -c=never link show $iface | grep -oP 'link/ether \K[0-9a-f:]+')
        echo "  $iface: $MAC"
        IFACES+=("$iface")
        MACS+=("$MAC")
        IFACE_COUNT=$((IFACE_COUNT + 1))
    fi
done

if [ $IFACE_COUNT -lt 2 ]; then
    echo "ERROR: Need at least 2 hwsim interfaces"
    exit 1
fi

# Create wmediumd config
cat > /tmp/wmediumd.cfg << EOF
ifaces : {
	ids = [
		"${MACS[0]}",
		"${MACS[1]}",
		"${MACS[2]}",
		"${MACS[3]}"
	];
};

model_type: probabilistic
model_params : {
	# Simulate SNR-based probability
	default_prob = 1.0;
};
EOF

echo ""
echo "Config written to /tmp/wmediumd.cfg"
cat /tmp/wmediumd.cfg

# Start wmediumd
echo ""
echo "Starting wmediumd..."
pkill wmediumd 2>/dev/null || true
sleep 0.5

wmediumd -c /tmp/wmediumd.cfg -l 3 &
WMEDIUM_PID=$!
sleep 1

if kill -0 $WMEDIUM_PID 2>/dev/null; then
    echo "wmediumd running (PID=$WMEDIUM_PID)"
else
    echo "ERROR: wmediumd failed to start"
    exit 1
fi

echo "=== wmediumd setup DONE ==="
