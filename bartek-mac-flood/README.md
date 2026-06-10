# Bartek — MAC Spoofing + Association Hijacking

**CVE-2022-47522** | AirSnitch Port Stealing | MacStealer  
Środowisko: Kali Linux VM · Mininet-wifi · Scapy · hostapd · Wireshark

---

## Atak

Ominięcie izolacji klientów Wi-Fi (Client Isolation / AP Isolation) przez podmianę adresu MAC i ponowną asocjację z Access Pointem.

Standard 802.11 rozdziela autentykację (hasło/certyfikat) od rutowania (adres MAC). AP nie weryfikuje, czy klient łączący się z danym MAC-em to ta sama osoba co poprzednio. Atakujący loguje się swoimi danymi, ale z MAC-em ofiary — AP kieruje ruch ofiary do atakującego.

## Wyniki

- Baseline: `sta1 → sta2` — 100% packet loss (izolacja działa)
- Po ataku: tcpdump na sta2 przechwytuje pakiety `h1 → sta1` (ICMP echo request)
- Dowód: PCAP z 10 przechwyconymipakami dla IP ofiary

## Pliki

| Plik | Opis |
|------|------|
| `topology.py` | Topologia Mininet-wifi: 1 AP (WPA2, client_isolation=True) + sta1 + sta2 + h1 |
| `demo.py` | Demo z przerwami na Enter, komentarze techniczne, auto-generuje ruch z h1 |
| `attack.py` | Pełny skrypt ataku, tryb `--demo` z pauzami |
| `baseline_test.sh` | Automatyczny test izolacji przed atakiem |
| `MAC-Spoofing-Association-Hijacking.md` | Dokumentacja: mechanizm, przebieg, wyniki, mitigacje |
| `PLAN-ATAKU.md` | Plan realizacji i opis kroków ataku |
| `captures/` | Pliki PCAP (generowane na VM, ignorowane przez git) |
| `logs/` | Logi z przebiegiem ataku (generowane na VM, ignorowane przez git) |

## Uruchomienie

```bash
# 1. Wyczyść poprzednią sesję i załaduj moduł wirtualnych kart wifi
sudo mn -c
sudo modprobe mac80211_hwsim radios=4

# 2. Uruchom topologię
sudo python3 /home/kali/bbsk-projekt/topology.py

# 3. Napraw OVS bridge (w CLI mininet-wifi)
mininet-wifi> sh ovs-vsctl del-port ap1 ap1-wlan2
mininet-wifi> sh ovs-vsctl del-port ap1 h1-eth0
mininet-wifi> sh ovs-vsctl add-port ap1 ap1-wlan1

# 4. Potwierdź baseline (izolacja blokuje sta1↔sta2)
mininet-wifi> sta1 ping -c 3 10.0.0.2     # powinno failować
mininet-wifi> sta1 ping -c 3 10.0.0.100   # powinno działać

# 5. Uruchom demo ataku
mininet-wifi> sta2 python3 /home/kali/bbsk-projekt/demo.py
```

## Kroki ataku (demo.py)

1. Odczyt MAC ofiary z `/tmp/bbsk_config.txt`
2. Baseline ping — potwierdzenie że izolacja działa
3. Wysłanie 10 ramek 802.11 Deauthentication (Scapy, reason=3)
4. `ip link set sta2-wlan0 address <MAC_OFIARY>` — podmiana MAC
5. `wpa_cli -i sta2-wlan0 reassociate` — asocjacja z AP z MAC ofiary
6. Sniff — przechwycenie pakietów `h1 → 10.0.0.1` na interfejsie atakującego

## Literatura

- CVE-2022-47522: https://www.cvedetails.com/cve/CVE-2022-47522/
- MacStealer: https://github.com/vanhoefm/macstealer
- AirSnitch (NDSS 2024): https://www.ndss-symposium.org/ndss-paper/airsnitch-demystifying-and-breaking-client-isolation-in-wi-fi-networks/
- Framing Frames (USENIX '23): https://papers.mathyvanhoef.com/usenix2023-wifi.pdf
