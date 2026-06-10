# LAB VM — instrukcja dla agenta AI (Kali / VMware)

Ten dokument opisuje, jak agent AI łączy się z laboratorium, co może robić na VM i jak synchronizuje kod z hostem Windows.

---

## Czy agent ma pełny dostęp?

| Możliwość | Status |
|-----------|--------|
| SSH do VM (`agent@localhost:2222`) | Tak |
| `sudo` bez hasła (user `agent`) | Tak — pełny root na lab |
| Edycja kodu na VM (`~/pmf-bypass-lab-infra`) | Tak |
| Mininet-WiFi / `mn --wifi` | **Zweryfikuj** — może wymagać dokończenia instalacji (Python 3.13 + branch `master`) |
| `mac80211_hwsim` (wlan0–wlan3) | Tak — po `sudo modprobe mac80211_hwsim radios=4` |
| Odczyt share VMware (`/mnt/hgfs`) | Tak (jako `kali`; mount: `uid=1000,gid=1000`) |
| Zapis na share z VM | Tak po poprawnym mount (nie jako root) |

Agent **nie** ma automatycznego dostępu — musi używać SSH z hosta (Cursor terminal / `ssh`). VM musi być **włączona**, port forward **2222→22** skonfigurowany.

---

## Połączenie z hosta Windows

### Jednorazowa konfiguracja `~/.ssh/config`

Na hoście utwórz/edytuj `C:\Users\kalab\.ssh\config`:

```
Host kali-lab
    HostName localhost
    Port 2222
    User agent
    IdentityFile C:/Users/kalab/.ssh/agent_key.pem
    StrictHostKeyChecking accept-new
```

Test:

```powershell
ssh kali-lab "hostname && whoami && sudo -n true && echo SUDO_OK"
```

Oczekiwane: `kali`, `agent`, `SUDO_OK`.

### VMware NAT (stałe)

- Guest IP: `192.168.106.132` (sprawdź: `ip -4 addr show eth0`)
- Forward: **Host 2222 → Guest 22 TCP**

---

## Ścieżki na VM

| Ścieżka | Znaczenie |
|---------|-----------|
| `~/pmf-bypass-lab-infra/` | Główne repo labu (kopia robocza) |
| `/mnt/hgfs/` | Share z Windows (`client-isolation-bypass`) |
| `/mnt/hgfs/pmf-bypass-lab-infra/` | Sync z hostem — edycje na Windows |
| `/opt/mininet-wifi/` | Instalacja Mininet-WiFi |
| `~/raport/` lub `/mnt/hgfs/raport/` | Logi, PCAP, screenshoty do raportu |

### Sync host → VM (po edycji na Windows)

```bash
rsync -av --delete /mnt/hgfs/pmf-bypass-lab-infra/ ~/pmf-bypass-lab-infra/
```

### Sync VM → host (wyniki testów)

```bash
rsync -av ~/raport/ /mnt/hgfs/raport/
# lub bezpośrednio do podfolderów w pmf-bypass-lab-infra
```

---

## Checklist przed pracą agenta

Uruchom na VM (przez SSH):

```bash
# 1. Kernel Wi-Fi sim
sudo modprobe mac80211_hwsim radios=4
iw dev | grep -c Interface   # oczekuj >= 4

# 2. Open vSwitch
sudo systemctl is-active openvswitch-switch

# 3. Python / Scapy
python3 -c "import scapy; print('scapy', scapy.__version__)"
python3 -c "import mn_wifi; print('mn_wifi OK')" 2>/dev/null || echo "BRAK mn_wifi — dokończ install"

# 4. Mininet CLI
command -v mn && sudo mn --wifi --test pingall

# 5. Repo
test -d ~/pmf-bypass-lab-infra/topology && echo "repo OK"
```

Jeśli `mn_wifi` brak — patrz `setup/install.sh` (ścieżka Kali: branch `master` + `pip3 install -e /opt/mininet-wifi`).

---

## Komendy labu (szablony)

```bash
cd ~/pmf-bypass-lab-infra

# Baseline — muszą PASS przed atakami
sudo python3 baseline/test_isolation.py
sudo python3 baseline/test_pmf.py
sudo python3 baseline/test_csa.py

# Topologia interaktywna
sudo python3 topology/lab_topology.py --cli

# Sniffer ramek (interfejs z Mininet, np. ap1-mp1)
sudo python3 wids/scapy_sniffer.py --iface ap1-mp1 --duration 120 --out /tmp/capture.pcap

# Kopiuj PCAP do raportu
cp /tmp/capture.pcap /mnt/hgfs/raport/pcaps/baseline/
```

Wszystkie testy wymagają **`sudo`** (namespaces, hostapd, injection).

---

## Zasady pracy agenta

