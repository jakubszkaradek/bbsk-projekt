# DEEPRESEARCH PROMPT: Kali Kernel Rebuild for mac80211_hwsim CSA Channel Switch Support

## ⚠️ CRITICAL: Read this entire prompt before starting any research. Your task is to produce a comprehensive research report covering ALL sections below. Do NOT stop early. Every section must be addressed.

---

## 1. PROJECT CONTEXT — What We're Building

**Project:** PMF (802.11w) Bypass via Beacon CSA Injection  
**Goal:** Prove that Beacon-based Channel Switch Announcement (CSA) bypasses Protected Management Frames on ALL hostapd versions, because Beacon frames (802.11 subtype 8) are NEVER protected by PMF per the IEEE 802.11w standard.

**Architecture:**
```
Attacker injects spoofed Beacon frames with CSA IE (tag 37)
    → Spoofed Beacon claims "AP is switching from channel 6 to channel 11"
    → Victim station processes the Beacon (Beacons are always Non-Robust)
    → Station switches to channel 11
    → Attacker's Evil Twin AP on channel 11 captures the station
```

**Why Beacon CSA:** Action Frame CSA (subtype 13) is protected by PMF on hostapd ≥ 2.7. But Beacon frames (subtype 8) are NEVER protected — even with `ieee80211w=2` (PMF required). This is a fundamental gap in the 802.11w specification.

**External Validation (already confirmed):**
- **Politician** (ESP32 tool by 0ldev): `_sendCsaBurst()` uses Beacon CSA — confirmed working on real hardware
- **BeaconStrike** (by confnameless): "The Ultimate WPA3 Channel-Switch Exploit Toolkit" — Beacon CSA injection tool
- **Academic paper:** "802.11 Man-in-the-Middle Attack Using Channel Switch Announcement" (Springer 2020)
- **Academic paper:** "On the detection of Channel Switch Announcement Attack in 802.11 networks" (IEEE 2021)
- **Academic paper:** "CSA Attack Tracker" (IEEE Access 2024)

---

## 2. THE TECHNICAL PROBLEM — What's Blocking Us

### 2.1 Environment
- **OS:** Kali GNU/Linux Rolling (2026.2)
- **Kernel:** `6.18.12+kali-amd64`
- **Virtualization:** VMware Workstation on Windows host
- **Wireless simulation:** `mac80211_hwsim` kernel module (virtual 802.11 radios)
- **No physical WiFi hardware available in the VM**

### 2.2 What Works
We have successfully demonstrated:
- ✅ Loading mac80211_hwsim with 4 virtual radios
- ✅ Running hostapd directly on a hwsim interface (AP mode, WPA2-PSK, channel 6)
- ✅ Running wpa_supplicant on a second hwsim interface
- ✅ **REAL 802.11 association** through the kernel: Auth → Assoc → 4-Way Handshake → CONNECTED
- ✅ PMF=2 (required) works correctly — rejects unprotected deauth frames
- ✅ Beacon CSA frame injection via monitor mode (scapy confirms transmission)
- ✅ wmediumd for wireless medium simulation with channel separation

### 2.3 What FAILS — The Root Cause
```
$ sudo iw dev wlan2 switch channel 11
command failed: Operation not supported (-95)

$ sudo iw dev wlan2 set channel 11
(no error but channel does NOT change — stays on channel 6)
```

**Root cause identified:**
```
$ grep CFG80211 /boot/config-6.18.12+kali-amd64
CONFIG_CFG80211=m
# CONFIG_CFG80211_CERTIFICATION_ONUS is not set
```

The `CONFIG_CFG80211_CERTIFICATION_ONUS` kernel option is **NOT ENABLED** in the stock Kali kernel. This option, when set to `y`, relaxes certain regulatory/operational restrictions in cfg80211, including allowing channel switch operations on client (STA) interfaces that would normally be restricted. Without it, the kernel's `cfg80211` subsystem rejects `NL80211_CMD_CHANNEL_SWITCH` on STA interfaces with `-EOPNOTSUPP` (-95).

**The chain of failure:**
1. We inject Beacon CSA frames → they reach the STA interface ✅
2. mac80211 parses the Beacon, extracts CSA IE (tag 37) ✅
3. mac80211 calls `ieee80211_sta_process_chanswitch()` in `net/mac80211/spectmgmt.c`
4. This function attempts to call `cfg80211_ch_switch_notify()` 
5. cfg80211 checks if the underlying driver (hwsim) supports channel switch on STA
6. hwsim driver does NOT register the channel_switch operation for STA interfaces
7. Without `CERTIFICATION_ONUS`, cfg80211 strictly rejects the operation → `-EOPNOTSUPP`

### 2.4 Additional Kernel Details
```
$ uname -a
Linux kali 6.18.12+kali-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.18.12-1kali1 (2026-05-05) x86_64 GNU/Linux

$ ls -la /boot/
config-6.18.12+kali-amd64
System.map-6.18.12+kali-amd64
vmlinuz-6.18.12+kali-amd64
initrd.img-6.18.12+kali-amd64
```

