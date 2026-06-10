# Handoff — Bartek / MAC Spoofing + Association Hijacking

Notatki dla przyszłych agentów AI lub dla Bartka wracającego do projektu.  
Sesja z: 2026-06-10

---

## Co zostało zrobione

Pełna implementacja ataku MAC Spoofing + Association Hijacking (CVE-2022-47522) na Kali Linux VM z Mininet-wifi.

1. Kali Linux VM skonfigurowana do zdalnego SSH z Windows
2. Mininet-wifi zainstalowane ręcznie (patchowanie install.sh dla Kali, patch FlightRadar24, mnexec skompilowany)
3. Topologia sieci napisana i uruchomiona (`topology.py`)
4. Atak zaimplementowany w `attack.py` i `demo.py`
5. Atak potwierdzony — tcpdump na sta2 przechwycił pakiety adresowane do sta1 mimo włączonej izolacji klientów
6. Dokumentacja: `MAC-Spoofing-Association-Hijacking.md`, `PLAN-ATAKU.md`

---

## Środowisko

### Kali Linux VM

- Host: Windows 10, VirtualBox
- IP (sieć wewnętrzna): `192.168.1.100` (eth0, Bridged)
- IP (docker bridge): `172.17.0.1` (docker0)
- Użytkownik: `kali` z `NOPASSWD` sudo (`/etc/sudoers.d/kali-nopasswd`)
- SSH: port 22, klucz w `/home/kali/.ssh/authorized_keys`

### SSH z Windows

```powershell
# Klucz prywatny:
# C:\Users\barte\.ssh\id_ed25519

ssh kali@192.168.1.100
```

### Pliki ataku na VM

Wszystkie pliki wgrane do: `/home/kali/bbsk-projekt/`

```
/home/kali/bbsk-projekt/
├── topology.py
├── demo.py
├── attack.py
├── baseline_test.sh
├── MAC-Spoofing-Association-Hijacking.md
├── PLAN-ATAKU.md
├── captures/           (pliki PCAP)
└── logs/               (logi z ataków)
```

---

## Jak uruchomić atak od zera

```bash
# 1. SSH na VM
ssh kali@192.168.1.100

# 2. Wyczyść poprzednią sesję
sudo mn -c

# 3. Załaduj moduł wirtualnych kart wifi
sudo modprobe mac80211_hwsim radios=4

# 4. Uruchom topologię (zostaniesz w CLI mininet-wifi)
sudo python3 /home/kali/bbsk-projekt/topology.py

# 5. W CLI mininet-wifi napraw OVS bridge
# (topologia próbuje to zrobić automatycznie, ale czasem trzeba ręcznie)
mininet-wifi> sh ovs-vsctl del-port ap1 ap1-wlan2
mininet-wifi> sh ovs-vsctl del-port ap1 h1-eth0
mininet-wifi> sh ovs-vsctl add-port ap1 ap1-wlan1

# 6. Sprawdź czy routing działa
mininet-wifi> sta1 ping -c 3 10.0.0.100   # powinno działać (h1)
mininet-wifi> sta1 ping -c 3 10.0.0.2     # powinno failować (izolacja)

# 7. Uruchom demo
mininet-wifi> sta2 python3 /home/kali/bbsk-projekt/demo.py
# demo zatrzymuje się po każdym kroku — kliknij Enter żeby kontynuować
```

---

## Znane problemy i fixes

### OVS bridge — błędne porty po uruchomieniu topology.py

Symptom: `sta1 ping -c 3 10.0.0.100` — Destination Host Unreachable  
Fix: ręczne komendy w CLI mininet-wifi (krok 5 powyżej)  
Przyczyna: Mininet-wifi dodaje `ap1-wlan2` i `h1-eth0` do bridgy, które nie istnieją w odpowiednim namespace.

### Mininet-wifi nie instaluje się przez install.sh na Kali

Użyta metoda: ręczna instalacja z APT + pip + klonowanie mininet ze źródeł.
Szczegóły w sesji agenta d8d9011b-3f05-42ea-a359-b04a16fbcf4a.

### FlightRadar24 import error

Patch w `/home/kali/mininet-wifi/mn_wifi/net.py`: import `FlightRadar24API` opakowany w `try/except`.

### brak mnexec

Fix: `cd ~/mininet && sudo make install`

### brak ovs-testcontroller / controller

Fix: `sudo apt install openvswitch-testcontroller && sudo ln -sf /usr/bin/ovs-testcontroller /usr/local/bin/controller`

---

## Sieć w topologii

| Node | IP | MAC |
|------|-----|-----|
| sta1 (ofiara) | 10.0.0.1 | 02:00:00:00:04:00 |
| sta2 (atakujący) | 10.0.0.2 | 02:00:00:00:05:00 |
| ap1 (AP) | — | 02:00:00:00:06:00 |
| h1 (serwer) | 10.0.0.100 | — |

SSID: `testnet`, hasło: `password123`, WPA2, PMF=disabled (ieee80211w=0), client_isolation=True

---

## Wyniki ataku (potwierdzone)

```
tcpdump -i sta2-wlan0 dst 10.0.0.1 -n -c 10
# po ataku:
13:37:22.147618 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, id 38491, seq 1, length 64
13:37:23.150442 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, id 38491, seq 2, length 64
...
10 packets captured
```

Pakiety adresowane do IP ofiary (10.0.0.1) trafiają na interfejs atakującego (sta2-wlan0) mimo włączonej izolacji.

---

## Pliki w repo

```
bbsk-projekt/
├── bartek-mac-flood/
│   ├── topology.py                         — Mininet-wifi topologia
│   ├── demo.py                             — demo z pauzami na Enter
│   ├── attack.py                           — pełny skrypt ataku
│   ├── baseline_test.sh                    — test izolacji
│   ├── MAC-Spoofing-Association-Hijacking.md — dokumentacja dla prowadzącego
│   ├── PLAN-ATAKU.md                       — wewnętrzny plan
│   ├── captures/.gitkeep
│   └── logs/.gitkeep
├── kamil-airsnitch/
│   └── README.md                           — placeholder dla Kamila
├── kuba-pmf-bypass/                        — praca Kuby (niezmieniona)
├── README.md
├── analiza-wnioski.md
└── handoff.md                              — ten plik
```

---

## Co jeszcze można zrobić (opcjonalne)

- Nagrać atak jako gif / asciinema do repo
- Dodać sekcję "Mitigacje" do prezentacji slajdów
- Kamil: uzupełnić `kamil-airsnitch/` własnymi skryptami i README
- Zebrać wspólną `analiza-wnioski.md` z wnioskami całego zespołu
