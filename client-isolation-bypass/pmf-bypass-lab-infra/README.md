# PMF Bypass Lab Infrastructure

Wspolna infrastruktura laboratoryjna do testowania bezpieczenstwa Wi-Fi w izolowanym srodowisku VMware (Kali Linux).

**Cel:** dostarczyc konfigurowalne srodowisko z Mininet-WiFi, hostapd (PMF + Client Isolation), Scapy, Kismet i Wireshark dla zespolu realizujacego projekt akademicki z zakresu pentestingu sieci bezprzewodowych.

## Architektura

```
pmf-bypass-lab-infra/
├── topology/               # Skrypty topologii Mininet-WiFi
│   └── lab_topology.py     # 1 AP + 3 stacje, PMF=required, Client Isolation
├── configs/                # Konfiguracje AP i klientow
│   ├── hostapd.conf        # PMF (ieee80211w=2), ap_isolate=1
│   └── wpa_supplicant.conf # WPA2-PSK + PMF=required
├── baseline/               # Testy weryfikujace baseline security
│   ├── test_isolation.py   # Sprawdza Client Isolation (L2 block)
│   ├── test_pmf.py         # Sprawdza ochrone PMF (deauth rejection)
│   └── test_csa.py         # Sprawdza ochrone CSA Action Frames
├── wids/                   # Wireless Intrusion Detection System
│   ├── scapy_sniffer.py    # Precyzyjny sniffer ramek zarzadzajacych
│   └── kismet.conf         # Konfiguracja Kismet jako WIDS
├── setup/                  # Skrypty instalacyjne
│   ├── install.sh          # Instalacja wszystkich zaleznosci
│   └── ssh_setup.sh        # Konfiguracja SSH dla agentow AI
├── docs/
│   └── PMF_ANALYSIS.md     # Analiza teoretyczna 802.11w/PMF
└── README.md               # Ten plik
```

## Wymagania

- Kali Linux (VMware) — lub Debian-based distro z dostepem do Kali repos
- Python 3.8+
- 4 GB RAM minimum (dla Mininet-WiFi + Kismet)
- Kernel z modulem `mac80211_hwsim`

## Agent AI na VM

Pełna instrukcja + master prompt: [docs/LAB_VM_AGENT.md](docs/LAB_VM_AGENT.md)

```powershell
# Windows — test połączenia
ssh kali-lab "cd ~/pmf-bypass-lab-infra && ls baseline"
```

## Szybki start

### 1. Instalacja srodowiska

```bash
cd pmf-bypass-lab-infra
chmod +x setup/install.sh setup/ssh_setup.sh
sudo ./setup/install.sh
```

### 2. Konfiguracja SSH dla agentow AI (opcjonalne)

```bash
sudo ./setup/ssh_setup.sh
```

Po wykonaniu:
- Skopiuj klucz prywatny do maszyny agenta
- W VMware skonfiguruj NAT Port Forwarding: Host:2222 → VM:22
- Test: `ssh -i klucz -p 2222 agent@localhost`

### 3. Uruchomienie topologii

```bash
# Tryb interaktywny (CLI Mininet)
sudo python3 topology/lab_topology.py --cli

# Z Kismet w tle
sudo python3 topology/lab_topology.py --cli --kismet
```

W CLI Mininet:
```
mininet-wifi> nodes        # Lista wezlow
mininet-wifi> sta1 ping sta2  # Test (powinien FAIL z izolacja)
mininet-wifi> py sta1.cmd('iw dev sta1-wlan0 link')  # Status polaczenia
```

### 4. Uruchomienie testow bazowych

```bash
# Test izolacji klientow (powinien PASS)
sudo python3 baseline/test_isolation.py

# Test PMF — deauth spoofing (powinien PASS)
sudo python3 baseline/test_pmf.py

# Test CSA — ochrona Action Frames (analiza)
sudo python3 baseline/test_csa.py
```

### 5. Sniffer ramek zarzadzajacych

```bash
# Przechwytywanie ramek na interfejsie monitora AP
sudo python3 wids/scapy_sniffer.py --iface ap1-mp1 --duration 120 --out captured.pcap

# Analiza w Wireshark
wireshark captured.pcap &
```

## Workflow dla zespolu

### Kuba (PMF Bypass)

1. Uruchom topologie: `sudo python3 topology/lab_topology.py --cli`
2. Przeprowadz baseline testy dla potwierdzenia dzialania PMF
3. W docelowym repo `pmf-bypass-kuba/` implementuj analize atakow na ramki zarzadzania

### Kamil (AirSnitch)

1. Uruchom topologie z izolacja klientow
2. W repo `airsnitch-kamil/` implementuj analize omijania Client Isolation

### Bartek (MAC Flood)

1. Uruchom topologie, zweryfikuj limity polaczen (max_num_sta)
2. Uwaga: Mininet-WiFi/CPU moze nie wytrzymac setek klientow — rozwaz NS3

## Granice odpowiedzialnosci

To repozytorium zawiera wylacznie:
- Konfiguracje i skrypty do postawienia srodowiska laboratoryjnego
- Testy bazowe weryfikujace dzialanie mechanizmow bezpieczenstwa
- Narzedzia obserwacyjne (sniffer, WIDS)
- Analize teoretyczna PMF/802.11w

**Nie zawiera** kodu eksploitow, wektorow ataku ani narzedzi ofensywnych.
Implementacja atakow (PMF Bypass, AirSnitch, MAC flood) nalezy do
poszczegolnych czlonkow zespolu w ich wlasnych repozytoriach.

## Powiazane repozytoria

| Repozytorium | Odpowiedzialny | Zakres |
|-------------|---------------|--------|
| `pmf-bypass-lab-infra` | Wspolne | Infrastruktura, baseline testy, WIDS |
| `pmf-bypass-kuba` | Kuba | Atak PMF (deauth/CSA bypass) |
| `airsnitch-kamil` | Kamil | Atak AirSnitch (Client Isolation bypass) |
| `mac-flood-bartek` | Bartek | Atak MAC flood / DoS |