The kernel is a Debian-packaged Kali kernel. We need to either:
- Rebuild the Kali kernel from source with `CERTIFICATION_ONUS=y`
- OR find/build a custom kernel that supports this
- OR find an alternative approach to enable channel switching on hwsim STA

---

## 3. RESEARCH TASKS — What We Need You To Find

### TASK A: Has Anyone Done This Before?
Search for **anyone** who has:
- Rebuilt the Kali/Ubuntu/Debian kernel with `CONFIG_CFG80211_CERTIFICATION_ONUS=y`
- Modified mac80211_hwsim to support channel switching on STA interfaces
- Successfully tested CSA (Channel Switch Announcement) on mac80211_hwsim
- Written about or documented the `CERTIFICATION_ONUS` flag and its effects on WiFi testing
- Created patches or workarounds for hwsim channel switch limitations

**Specific search targets:**
- GitHub issues and PRs mentioning `CONFIG_CFG80211_CERTIFICATION_ONUS`
- Kernel mailing list (LKML) threads about cfg80211 certification_onus
- Stack Overflow / Server Fault / Unix & Linux Stack Exchange posts
- Kali Linux forums and bug trackers
- Reddit: r/KaliLinux, r/linux, r/netsec, r/wifi
- Blog posts about "hwsim channel switch" or "mac80211_hwsim CSA"
- YouTube tutorials on custom Kali kernel builds

### TASK B: Prebuilt Kernels & Ready Solutions
Find if there exists:
- A prebuilt Kali/Debian kernel package with `CERTIFICATION_ONUS=y`
- Any Linux distribution that ships with this flag enabled by default
- Docker images or VM appliances pre-configured for WiFi security testing with hwsim CSA support
- Alternative kernel modules or DKMS packages that add channel switch support to hwsim
- Any project on GitHub that provides "hwsim with CSA support" or similar

**Specific search targets:**
- `site:github.com CONFIG_CFG80211_CERTIFICATION_ONUS`
- `site:github.com "certification_onus" kernel config`
- Kali package repositories for custom kernel builds
- Ubuntu mainline kernel builds with modified configs
- Arch Linux AUR packages related to cfg80211 or hwsim

### TASK C: Kernel Contributors & Experts
Identify:
- Who wrote/committed the `CONFIG_CFG80211_CERTIFICATION_ONUS` code
- Maintainers of `net/wireless/` and `drivers/net/wireless/mac80211_hwsim.c`
- Key contributors to the `cfg80211` subsystem who might have insight into channel switch behavior
- Anyone who has submitted patches related to channel switching on virtual WiFi interfaces
- Developers who work on wireless testing frameworks (hostapd test suite, wmediumd, etc.)

**Specific search targets:**
- `git log -- net/wireless/` on the Linux kernel repository
- `git blame drivers/net/wireless/mac80211_hwsim.c` for channel_switch related code
- MAINTAINERS file entry for `CFG80211` and `MAC80211_HWSIM`
- Authors of recent commits to `net/mac80211/spectmgmt.c` (where `ieee80211_sta_process_chanswitch` lives)

### TASK D: Alternative Approaches
Research alternative ways to achieve our goal WITHOUT rebuilding the kernel:
- Can we use `iw dev wlanX set channel` differently?
- Can we create a virtual monitor interface that forces a channel change?
- Can we use netlink directly to bypass cfg80211 restrictions?
- Can we use `mac80211_hwsim` module parameters to enable channel switching?
- Is there a way to patch only the hwsim module (not full kernel rebuild)?
- Can we use qemu/kvm with a custom kernel for just the wireless testing?
- Are there user-space WiFi stacks that support CSA without kernel support?
- Can we use `aircrack-ng` or similar tools to force channel changes?
- Does the `support_p2p_device` hwsim parameter affect channel switching?

### TASK E: Build Guide Research
Find the best, most reliable guide for rebuilding the Kali kernel:
- Official Kali documentation for kernel rebuilds
- Step-by-step guides tested on Kali 2024-2026
- Known pitfalls and gotchas when rebuilding Kali kernels
- How to preserve the existing kernel as fallback
- How to build only the wireless modules (not full kernel) if possible
- GRUB configuration for dual-booting custom kernels
- VMware-specific considerations for custom kernels

---

## 4. TECHNICAL NUANCES — Details The Researcher Must Understand

### 4.1 Why `CERTIFICATION_ONUS` matters specifically
The flag name is misleading. "Certification Onus" means "the burden of certification is on you." When enabled, it allows non-standard behavior that would normally fail WiFi certification tests. Specifically for our case:

- **Without the flag:** cfg80211 checks if the driver's `wiphy` has the `NL80211_IFTYPE_STATION` flag set in its `channel_switch` supported interfaces mask. Since hwsim only registers channel_switch support for AP interfaces, STA channel switches are rejected.
- **With the flag:** cfg80211 skips this check and allows the channel switch operation to proceed, placing the "certification onus" on the user.