1. **Czytaj najpierw:** `AGENTS.md`, `AGENT.md`, `pmf-bypass-lab-infra/README.md`, `docs/PMF_ANALYSIS.md`.
2. **Context7:** przed kodem Scapy / Mininet-WiFi — pobierz aktualną dokumentację (`resolve-library-id` → `query-docs`).
3. **Caveman:** komunikacja z userem — zwięzła; kod i komendy — pełne, bez skracania.
4. **Loguj wyniki:** każdy test → `raport/logs/`, PCAP → `raport/pcaps/<nazwa_testu>/`, komendy w raporcie.
5. **Nie commituj:** `agent_key.pem`, kluczy prywatnych, haseł WPA z `configs/`.
6. **Izolacja:** praca tylko na VM labowej; nie skanuj sieci poza labem.
7. **Po sesji:** zapisz postęp w `EXECUTION-MOMENTUM.md` (na hoście przez share).

---

## MASTER PROMPT — wklej na start sesji agenta

```markdown
Jesteś agentem AI projektu PMF Bypass Lab (BBSK, cyberbezpieczeństwo Wi-Fi).

## Cel
Pomagasz zbudować i testować izolowane laboratorium na Kali VM (VMware).
Projekt: Client Isolation + PMF (802.11w). Rola użytkownika: Kuba — PMF Bypass (CSA, deauth, SA Query).

## Środowisko
- Host: Windows + Cursor
- VM: Kali Linux, SSH alias `kali-lab` (localhost:2222, user `agent`, sudo NOPASSWD)
- Repo labu na VM: `~/pmf-bypass-lab-infra/`
- Sync z hostem: `/mnt/hgfs/pmf-bypass-lab-infra/` (rsync)
- Dokumentacja VM: `pmf-bypass-lab-infra/docs/LAB_VM_AGENT.md`

## Jak wykonujesz komendy
Zawsze przez SSH na VM, nie zakładaj że shell jest już na Kali:
  ssh kali-lab "cd ~/pmf-bypass-lab-infra && sudo python3 baseline/test_isolation.py"

Na Windows (PowerShell) przed pracą:
  ssh kali-lab "hostname"

## Kolejność pracy
1. Sprawdź checklist w LAB_VM_AGENT.md (hwsim, ovs, mn_wifi, mn).
2. rsync z /mnt/hgfs jeśli host zmieniał pliki.
3. Uruchom baseline testy — zapisz logi do raport/pcaps.
4. Implementuj / debuguj w `attacks/` (PMF) lub `topology/`, `baseline/`, `wids/`.
5. Po teście: PCAP + komenda + wynik PASS/FAIL do raport/.

## Skille
- **context7-mcp:** dokumentacja Scapy, Mininet-WiFi, hostapd — przed pisaniem kodu.
- **caveman:** odpowiedzi do usera — krótko; kod bez zmian.

## Granice
- Nie pisz treści raportu akademickiego za studenta.
- Nie commituj kluczy SSH ani sekretów.
- Infra repo = środowisko + baseline + WIDS; wektory ofensywne w `attacks/` z logami z VM.

## Pliki prawdy
- Konfig AP: `configs/hostapd.conf` (ieee80211w=2, ap_isolate=1)
- Topologia: `topology/lab_topology.py`
- Teoria PMF: `docs/PMF_ANALYSIS.md`

Zacznij od: połączenia SSH + checklist + status mininet-wifi.
```

---

## Cursor — jak agent ma uruchamiać SSH

W terminalu Cursor (PowerShell na hoście):

```powershell
# pojedyncza komenda
ssh kali-lab "sudo modprobe mac80211_hwsim radios=4 && iw dev"

# interaktywna sesja (user ręcznie)
ssh kali-lab
```

Agent w Cursor **nie** ma wbudowanego Remote-SSH — każda operacja na VM = jawne `ssh kali-lab "..."` albo sesja interaktywna w terminalu.

Opcjonalnie: rozszerzenie **Remote - SSH** w Cursor, host `kali-lab` — wtedy agent edytuje pliki bezpośrednio na VM.

---

## Montowanie share (jeśli puste po reboot)

Jako user `kali` na VM:

```bash
sudo umount /mnt/hgfs 2>/dev/null
sudo mkdir -p /mnt/hgfs
sudo vmhgfs-fuse .host:/client-isolation-bypass /mnt/hgfs -o allow_other,uid=1000,gid=1000
```

---

## Bezpieczeństwo klucza

- Klucz prywatny tylko: `C:\Users\kalab\.ssh\agent_key.pem`
- **Nie** trzymaj `agent_key.pem` w repo / na share po skonfigurowaniu
- Na VM: `sudo shred -u /home/agent/.ssh/id_ed25519` jeśli kopia lokalna jeszcze istnieje
