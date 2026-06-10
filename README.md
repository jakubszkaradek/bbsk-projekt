# BBSK Projekt — Ataki na sieci WiFi

Trzyosobowy projekt zaliczeniowy z przedmiotu BBSK.

## Zespół

| Osoba | Atak | Folder |
|-------|------|--------|
| **Kuba** | PMF Bypass (802.11w) przez Beacon CSA Injection | `kuba-pmf-bypass/` |
| **Kamil** | AirSnitch — Client Isolation bypass | `kamil-airsnitch/` |
| **Bartek** | MAC Flood / DoS | `bartek-mac-flood/` |

## Infrastruktura współdzielona

Laboratorium działa na Kali Linux VM (VMware) z Mininet-WiFi + mac80211_hwsim + hostapd + wpa_supplicant.

Folder `kuba-pmf-bypass/pmf-bypass-lab-infra/` zawiera współdzieloną infrastrukturę (topologia, testy bazowe, WIDS).

## Struktura repo

```
bbsk-projekt/
├── README.md
├── analiza-wnioski.md          # Wspólna analiza i wnioski
├── .gitignore
├── prezentacja/                # Slajdy i materiały prezentacyjne
├── kuba-pmf-bypass/            # PMF Bypass przez Beacon CSA
│   ├── raport/                 # Pełny raport (sekcje 00-09)
│   ├── demo/                   # Skrypty demonstracyjne
│   └── pmf-bypass-lab-infra/   # Infrastruktura laboratoryjna
├── kamil-airsnitch/            # Client Isolation bypass
└── bartek-mac-flood/           # MAC Flood / DoS
```

## Kluczowe wyniki

- **PMF (802.11w) NIE chroni przed Beacon CSA Injection** — Beacon (subtype 8) jest zawsze Non-Robust
- Atak działa na wszystkich testowanych wersjach hostapd (2.6, 2.10)
- **CERTIFICATION_ONUS nie jest wymagane** — ścieżka Beacon CSA w kernelu działa bez rekompilacji
- Beacon CSA **omija standardowe WIDS** (scapy_sniffer, Kismet)

## Szybki start (Kuba)

```bash
ssh kali-lab lab-run sync
ssh kali-lab "sudo python3 /mnt/hgfs/kuba-pmf-bypass/raport/direct_hwsim_csa.py --hostapd-ver 2.6 --pmf 2 --no-wmediumd"
```

## Demo (na VM, bez SSH)

```bash
cd /mnt/hgfs/kuba-pmf-bypass/demo
sudo ./demo_atak_csa.sh
```
