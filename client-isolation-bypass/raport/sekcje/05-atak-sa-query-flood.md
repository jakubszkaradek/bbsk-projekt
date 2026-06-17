# 05 — Atak: SA Query Flood

**Data:** 2-3 czerwca 2026  

## 1. Opis ataku

SA (Security Association) Query to mechanizm obronny PMF: gdy stacja otrzyma podejrzana ramke Robust Management (np. deauth), wysyla do AP zapytanie SA Query: "czy naprawde wyslales te ramke?". AP odpowiada SA Query Response. Jesli AP potwierdzi — stacja akceptuje ramke. Jesli nie — ramka jest odrzucana.

Atak **SA Query Flood** probuje przeciazyc ten mechanizm: atakujacy wysyla bardzo duzo sfalszowanych ramek deauth w krotkim czasie. Kazda ramka powoduje wyslanie SA Query przez stacje do AP. Jesli AP nie nadazy z odpowiedziami, mechanizm moze ulec timeoutowi, a stacja moze zaakceptowac niezweryfikowana ramke.

## 2. Implementacja

```python
# Generowanie ramki deauth
frame = RadioTap() / Dot11(
    type=0, subtype=12,
    addr1=target_mac,
    addr2=ap_mac,
    addr3=ap_mac,
) / Dot11Deauth(reason=7)

# Wysylanie z duza czestotliwoscia
for i in range(count):
    sendp(frame, iface='wlan0', count=10, inter=0.01, verbose=False)
    sent_count += 10
    time.sleep(interval * 10)
```

## 3. Wyniki

**Parametry ataku:**
| Parametr | Wartosc |
|----------|---------|
| Cel | sta1 |
| Docelowa czestotliwosc | 50 ramek/sekunde |
| Czas trwania | ~15 sekund |
| Laczna liczba wyslanych ramek | 110 |
| Rzeczywista czestotliwosc | ~7 ramek/sekunde |

```
[2026-06-09T09:49:20] === Analysis ===
[PASS] Station remained connected.
       PMF protection held — SA Query flood did not cause disconnect.
       AP handled 110 deauth attempts without issue.
```

**Wynik:** Atak **NIESKUTECZNY**. Stacja pozostala polaczona. PMF wytrzymal zalew 110 ramkami deauth.

## 4. Analiza

Rzeczywista czestotliwosc wysylania (~7 ramek/s) jest nizsza od docelowej (50/s) ze wzgledu na narzut zwiazany z wywolaniami `sta.cmd()` — kazde wyslanie 10 ramek wymaga osobnego procesu Pythona w przestrzeni nazw Mininet. Jest to ograniczenie srodowiska testowego, nie samego ataku.

Mimo to, nawet 110 ramek deauth nie spowodowalo rozlaczenia stacji. Sugeruje to, ze mechanizm SA Query jest odporny na ataki typu flood — AP nadaza z odpowiadaniem na zapytania SA Query, a stacja nie akceptuje niezweryfikowanych ramek.

Nalezy zauwazyc, ze test przeprowadzono w srodowisku wirtualnym, gdzie opoznienia sieciowe sa minimalne. W srodowisku rzeczywistym, przy wiekszych opoznieniach i rzeczywistej mocy obliczeniowej AP, wyniki moga sie roznic.

## 5. Uwagi

- Rzeczywisty limit ramek na sekunde w tescie byl ograniczony przez narzut Mininet-WiFi
- Docelowy atak w warunkach rzeczywistych moglby osiagnac znacznie wyzsze czestotliwosci
- Test nie mierzyl bezposrednio ruchu SA Query/Response — wymagana dodatkowa analiza Wireshark

---

**[screenshot: Terminal — output sa_query_flood.py pokazujacy licznik ramek i PASS]**  
**[screenshot: Wireshark — zalew ramek deauth (wiele ramek w krotkim odstepie)]**  
**[screenshot: Wireshark — ramka SA Query (Action Frame) wyslana przez stacje do AP]**