### 4.2 The specific kernel files involved
- `net/wireless/nl80211.c` — handles `NL80211_CMD_CHANNEL_SWITCH` (the command we're failing on)
- `net/wireless/chan.c` — `cfg80211_ch_switch_notify()` and related functions
- `drivers/net/wireless/mac80211_hwsim.c` — the hwsim driver, specifically its `wiphy` registration
- `net/mac80211/spectmgmt.c` — `ieee80211_sta_process_chanswitch()` where CSA IEs are processed
- `net/mac80211/cfg.c` — mac80211's cfg80211 ops, including channel switch
- `include/net/cfg80211.h` — data structures and flags

### 4.3 What we've already tried
- Mininet-WiFi with OVSAP mode → no real 802.11 association (bridging only)
- Mininet-WiFi with wmediumd link mode → same issue
- Direct hostapd + wpa_supplicant on hwsim → association works! But channel switch fails
- `iw dev wlanX switch channel N` → `Operation not supported (-95)`
- `iw dev wlanX set channel N` → no error, but channel doesn't actually change
- Verified the kernel config → `CERTIFICATION_ONUS` is confirmed disabled

### 4.4 Error codes decoded
- `-95` = `EOPNOTSUPP` (Operation not supported)
- `-16` = `EBUSY` (Device or resource busy) — seen during wpa_supplicant scan attempts
- `-19` = `ENODEV` (No such device)

---

## 5. OUTPUT FORMAT — What Your Research Report Must Contain

Please structure your findings as follows:

```
# Research Report: Enabling CSA Channel Switch on mac80211_hwsim

## 1. Executive Summary
(3-5 sentences summarizing all key findings)

## 2. Prior Art — Who Has Done This
(For each finding: URL, date, author, what they did, outcome, relevance to our project)

## 3. Prebuilt Solutions
(Any ready-to-use kernels, packages, Docker images, or VMs)

## 4. Key People & Contacts
(Names, GitHub handles, email if public, areas of expertise, relevant commits)

## 5. Alternative Approaches
(Any way to achieve our goal without full kernel rebuild)

## 6. Build Guide Recommendations
(Best guides found, ranked by reliability/recency, with specific links)

## 7. Risks & Known Issues
(What can go wrong, what others have encountered, mitigation strategies)

## 8. Recommended Action Plan
(Your synthesized recommendation for the most reliable path forward)

## 9. All Source URLs
(Complete list of every URL referenced, with brief description)
```

---

## 6. SEARCH STRATEGY — Specific Queries To Run

Run these exact searches (and variations thereof):

```
1. CONFIG_CFG80211_CERTIFICATION_ONUS kernel rebuild
2. "certification_onus" site:github.com
3. mac80211_hwsim channel switch STA "not supported"
4. "NL80211_CMD_CHANNEL_SWITCH" hwsim station
5. kali linux rebuild kernel custom config step by step
6. "ieee80211_sta_process_chanswitch" hwsim
7. cfg80211_ch_switch_notify "operation not supported"
8. linux kernel CONFIG_CFG80211_CERTIFICATION_ONUS explained
9. mac80211_hwsim CSA test channel switch announcement
10. build kali kernel from source 2024 2025 2026
11. debian rebuild kernel wireless certification onus
12. "iw dev" "switch channel" "not supported" hwsim
13. hostapd hwsim test CSA channel switch test case
14. github mac80211_hwsim channel switch STA patch
15. wmediumd channel switch station mode cfg80211
```

**Also search these specific GitHub repositories:**
- `torvalds/linux` — especially `net/wireless/` and `drivers/net/wireless/mac80211_hwsim.c`
- `johannesberg/linux` — Johannes Berg's kernel tree (cfg80211 maintainer)
- `ramonfontes/wmediumd` — wmediumd (branch: mininet-wifi)
- `ramonfontes/mininet-wifi` — Mininet-WiFi
- `bcopeland/wmediumd` — alternative wmediumd
- `patgrosse/wmediumd-python-connector` — wmediumd Python tools
- `patgrosse/mac80211_hwsim_mgmt` — hwsim management tools
- `0ldev/Politician` — Politician ESP32 WiFi attack tool
- `confnameless/BeaconStrike` — BeaconStrike CSA tool
- Kali Linux package repos for kernel-related packages
- Debian kernel team repositories

---

## 7. FINAL INSTRUCTIONS

1. **Be thorough.** This research will determine whether we spend 4-6 hours rebuilding a kernel or find a 30-minute solution.
2. **Cite everything.** Every claim should have a URL, commit hash, or reproducible source.
3. **Prioritize recency.** Prefer information from 2024-2026. Older info may be outdated.
4. **Note dead ends.** If you find something that LOOKS promising but turned out to be a dead end, document it and explain why.
5. **Flag uncertainties.** If you're not sure about something, say so. Don't guess.
6. **Think like a kernel developer.** Consider not just the direct solution but also workarounds, partial solutions, and creative approaches.

**The report you produce will be fed directly into a development agent that will plan and execute the kernel rebuild. Make it comprehensive.**
