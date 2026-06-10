# 07 — Testy Wielowersyjne hostapd

**Data:** 8-9 czerwca 2026  

## 1. Cel

Porównanie zachowania różnych wersji hostapd pod kątem ochrony PMF, ze szczególnym uwzględnieniem klasyfikacji ramek Action Frame (CSA).

## 2. Konfiguracja

Zbudowano dwie wersje hostapd:

| Wersja | Źródło | Data wydania | CSA |
|--------|--------|-------------|-----|
| hostapd 2.6 | hostap_2_6 tag (git) | ~2016 | Non-Robust |
| hostapd 2.10 | Kali Linux (apt) | 2024 | Robust |

### Kompilacja hostapd 2.6

```bash
git clone --branch hostap_2_6 https://w1.fi/hostap.git
cd hostap/hostapd
cp defconfig .config

# Włączenie PMF
cat >> .config << 'EOF'
CONFIG_DRIVER_NL80211=y
CONFIG_LIBNL32=y
CONFIG_IEEE80211W=y
CONFIG_IEEE80211N=y
EOF

make -j$(nproc)
sudo cp hostapd /opt/hostapd-2.6/bin/
```

## 3. Macierz wyników

### 3.1 Testy bezpieczeństwa (baseline)

| Test | hostapd 2.6 | hostapd 2.10 |
|------|------------|-------------|
| Client Isolation | PASS | PASS |
| PMF Deauth Protection | PASS | PASS |
| SA Query Flood | PASS | nie testowano |

### 3.2 Testy CSA Injection (2026-06-10)

| Wektor ataku | hostapd 2.6 | hostapd 2.10 |
|-------------|------------|-------------|
| **Beacon CSA** (subtype 8, IE 37) | 🎯 **SUCCESS** — ch6→ch11 | 🎯 **SUCCESS** — ch6→ch11 |
| Action Frame CSA (subtype 13) | ❌ n/a (hwsim nie wspiera Action CSA na STA) | ❌ n/a |
| **Pełny exploit (CSA + Evil Twin)** | 🎯 **SUCCESS** — reassocjacja | ⏸️ nie testowano |

**Kluczowy wniosek:** Beacon CSA omija PMF na **wszystkich** wersjach hostapd, ponieważ Beacon (subtype 8) jest zawsze klasyfikowany jako Non-Robust Management Frame przez 802.11w, niezależnie od wersji hostapd.

## 4. Analiza

### PMF Deauth — obie wersje chronią

Zarówno hostapd 2.6 jak i 2.10 poprawnie implementują ochronę PMF dla ramek deauthentication. Sfałszowane ramki bez MIC są odrzucane przez stację. Wynik jest zgodny ze specyfikacją 802.11w — ramki Deauth (subtype 12) są klasyfikowane jako Robust Management w obu wersjach.

### CSA — dwie ścieżki, różna ochrona

Analiza kodu źródłowego kernela 6.19.14 (2026-06-10) ujawniła dwie niezależne ścieżki CSA:

1. **Action Frame CSA** (subtype 13): klasyfikacja jako Robust/Non-Robust zależy od wersji hostapd (commit `4c8d4e8e`). Chroniona na hostapd ≥ 2.7.
2. **Beacon CSA** (subtype 8, IE 37): **NIGDY niechroniona** — Beacon jest Non-Robust wg 802.11w. Działa na wszystkich wersjach hostapd.

Różnica w klasyfikacji Action Frame CSA między wersjami hostapd (Non-Robust w 2.6, Robust w 2.7+) ma znaczenie tylko dla ataków przez Action Frame — nie wpływa na skuteczność Beacon CSA.

### Znaczenie wersji

Dla administratorów sieci:
- **hostapd ≥ 2.7** — pełna ochrona PMF dla wszystkich Action Frames
- **hostapd < 2.7** — podatność na CSA Injection (atakujący może zmusić klienta do przełączenia kanału)
- Zalecana aktualizacja do najnowszej wersji

## 5. Wnioski

Różnica w klasyfikacji CSA między wersjami hostapd jest istotna z punktu widzenia bezpieczeństwa. Organizacje używające starszych wersji hostapd powinny rozważyć aktualizację. Testy w środowisku wirtualnym potwierdzają poprawność ochrony PMF dla ramek Deauth, ale nie pozwalają na pełną weryfikację ataku CSA Injection.

---

**[✗ SCREENSHOT: Terminal — kompilacja hostapd 2.6 ze źródła]**  
**[✗ SCREENSHOT: Terminal — porównanie wersji (`hostapd -v`)]**  
**[✗ SCREENSHOT: Tabela — macierz wyników testów]**
