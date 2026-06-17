# PMF Bypass — Raport z Badan Bezpieczenstwa 802.11w

## Streszczenie Wykonawcze

**Projekt:** Analiza i proba obejscia mechanizmu Protected Management Frames (802.11w)  
**Autor:** Kuba  
**Okres badawczy:** 25 maja – 9 czerwca 2026  
**Srodowisko:** Kali Linux (VMware), Mininet-WiFi 2.7, mac80211_hwsim, hostapd 2.6/2.10

### Cel

Zbadanie skutecznosci mechanizmu PMF (Protected Management Frames, IEEE 802.11w) w ochronie przed atakami na ramki zarzadzajace w sieciach Wi-Fi. Weryfikacja, czy przy wlaczonym PMF w trybie `required` (ieee80211w=2) mozliwe jest:
- Wymuszenie rozlaczenia klienta poprzez sfalszowane ramki deauthentication
- Przeprowadzenie ataku SA Query Flood
- Manipulacja kanalem klienta poprzez CSA (Channel Switch Announcement) Injection

### Glowne ustalenia

1. **Deauth spoofing — NIESKUTECZNY przy PMF=required.** Stacja poprawnie odrzuca sfalszowane ramki deauthentication pozbawione kryptograficznego podpisu MIC.

2. **SA Query Flood — NIESKUTECZNY.** Mechanizm SA Query jest odporny na zalewanie ramkami. Przy 110 ramkach w ciagu ~15 sekund stacja pozostala polaczona.

3. **CSA Injection — ograniczenia srodowiska wirtualnego.** W symulowanym srodowisku mac80211_hwsim atak CSA nie powoduje przelaczania kanalu — wszystkie wirtualne radia dziela te sama przestrzen radiowa.

4. **Wersja hostapd ma znaczenie.** Hostapd < 2.7 klasyfikuje ramki CSA jako Non-Robust (niechronione przez PMF). Hostapd ≥ 2.7 klasyfikuje je jako Robust. Testy przeprowadzono na obu wersjach.

### Wnioski

PMF w trybie `required` skutecznie chroni przed atakami na ramki zarzadzajace w testowanym srodowisku. Atak CSA Injection wymaga starszej wersji hostapd (< 2.7) oraz rzeczywistego sprzetu radiowego — symulacja programowa nie odwzorowuje w pelni mechanizmu przelaczania kanalow.

### Struktura raportu

| Sekcja | Zawartosc |
|--------|-----------|
| [01-metodologia.md](01-metodologia.md) | Metodologia testow i model zagrozenia |
| [02-lab-setup.md](02-lab-setup.md) | Konfiguracja laboratorium |
| [03-baseline-testy.md](03-baseline-testy.md) | Wyniki testow bazowych |
| [04-atak-pmf-deauth.md](04-atak-pmf-deauth.md) | Atak Deauth Spoofing |
| [05-atak-sa-query-flood.md](05-atak-sa-query-flood.md) | Atak SA Query Flood |
| [06-atak-csa-injection.md](06-atak-csa-injection.md) | Atak CSA Injection |
| [07-multi-version.md](07-multi-version.md) | Testy wielowersyjne hostapd |
| [08-problemy-implementacyjne.md](08-problemy-implementacyjne.md) | Napotkane problemy |
| [09-wnioski.md](09-wnioski.md) | Wnioski i rekomendacje |
