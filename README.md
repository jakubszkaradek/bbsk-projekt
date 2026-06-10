# BBSK Projekt — Ataki na sieci WiFi

Trzyosobowy projekt zaliczeniowy z przedmiotu BBSK.

## Zespół

| Osoba | Atak | Folder |
|-------|------|--------|
| **Kuba** | PMF Bypass (802.11w) przez Beacon CSA Injection | `kuba-pmf-bypass/` |
| **Kamil** | AirSnitch — Client Isolation bypass | `kamil-airsnitch/` |
| **Bartek** | MAC Spoofing + Association Hijacking (CVE-2022-47522) | `bartek-mac-flood/` |

## Infrastruktura współdzielona

Laboratorium działa na Kali Linux VM z Mininet-WiFi + mac80211_hwsim + hostapd + wpa_supplicant.

Folder `kuba-pmf-bypass/pmf-bypass-lab-infra/` zawiera współdzieloną infrastrukturę (topologia, testy bazowe, WIDS).

## Struktura repo

```
bbsk-projekt/
├── README.md
├── analiza-wnioski.md          # Wspólna analiza i wnioski
├── handoff.md                  # Notatki dla przyszłych sesji / agentów
├── .gitignore
├── prezentacja/                # Slajdy i materiały prezentacyjne
├── kuba-pmf-bypass/            # PMF Bypass przez Beacon CSA
│   ├── raport/                 # Pełny raport (sekcje 00-09)
│   ├── demo/                   # Skrypty demonstracyjne
│   └── pmf-bypass-lab-infra/   # Infrastruktura laboratoryjna
├── kamil-airsnitch/            # Client Isolation bypass (AirSnitch)
└── bartek-mac-flood/           # MAC Spoofing + Association Hijacking
    ├── topology.py             # Topologia Mininet-wifi
    ├── demo.py                 # Demo ataku krok po kroku
    ├── attack.py               # Pełny skrypt ataku
    ├── baseline_test.sh        # Test izolacji przed atakiem
    └── MAC-Spoofing-Association-Hijacking.md  # Dokumentacja
```

## Kluczowe wyniki

- **PMF (802.11w) NIE chroni przed Beacon CSA Injection** — Beacon (subtype 8) jest zawsze Non-Robust
- Atak Kuby działa na wszystkich testowanych wersjach hostapd (2.6, 2.10)
- **MAC Spoofing omija Client Isolation** — AP rutuje po MAC, nie po tożsamości kryptograficznej (CVE-2022-47522)
- Atak Bartka potwierdzony: tcpdump na sta2 przechwycił 10 pakietów adresowanych do ofiary mimo włączonej izolacji

---

## Bartek — MAC Spoofing + Association Hijacking

**CVE-2022-47522** | AirSnitch Port Stealing | MacStealer

### Na czym polega

Standard 802.11 rozdziela autentykację (hasło/certyfikat) od rutowania pakietów (adres MAC). AP nie weryfikuje, czy nowy klient używający danego MAC-a to ta sama osoba co poprzednio. Atakujący loguje się swoimi danymi, ale z MAC-em ofiary — AP aktualizuje tablicę asocjacji i zaczyna kierować ruch ofiary do atakującego. Client Isolation nie pomaga, bo nie chroni przed podmianą MAC przy asocjacji.

### Wyniki

| Test | Wynik |
|------|-------|
| sta1 → sta2 przed atakiem | 100% packet loss — izolacja działa |
| sta1 → h1 przed atakiem | 0% packet loss — routing działa |
| tcpdump na sta2 po ataku | 10 pakietów `h1 → sta1` przechwyconych |

### Uruchomienie

```bash
sudo mn -c && sudo modprobe mac80211_hwsim radios=4
sudo python3 /home/kali/bbsk-projekt/bartek-mac-flood/topology.py
# napraw OVS bridge, a potem:
mininet-wifi> sta2 python3 /home/kali/bbsk-projekt/bartek-mac-flood/demo.py
```

Szczegóły: [`bartek-mac-flood/README.md`](bartek-mac-flood/README.md)  
Dokumentacja ataku: [`bartek-mac-flood/MAC-Spoofing-Association-Hijacking.md`](bartek-mac-flood/MAC-Spoofing-Association-Hijacking.md)

---

<!-- KAMIL: uzupełnij sekcję poniżej opisem swojego ataku AirSnitch -->
## Kamil — AirSnitch (Client Isolation Bypass)

> **TODO dla Kamila:** uzupełnij tę sekcję.
> Wzoruj się na sekcji Bartka powyżej. Dodaj:
> - krótki opis na czym polega atak
> - tabelę wyników
> - komendę uruchomienia
> - link do swojego README w `kamil-airsnitch/`

Szczegóły: [`kamil-airsnitch/README.md`](kamil-airsnitch/README.md)

---

## Kuba — PMF Bypass przez Beacon CSA Injection

Szczegóły i pełny raport: [`kuba-pmf-bypass/`](kuba-pmf-bypass/)

### Szybki start

```bash
ssh kali-lab lab-run sync
ssh kali-lab "sudo python3 /mnt/hgfs/kuba-pmf-bypass/raport/direct_hwsim_csa.py --hostapd-ver 2.6 --pmf 2 --no-wmediumd"
```

### Demo (na VM, bez SSH)

```bash
cd /mnt/hgfs/demo
sudo python3 demo_atak_csa.py
```
