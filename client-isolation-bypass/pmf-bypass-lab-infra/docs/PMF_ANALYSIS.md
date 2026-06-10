# PMF (802.11w) — Protected Management Frames: Theoretical Analysis

## 1. Background

Before 802.11w (ratified 2009), ALL Wi-Fi management frames were sent
unauthenticated and unencrypted. This meant any attacker within radio range
could:

- Send forged Deauthentication frames to disconnect users (DoS)
- Spoof Disassociation frames
- Manipulate Action Frames (e.g., Channel Switch Announcements)

**802.11w (PMF)** was introduced to close this gap by cryptographically
protecting a subset of management frames called **Robust Management Frames**.

---

## 2. Frame Classification Under PMF

| Category | Subtype | Frame Name | Protected by PMF? |
|----------|---------|------------|-------------------|
| **Management** | 0 | Association Request | NO (non-robust) |
| **Management** | 1 | Association Response | NO (non-robust) |
| **Management** | 2 | Reassociation Request | NO (non-robust) |
| **Management** | 3 | Reassociation Response | NO (non-robust) |
| **Management** | 4 | Probe Request | NO (non-robust) |
| **Management** | 5 | Probe Response | NO (non-robust) |
| **Management** | 8 | Beacon | NO (non-robust) |
| **Management** | 9 | ATIM | NO |
| **Management** | 10 | Disassociation | **YES** (Robust) |
| **Management** | 11 | Authentication | NO (non-robust) |
| **Management** | 12 | Deauthentication | **YES** (Robust) |
| **Management** | 13 | Action | **DEPENDS** (see §3) |

### Key takeaway

PMF protects: **Deauth (12), Disassociation (10), and select Action frames (13).**
It does NOT protect: Beacon, Probe, Auth, or Assoc frames.

---

## 3. The Gray Zone — Action Frames

Action Frames (subtype 13) are the most ambiguous category under PMF.
The standard distinguishes:

- **Robust Action Frames** — protected by PMF (e.g., SA Query, BSS Transition Management Query)
- **Non-Robust Action Frames** — NOT protected (e.g., Spectrum Management, certain CSA variants)

### 3.1 Channel Switch Announcement (CSA)

CSA (802.11h) is an Action Frame used by the AP to tell stations to change
channel. Historically, this frame was classified as:

- **Non-Robust** in early 802.11w implementations
- **Robust** in newer implementations (post-2016 hostapd patches)

**Implication:** Older hostapd versions may NOT protect CSA frames via PMF,
allowing an attacker to spoof a CSA and force stations off-channel onto an
attacker-controlled Evil Twin AP.

The relevant hostapd commit that changed CSA classification:
- hostapd commit `4c8d4e8e` (2016-04): "Make Channel Switch Announcement frames robust"

### 3.2 BSS Transition Management (802.11v)

BSS Transition frames can be used to steer clients between APs.
Whether these are protected depends on the `RM Enabled Capabilities` element
negotiated during association.

### 3.3 SA Query Procedure

SA (Security Association) Query is a PMF-specific mechanism: when a station
receives an unprotected Robust Management Frame, it can send an SA Query to
the AP to verify the frame's authenticity. The AP responds, and if the
response confirms the frame was legitimate, the station accepts it.

**Attack surface:** SA Query timeout. If the attacker blocks the SA Query
response, the station may accept the spoofed frame after a timeout.

---

## 4. PMF Modes in hostapd

| `ieee80211w` | Mode | Behavior |
|-------------|------|----------|
| 0 | Disabled | No PMF protection — all management frames accepted |
| 1 | Optional | PMF-capable stations get protection; legacy stations connect without |
| 2 | Required | ALL stations must support PMF or they are rejected |

### Configuration implications

- `ieee80211w=2` is the strongest: even if an attacker spoofs a deauth from
  the AP's MAC, the station will **ignore it** because it lacks the PMF
  cryptographic integrity check (MIC).

- `ieee80211w=1` is less secure: legacy clients that don't support PMF
  are still vulnerable to deauth attacks. The attacker can target these
  specific clients by checking their Association Request capabilities.

---

## 5. What PMF Does NOT Protect Against

Even with `ieee80211w=2`, several attack surfaces remain:

1. **Non-Robust Action Frames:** CSA in older implementations, Spectrum
   Management frames, etc.

2. **Beacon-based attacks:** Beacons are never protected. An attacker can
   broadcast a fake Beacon with a CSA element, and stations that process
   Beacon CSA may switch channel.

3. **4-Way Handshake attacks:** PMF protects management frames AFTER
   association, but the 4-Way Handshake itself occurs during association
   and has its own attack surface (e.g., replay attacks).

4. **SA Query flood:** An attacker can send many SA Queries to overload
   the AP's state table.

5. **Timing/DoS at radio level:** PMF doesn't prevent physical layer
   jamming or channel congestion.

---

## 6. PMF Evolution Across hostapd Versions

| hostapd version | PMF support | CSA classification | Notes |
|----------------|-------------|-------------------|-------|
| pre-2.0 | None | N/A | No 802.11w at all |
| 2.0–2.4 | Basic | Non-Robust | Early PMF, CSA unprotected |
| 2.5–2.6 | Improved | Non-Robust (default) | SA Query support added |
| 2.7+ | Full | Robust (patched) | CSA reclassified as Robust |
| 2.9+ | Stable | Robust | Current standard |

---

## 7. Defensive Measures (WIDS Perspective)

A Wireless IDS should monitor for:

| Anomaly | Detection Method | Indication |
|---------|-----------------|------------|
| Deauth flood | >N deauth frames from single source in T seconds | Active PMF bypass attempt |
| CSA spoofing | Channel change without corresponding Beacon CSA from legitimate AP | PMF Action Frame bypass |
| SA Query flood | High rate of SA Query frames | Resource exhaustion attack |
| Disassociation storm | Loss of multiple clients simultaneously | Coordinated DoS |
| Unexpected channel switch | Client appears on unexpected channel | CSA manipulation successful |

### Configuration hardening (hostapd)

```
# Force PMF
ieee80211w=2

# Limit stations per AP
max_num_sta=10

# MAC ACL (whitelist)
macaddr_acl=1
accept_mac_file=/etc/hostapd/accept_mac

# Disable legacy rates (reduces attack surface on non-robust frames)
hw_mode=g
```

---

## 8. References

- IEEE 802.11w-2009 Amendment: Protected Management Frames
- hostapd configuration: https://w1.fi/cgit/hostap/plain/hostapd/hostapd.conf
- Vanhoef, M. "Framing Frames: Bypassing Wi-Fi Encryption by Manipulating Transmit Queues" (USENIX Security 2023)
- Schepers, D. "wifi-deauthentication" — https://github.com/domienschepers/wifi-deauthentication
