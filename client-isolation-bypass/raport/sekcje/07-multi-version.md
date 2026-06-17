# 07 — Testy Wielowersyjne hostapd

**Data:** 8-9 czerwca 2026  

## 1. Cel

Porownanie zachowania roznych wersji hostapd pod katem ochrony PMF, ze szczegolnym uwzglednieniem klasyfikacji ramek Action Frame (CSA).

## 2. Konfiguracja

Zbudowano dwie wersje hostapd:

| Wersja | Zrodlo | Data wydania | CSA |
|--------|--------|-------------|-----|
| hostapd 2.6 | hostap_2_6 tag (git) | ~2016 | Non-Robust |
| hostapd 2.10 | Kali Linux (apt) | 2024 | Robust |

### Kompilacja hostapd 2.6

```bash
git clone --branch hostap_2_6 https://w1.fi/hostap.git
cd hostap/hostapd
cp defconfig .config

# Wlaczenie PMF
cat >> .config << 'EOF'
CONFIG_DRIVER_NL80211=y
CONFIG_LIBNL32=y
CONFIG_IEEE80211W=y
CONFIG_IEEE80211N=y
EOF

make -j$(nproc)
sudo cp hostapd /opt/hostapd-2.6/bin/
```

## 3. Macierz wynikow

### 3.1 Testy bezpieczenstwa (baseline)

| Test | hostapd 2.6 | hostapd 2.10 |
|------|------------|-------------|
| Client Isolation | PASS | PASS |
| PMF Deauth Protection | PASS | PASS |
| SA Query Flood | PASS | nie testowano |

### 3.2 Testy CSA Injection (2026-06-10)

| Wektor ataku | hostapd 2.6 | hostapd 2.10 |
|-------------|------------|-------------|
| **Beacon CSA** (subtype 8, IE 37) | **SUCCESS** — ch6→ch11 | **SUCCESS** — ch6→ch11 |
| Action Frame CSA (subtype 13) | n/a (hwsim nie wspiera Action CSA na STA) | n/a |
| **Pelny exploit (CSA + Evil Twin)** | **SUCCESS** — reassocjacja | nie testowano |

**Kluczowy wniosek:** Beacon CSA omija PMF na **wszystkich** wersjach hostapd, poniewaz Beacon (subtype 8) jest zawsze klasyfikowany jako Non-Robust Management Frame przez 802.11w, niezaleznie od wersji hostapd.

## 4. Analiza

### PMF Deauth — obie wersje chronia

Zarowno hostapd 2.6 jak i 2.10 poprawnie implementuja ochrone PMF dla ramek deauthentication. Sfalszowane ramki bez MIC sa odrzucane przez stacje. Wynik jest zgodny ze specyfikacja 802.11w — ramki Deauth (subtype 12) sa klasyfikowane jako Robust Management w obu wersjach.

### CSA — dwie sciezki, rozna ochrona

Analiza kodu zrodlowego kernela 6.19.14 (2026-06-10) ujawnila dwie niezalezne sciezki CSA:

1. **Action Frame CSA** (subtype 13): klasyfikacja jako Robust/Non-Robust zalezy od wersji hostapd (commit `4c8d4e8e`). Chroniona na hostapd ≥ 2.7.
2. **Beacon CSA** (subtype 8, IE 37): **NIGDY niechroniona** — Beacon jest Non-Robust wg 802.11w. Dziala na wszystkich wersjach hostapd.

Roznica w klasyfikacji Action Frame CSA miedzy wersjami hostapd (Non-Robust w 2.6, Robust w 2.7+) ma znaczenie tylko dla atakow przez Action Frame — nie wplywa na skutecznosc Beacon CSA.

### Znaczenie wersji

Dla administratorow sieci:
- **hostapd ≥ 2.7** — pelna ochrona PMF dla wszystkich Action Frames
- **hostapd < 2.7** — podatnosc na CSA Injection (atakujacy moze zmusic klienta do przelaczenia kanalu)
- Zalecana aktualizacja do najnowszej wersji

## 5. Wnioski

Roznica w klasyfikacji CSA miedzy wersjami hostapd jest istotna z punktu widzenia bezpieczenstwa. Organizacje uzywajace starszych wersji hostapd powinny rozwazyc aktualizacje. Testy w srodowisku wirtualnym potwierdzaja poprawnosc ochrony PMF dla ramek Deauth, ale nie pozwalaja na pelna weryfikacje ataku CSA Injection.

---

**[screenshot: Terminal — kompilacja hostapd 2.6 ze zrodla]**  
**[screenshot: Terminal — porownanie wersji (`hostapd -v`)]**  
**[screenshot: Tabela — macierz wynikow testow]**
