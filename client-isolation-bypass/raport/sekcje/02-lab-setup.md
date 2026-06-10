# 02 — Konfiguracja Laboratorium

**Data:** 26-27 maja 2026  

## 1. Topologia

```
┌──────────────────────────────────────────────┐
│              Kali Linux VM                    │
│  ┌────────────────────────────────────────┐  │
│  │         Mininet-WiFi 2.7                │  │
│  │                                        │  │
│  │   AP1 (hostapd) ─── sta1 (klient)      │  │
│  │   SSID: PMF_Lab_Secure                 │  │
│  │   Kanał: 6, WPA2-PSK, CCMP              │  │
│  │   PMF: required (ieee80211w=2)          │  │
│  │   Client Isolation: enabled             │  │
│  │                                        │  │
│  │   AP1 ─── sta2                         │  │
│  │   AP1 ─── sta3                         │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  WIDS: scapy_sniffer.py + Kismet             │
│  Analiza: Wireshark                          │
└──────────────────────────────────────────────┘
```

## 2. Konfiguracja AP (hostapd.conf)

```ini
interface=ap1-wlan1
driver=nl80211
ssid=PMF_Lab_Secure
hw_mode=g
channel=6
wpa=2
wpa_passphrase=LabTest123!
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=2          # PMF required
ap_isolate=1           # Client Isolation
max_num_sta=10
```

## 3. Konfiguracja stacji (wpa_supplicant.conf)

```ini
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=PL

network={
    ssid="PMF_Lab_Secure"
    psk="LabTest123!"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=2        # PMF required
}
```

## 4. Proces uruchomienia laboratorium

```bash
# 1. Załadowanie modułu wirtualnych interfejsów WiFi
sudo modprobe mac80211_hwsim radios=4

# 2. Uruchomienie topologii
sudo python3 topology/lab_topology.py --cli

# 3. Weryfikacja połączenia stacji
mininet-wifi> sta1 iw dev wlan0 link
```

## 5. Weryfikacja środowiska

Przed rozpoczęciem testów zweryfikowano:
- [x] 4 wirtualne interfejsy radiowe (wlan0-wlan3)
- [x] Open vSwitch aktywny
- [x] Python 3.13.12 + Scapy 2.7.01
- [x] Mininet-WiFi 2.7 zaimportowane poprawnie
- [x] hostapd v2.10 (systemowy) + v2.6 (zbudowany ze źródła)

---

**[✗ SCREENSHOT: Terminal — output polecenia `iw dev` pokazujący 4 interfejsy wlan0-wlan3]**  
**[✗ SCREENSHOT: Terminal — uruchomienie topologii Mininet-WiFi]**  
**[✗ SCREENSHOT: Wireshark — Beacon frame z SSID "PMF_Lab_Secure" i RSN IE z PMF capabilities]**
