# 05 — Atak: SA Query Flood

**Data:** 2-3 czerwca 2026  

## 1. Opis ataku

SA (Security Association) Query to mechanizm obronny PMF: gdy stacja otrzyma podejrzaną ramkę Robust Management (np. deauth), wysyła do AP zapytanie SA Query: "czy naprawdę wysłałeś tę ramkę?". AP odpowiada SA Query Response. Jeśli AP potwierdzi — stacja akceptuje ramkę. Jeśli nie — ramka jest odrzucana.

Atak **SA Query Flood** próbuje przeciążyć ten mechanizm: atakujący wysyła bardzo dużo sfałszowanych ramek deauth w krótkim czasie. Każda ramka powoduje wysłanie SA Query przez stację do AP. Jeśli AP nie nadąży z odpowiedziami, mechanizm może ulec timeoutowi, a stacja może zaakceptować niezweryfikowaną ramkę.

## 2. Implementacja

```python
# Generowanie ramki deauth
frame = RadioTap() / Dot11(
    type=0, subtype=12,
    addr1=target_mac,
    addr2=ap_mac,
    addr3=ap_mac,
) / Dot11Deauth(reason=7)

# Wysyłanie z dużą częstotliwością
for i in range(count):
    sendp(frame, iface='wlan0', count=10, inter=0.01, verbose=False)
    sent_count += 10
    time.sleep(interval * 10)
```

## 3. Wyniki

**Parametry ataku:**
| Parametr | Wartość |
|----------|---------|
| Cel | sta1 |
| Docelowa częstotliwość | 50 ramek/sekundę |
| Czas trwania | ~15 sekund |
| Łączna liczba wysłanych ramek | 110 |
| Rzeczywista częstotliwość | ~7 ramek/sekundę |

```
[2026-06-09T09:49:20] === Analysis ===
[PASS] Station remained connected.
       PMF protection held — SA Query flood did not cause disconnect.
       AP handled 110 deauth attempts without issue.
```

**Wynik:** Atak **NIESKUTECZNY**. Stacja pozostała połączona. PMF wytrzymał zalew 110 ramkami deauth.

## 4. Analiza

Rzeczywista częstotliwość wysyłania (~7 ramek/s) jest niższa od docelowej (50/s) ze względu na narzut związany z wywołaniami `sta.cmd()` — każde wysłanie 10 ramek wymaga osobnego procesu Pythona w przestrzeni nazw Mininet. Jest to ograniczenie środowiska testowego, nie samego ataku.

Mimo to, nawet 110 ramek deauth nie spowodowało rozłączenia stacji. Sugeruje to, że mechanizm SA Query jest odporny na ataki typu flood — AP nadąża z odpowiadaniem na zapytania SA Query, a stacja nie akceptuje niezweryfikowanych ramek.

Należy zauważyć, że test przeprowadzono w środowisku wirtualnym, gdzie opóźnienia sieciowe są minimalne. W środowisku rzeczywistym, przy większych opóźnieniach i rzeczywistej mocy obliczeniowej AP, wyniki mogą się różnić.

## 5. Uwagi

- Rzeczywisty limit ramek na sekundę w teście był ograniczony przez narzut Mininet-WiFi
- Docelowy atak w warunkach rzeczywistych mógłby osiągnąć znacznie wyższe częstotliwości
- Test nie mierzył bezpośrednio ruchu SA Query/Response — wymagana dodatkowa analiza Wireshark

---

**[✗ SCREENSHOT: Terminal — output sa_query_flood.py pokazujący licznik ramek i PASS]**  
**[✗ SCREENSHOT: Wireshark — zalew ramek deauth (wiele ramek w krótkim odstępie)]**  
**[✗ SCREENSHOT: Wireshark — ramka SA Query (Action Frame) wysłana przez stację do AP]**
