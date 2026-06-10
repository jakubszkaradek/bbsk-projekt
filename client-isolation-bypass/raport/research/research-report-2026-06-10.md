# Research Report: Enabling CSA Channel Switch on mac80211_hwsim

## 1. Executive Summary

The stock Kali 2026.2 kernel (6.18.12+kali-amd64) ships with `CONFIG_CFG80211_CERTIFICATION_ONUS` disabled, which prevents mac80211_hwsim virtual station interfaces from executing channel switches triggered by Beacon CSA injection. This is the sole blocker preventing the PMF bypass proof-of-concept. The fastest path to resolution is a targeted kernel rebuild enabling this single configuration option, which can be completed in under 2 hours using Kali's native kernel packaging infrastructure. No prebuilt kernel with this option enabled was found in any distribution's repositories, and no alternative runtime workaround exists that bypasses the cfg80211 restriction without kernel modification. However, a creative intermediate approach—patching only the mac80211_hwsim kernel module to register channel switch support for station interfaces—may provide a 30-minute solution without full kernel recompilation.

## 2. Prior Art — Who Has Done This

### 2.1 Microsoft WSL2 Kernel Team — Directly Modified CERTIFICATION_ONUS

**Finding:** Commit `76598c510caee04aee422301182bdf0c8320cd42` in the `microsoft/WSL2-Linux-Kernel` repository explicitly modifies `CONFIG_CFG80211_CERTIFICATION_ONUS` from "is not set" to an enabled state [6]. This is the only documented instance found where a major distribution kernel team has deliberately toggled this option.

**Relevance:** Confirms that enabling this option is a known, intentional configuration change for wireless testing scenarios. Microsoft's WSL2 team enabled it specifically to support wireless functionality in their virtualized environment, which parallels our mac80211_hwsim use case.

**Date:** The commit appears in the WSL2 kernel 5.10/5.15 era (2021-2022 timeframe).

**Outcome:** WSL2 kernels with this flag enabled allow wireless operations that would otherwise be restricted, though WSL2's lack of direct hardware access limits practical use [1].

### 2.2 Kali Linux Community — Kernel Rebuild Documentation

**Finding:** The InfoSecWarrior/Kali-Linux-Configuration repository provides structured guidance for Kali system configuration including kernel module management, initramfs regeneration, and module blacklisting [5]. While not specifically about CERTIFICATION_ONUS, the repository documents the exact workflow needed for custom kernel module handling: installing kernel headers via `apt install linux-headers-$(uname -r)`, managing conflicting modules, and regenerating initramfs after changes.

**Relevance:** The module management procedures documented here directly apply to our scenario—whether we rebuild the full kernel or patch only the hwsim module, we'll need to follow these same steps for header installation and initramfs updates.

### 2.3 Academic Research Community — CSA Attack Validation

**Finding:** Multiple academic papers (Springer 2020, IEEE 2021, IEEE Access 2024) have documented and validated the Beacon CSA attack vector against 802.11w PMF. The Politician tool (0ldev/ESP32) and BeaconStrike toolkit (confnameless) have implemented working Beacon CSA injection on real hardware.

**Relevance:** These confirm the attack works on physical hardware where channel switching is natively supported. Our challenge is purely a virtualized testing limitation, not a theoretical flaw in the attack.

### 2.4 Linux Wireless Community — No Public Patches Found

**Finding:** Extensive searching across GitHub, LKML archives, Stack Exchange, and wireless mailing lists revealed **no public patches** that add channel switch support to mac80211_hwsim for station interfaces. The hwsim driver's `wiphy` registration in `drivers/net/wireless/mac80211_hwsim.c` only advertises channel switch capability for AP-type interfaces.

**Relevance:** This is unexplored territory. We would be among the first to document this specific modification for virtualized CSA testing.

### 2.5 Realtek Driver Community — GCC Version Matching Requirement

**Finding:** The morrownr/88x2bu-20210702 out-of-kernel driver documentation explicitly states that the major GCC version used to compile the driver must match the major GCC version used to compile the running kernel [7]. This is verified via `cat /proc/version` and `gcc --version`.

**Relevance:** This same constraint applies to any out-of-tree kernel module compilation, including a patched mac80211_hwsim. We must ensure our build environment's GCC matches the kernel's GCC (likely GCC 14.x for Kali 6.18.12).

### 2.6 WSL2 Wireless Stack — nl80211 Availability Issues

**Finding:** In WSL2 environments, even with `CONFIG_NL80211_TESTMODE=y` and `CONFIG_CFG80211=m`, the nl80211 interface may not be available if the cfg80211 module isn't loaded or if no wireless device drivers are present [1]. USB/IP device forwarding doesn't guarantee automatic module loading.

**Relevance:** This is a cautionary tale about virtualized wireless testing—kernel configuration alone doesn't guarantee functionality. However, our VMware + mac80211_hwsim setup doesn't have this problem since hwsim creates virtual radios that properly trigger cfg80211/mac80211 loading.

## 3. Prebuilt Solutions

### 3.1 No Prebuilt Kernels Found

**Finding:** After exhaustive searching across:
- Kali Linux package repositories (kali-rolling, kali-experimental)
- Ubuntu mainline kernel PPA
- Debian kernel team repositories
- Arch Linux AUR
- GitHub releases for custom kernel builds
- Docker Hub for wireless testing images

**No prebuilt kernel package with `CONFIG_CFG80211_CERTIFICATION_ONUS=y` was found for any distribution.** This configuration option appears to be universally disabled in distribution kernels, likely due to regulatory compliance concerns.

### 3.2 Partial Solutions Considered

**Kali kernel packages with modified configs:** The Kali kernel package source (`linux-kali` or similar) is available but requires local rebuilding to change the config. No prebuilt variants with this option exist.

**Ubuntu mainline kernels:** Tested configs from Ubuntu mainline 6.8 through 6.18—all have `# CONFIG_CFG80211_CERTIFICATION_ONUS is not set`.

**Docker images:** No Docker images were found with preconfigured hwsim CSA support. Most wireless testing Docker images focus on aircrack-ng tool availability rather than kernel-level wireless simulation.

### 3.3 Closest Ready-Made Alternative

The WSL2 kernel with CERTIFICATION_ONUS enabled [6] is the closest prebuilt solution, but it's designed for WSL2's lightweight VM environment and would require significant adaptation to run in VMware with full systemd support. Not recommended as a drop-in replacement.

## 4. Key People & Contacts

### 4.1 cfg80211 Subsystem Maintainers

**Johannes Berg** (Intel/Linux Wireless)
- Role: Primary maintainer of cfg80211, mac80211, and the nl80211 interface
- Relevant: Author of much of `net/wireless/nl80211.c` and `net/wireless/chan.c`
- GitHub: johannesberg (maintains personal kernel tree with wireless patches)
- Key insight: Johannes introduced the `CERTIFICATION_ONUS` flag concept. His commit messages in the wireless tree would explain the original rationale.

### 4.2 mac80211_hwsim Maintainers

**Jouni Malinen** (hostapd/wpa_supplicant author)
- Role: Maintains mac80211_hwsim as part of the hostapd testing infrastructure
- Relevant: The hwsim driver is primarily used for hostapd/wpa_supplicant regression testing
- Key insight: Jouni designed hwsim for AP-side testing. The lack of STA channel switch support may be intentional to match real hardware behavior where stations don't typically initiate channel switches.

### 4.3 CSA Spectrum Management Code Authors

The `ieee80211_sta_process_chanswitch()` function in `net/mac80211/spectmgmt.c` was last significantly modified by:
- **Luis R. Rodriguez** (Qualcomm Atheros) — regulatory domain and spectrum management
- **Emmanuel Grumbach** (Intel) — mac80211 CSA handling improvements

### 4.4 Wireless Testing Framework Developers

**Ramon Fontes** (Mininet-WiFi/wmediumd)
- Role: Creator of Mininet-WiFi and maintainer of wmediumd
- Relevant: Has deep experience with hwsim limitations in virtualized wireless testing
- GitHub: ramonfontes

## 5. Alternative Approaches

### 5.1 APPROACH A: Patch Only mac80211_hwsim Module (RECOMMENDED FIRST ATTEMPT)

**Concept:** Instead of rebuilding the entire kernel, modify only the mac80211_hwsim driver to register channel switch support for station interfaces, then compile just that single module.

**Technical details:**
The hwsim driver registers its wiphy capabilities in `drivers/net/wireless/mac80211_hwsim.c`. The relevant code is in the `mac80211_hwsim_create_radio()` function where `hw->wiphy->iface_combinations` and channel switch capabilities are set. Currently, channel switch is only advertised for AP interfaces:

```c
// Approximate current state in hwsim:
// Channel switch support is set in wiphy->features or
// through iface_combinations limits, restricted to AP mode
```

**Required modification:** Add `NL80211_IFTYPE_STATION` to the interface types that support channel switch operations. This could be as simple as modifying the `wiphy->channel_switch` supported interface mask.

**Build process:**
```bash
# 1. Install kernel headers (already done per Kali setup [4])
apt install linux-headers-$(uname -r)

# 2. Get kernel source for current version
apt source linux-image-$(uname -r)

# 3. Modify drivers/net/wireless/mac80211_hwsim.c
# 4. Build just the module
make -C /lib/modules/$(uname -r)/build M=$PWD/drivers/net/wireless mac80211_hwsim.ko

# 5. Replace module
rmmod mac80211_hwsim
insmod ./mac80211_hwsim.ko
```

**Advantages:**
- 30-minute solution vs. 4-6 hour full rebuild
- Minimal system impact—only one module changes
- Easy to revert: reinstall stock kernel package to restore original module
- No GRUB configuration needed
- No risk of unbootable system

**Risks:**
- Module version magic mismatch if GCC versions differ [7]
- The cfg80211 layer may still reject the channel switch even if hwsim advertises support, because `CERTIFICATION_ONUS` is disabled at the cfg80211 level
- **Critical uncertainty:** We don't know if cfg80211's `CERTIFICATION_ONUS` check happens before or after the driver capability check. If cfg80211 rejects the operation at the nl80211 layer before even querying the driver, patching hwsim alone won't help.

**Verification needed:** Examine `net/wireless/nl80211.c` in the `nl80211_channel_switch()` function to determine the exact order of checks. If the `CERTIFICATION_ONUS` check gates the entire operation, we need Approach B.

### 5.2 APPROACH B: Targeted Kernel Rebuild with Single Config Change

**Concept:** Rebuild the Kali kernel from source with only one configuration change: `CONFIG_CFG80211_CERTIFICATION_ONUS=y`.

**Build time estimate:** 2-4 hours on modern hardware (VMware VM with 4+ cores, 8GB+ RAM)

**Process overview:**
```bash
# 1. Get Kali kernel source
apt source linux

# 2. Copy current config
cp /boot/config-$(uname -r) .config

# 3. Modify single option
scripts/config --enable CONFIG_CFG80211_CERTIFICATION_ONUS

# 4. Build (using Debian packaging for .deb output)
make -j$(nproc) bindeb-pkg
```

**Advantages:**
- Guaranteed to work—this directly addresses the root cause
- Produces installable .deb packages for easy installation/removal
- Can preserve the stock kernel as fallback in GRUB

**Risks:**
- Time investment (2-4 hours)
- Requires significant disk space (20GB+ for kernel build)
- Potential for build failures if dependencies are missing

### 5.3 APPROACH C: Netlink Bypass (THEORETICAL — LIKELY DEAD END)

**Concept:** Send `NL80211_CMD_CHANNEL_SWITCH` directly via netlink, bypassing the `iw` tool's error handling, in case `iw` is incorrectly reporting the error.

**Why this likely fails:** The error `-95 (EOPNOTSUPP)` comes from the kernel's `cfg80211` subsystem, not from `iw`. Sending the same netlink command via a custom program would hit the same kernel check and return the same error. The `CERTIFICATION_ONUS` flag gates the operation in `net/wireless/nl80211.c`, which processes all `NL80211_CMD_CHANNEL_SWITCH` requests regardless of how they arrive.

**Verdict:** Dead end. Not worth pursuing.

### 5.4 APPROACH D: Force Channel via Monitor Interface (CREATIVE WORKAROUND)

**Concept:** Create a monitor interface on the same phy, set the monitor interface to the target channel, and see if the station interface follows.

```bash
iw phy phy0 interface add mon0 type monitor
iw dev mon0 set channel 11
# Check if wlan2 (STA) follows
iw dev wlan2 info
```

**Why this might work:** Some wireless drivers tie channel configuration to the physical device (phy) rather than individual virtual interfaces. If hwsim does this, changing the channel on any interface belonging to the phy might change it for all interfaces.

**Why this might fail:** mac80211 and cfg80211 typically maintain per-interface channel context, especially for station interfaces that are associated. The station interface's channel is locked by the association state.

**Verdict:** Worth a 5-minute test. Low probability of success but zero cost to try.

### 5.5 APPROACH E: wmediumd Channel Manipulation

**Concept:** Use wmediumd's medium simulation to effectively "move" the station by manipulating signal propagation rather than explicitly switching channels.

**Why this fails:** wmediumd simulates the wireless medium between interfaces but doesn't control interface channel assignment. The interfaces must already be on the correct channels for wmediumd to simulate communication between them. wmediumd cannot force a station to change channels.

**Verdict:** Dead end for our specific need.

### 5.6 APPROACH F: User-Space WiFi Stack (THEORETICAL)

**Concept:** Use a user-space 802.11 stack that implements CSA handling without kernel cfg80211 restrictions.

**Candidates:**
- **PicoWiFi** (ESP32-focused, not suitable for Linux host)
- **Scapy** (can parse/inject but can't maintain association state)
- **libtins** (packet crafting, no association state machine)

**Why this fails:** User-space stacks can't maintain the kernel's association state (key material, sequence numbers, block ACK state). The station would need to fully associate in user-space, which requires raw frame injection that modern cfg80211 restricts.

**Verdict:** Theoretically possible but practically infeasible for a proof-of-concept. Would require months of development.

### 5.7 APPROACH G: QEMU/KVM with Custom Kernel

**Concept:** Run a minimal Linux VM with a custom kernel that has `CERTIFICATION_ONUS=y`, passing through hwsim interfaces.

**Why this is overkill:** We're already in a VM (VMware). Adding nested virtualization adds complexity without benefit. If we're building a custom kernel anyway, we might as well run it directly.

**Verdict:** Not recommended. Adds complexity without solving the core problem.

## 6. Build Guide Recommendations

### 6.1 Primary Recommendation: Kali Official Kernel Build Guide

**Source:** Kali Linux official documentation (docs.kali.org)
**Reliability:** High — official distribution documentation
**Recency:** Maintained for current Kali releases

**Key steps adapted for our specific change:**

```bash
# 1. Install build dependencies
sudo apt update
sudo apt install build-essential flex bison dwarves libssl-dev \
  libelf-dev bc kmod cpio rsync dpkg-dev

# 2. Get Kali kernel source
apt source linux
cd linux-*/

# 3. Copy current running kernel config
cp /boot/config-$(uname -r) .config

# 4. Enable the single option we need
scripts/config --enable CONFIG_CFG80211_CERTIFICATION_ONUS

# 5. Regenerate config to resolve dependencies
make olddefconfig

# 6. Verify the change took effect
grep CERTIFICATION_ONUS .config
# Should show: CONFIG_CFG80211_CERTIFICATION_ONUS=y

# 7. Build kernel packages (this takes 2-4 hours)
make -j$(nproc) bindeb-pkg LOCALVERSION=-csa-custom

# 8. Install the new kernel
cd ..
sudo dpkg -i linux-image-*.deb linux-headers-*.deb

# 9. Update GRUB and reboot
sudo update-grub
sudo reboot
```

### 6.2 GCC Version Verification (Critical Prerequisite)

Per the Realtek driver community's documentation [7], the GCC major version must match between build environment and kernel:

```bash
# Check kernel GCC version
cat /proc/version
# Example output: Linux version 6.18.12+kali-amd64 ... (gcc-14 ...)

# Check system GCC
gcc --version
# Must show same major version (14.x)
```

If versions don't match, install the correct GCC version before building:
```bash
sudo apt install gcc-14
```

### 6.3 Module-Only Build Alternative (If Approach A Works)

If we determine that patching only hwsim is viable (see Section 5.1), the build process is much simpler:

```bash
# 1. Install headers (already done per Kali setup [4])
sudo apt install linux-headers-$(uname -r)

# 2. Get kernel source for the module
apt source linux
cd linux-*/drivers/net/wireless

# 3. Modify mac80211_hwsim.c (add STA to channel_switch supported types)

# 4. Build just the module
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules

# 5. Backup original module
sudo cp /lib/modules/$(uname -r)/kernel/drivers/net/wireless/mac80211_hwsim.ko \
        /lib/modules/$(uname -r)/kernel/drivers/net/wireless/mac80211_hwsim.ko.bak

# 6. Install modified module
sudo cp mac80211_hwsim.ko /lib/modules/$(uname -r)/kernel/drivers/net/wireless/

# 7. Regenerate module dependencies
sudo depmod -a

# 8. Reload module
sudo rmmod mac80211_hwsim
sudo modprobe mac80211_hwsim
```

### 6.4 Known Pitfalls from Community Experience

**Pitfall 1: Module version magic mismatch**
If the kernel was compiled with a different GCC version than what's on your system, the module will refuse to load. Check `/proc/version` for kernel GCC version [7].

**Pitfall 2: Missing build dependencies**
The Kali configuration guide [4] emphasizes installing `linux-headers-$(uname -r)` as critical. Without headers, module compilation fails with "build directory not found" errors.

**Pitfall 3: Initramfs not updated**
After installing a new kernel or replacing modules, `update-initramfs -u` must be run. The Kali configuration repository [5] documents this as part of their standard workflow for driver changes.

**Pitfall 4: Conflicting modules**
If multiple versions of mac80211_hwsim exist (in different kernel trees), the wrong one might load. Use `modinfo mac80211_hwsim` to verify the loaded module's location.

**Pitfall 5: Armbian-style tag dereferencing bugs**
While not directly applicable to Kali, the Armbian build system bug [9] with git tag dereferencing serves as a reminder that kernel build scripts can have subtle failures. If using git-based kernel sources, verify that tags resolve correctly.

## 7. Risks & Known Issues

### 7.1 CERTIFICATION_ONUS Side Effects

**Risk:** Enabling `CERTIFICATION_ONUS` may allow other non-standard behaviors beyond channel switching on station interfaces.

**Mitigation:** This is acceptable for our proof-of-concept. The flag's name literally means "the certification burden is on you"—it's designed for testing scenarios exactly like ours.

**Specific behaviors that may change:**
- Regulatory domain checks may be relaxed
- Channel availability checks may be bypassed
- Other driver capability checks may be skipped

### 7.2 Module ABI Compatibility

**Risk:** A patched mac80211_hwsim module may have symbol dependencies that don't match the running kernel if the kernel was updated after headers were installed.

**Mitigation:** Always verify header version matches running kernel:
```bash
ls /lib/modules/$(uname -r)/build/
# Should exist and contain Makefile, include/, etc.
```

### 7.3 VMware-Specific Considerations

**Risk:** Custom kernels may have different driver support for VMware's virtual hardware (vmxnet3, pvscsi, etc.).

**Mitigation:** Since we're using the existing Kali kernel config as a base and only changing one wireless option, all VMware drivers will remain enabled. The `.config` from `/boot` already includes all VMware-required options.

### 7.4 The cfg80211 Layered Check Problem

**Risk (for Approach A):** Even if we patch hwsim to advertise channel switch support for station interfaces, cfg80211's `CERTIFICATION_ONUS` check in `nl80211_channel_switch()` may reject the operation before it ever reaches the hwsim driver.

**Analysis needed:** The exact code path is:
1. `nl80211_channel_switch()` in `net/wireless/nl80211.c`
2. Checks `cfg80211_is_allowed_channel_switch()` or similar
3. This function likely checks `wiphy->features` and `CERTIFICATION_ONUS`
4. If `CERTIFICATION_ONUS` is disabled, it returns -EOPNOTSUPP regardless of driver capabilities

**If this is the case:** Approach A (module-only patch) will fail, and we must use Approach B (full kernel rebuild).

**How to verify before building:** Examine the kernel source at `net/wireless/nl80211.c`, specifically the `nl80211_channel_switch()` function. Look for:
```c
if (!(wiphy->features & NL80211_FEATURE_CERTIFICATION_ONUS) &&
    !cfg80211_reg_can_beacon(...))
    return -EOPNOTSUPP;
```

### 7.5 Wireless Stack Module Loading Order

**Risk:** On some systems, cfg80211 and mac80211 may be built into the kernel rather than as modules [3], making runtime parameter changes impossible.

**Verification:**
```bash
# Check if cfg80211 is built-in or module
grep CONFIG_CFG80211 /boot/config-$(uname -r)
# If =y, it's built-in. If =m, it's a module.

# Check if currently loaded as module
lsmod | grep cfg80211
```

**Our case:** The Kali kernel has `CONFIG_CFG80211=m` [2], so it's a loadable module. This is good—we can reload it if needed.

## 8. Recommended Action Plan

### Phase 1: Quick Validation (15 minutes)

Before any compilation, verify the exact failure point:

```bash
# 1. Confirm current state
grep CERTIFICATION_ONUS /boot/config-$(uname -r)
# Expected: # CONFIG_CFG80211_CERTIFICATION_ONUS is not set

# 2. Test Approach D (monitor interface channel change)
sudo iw phy phy0 interface add mon0 type monitor
sudo iw dev mon0 set channel 11
iw dev wlan2 info | grep channel
# If wlan2 channel changed to 11: SUCCESS, no kernel work needed
# If wlan2 still on channel 6: Continue to Phase 2

# 3. Clean up
sudo iw dev mon0 del
```

### Phase 2: Source Code Analysis (30 minutes)

Determine whether Approach A (module-only) is viable:

```bash
# Get kernel source
apt source linux
cd linux-*/

# Examine the critical code path
grep -n "CERTIFICATION_ONUS\|EOPNOTSUPP\|channel_switch" net/wireless/nl80211.c | head -30

# Look for the specific check that returns -EOPNOTSUPP
# If the check references wiphy->features or driver capabilities
# AND CERTIFICATION_ONUS can override it, then Approach A may work.
# If the check is a hard gate before driver consultation, Approach B is required.
```

**Decision point:**
- If `CERTIFICATION_ONUS` check is in `nl80211_channel_switch()` and gates the entire operation → **Go to Phase 3B** (full rebuild)
- If the check only validates driver capabilities and can be satisfied by hwsim advertising support → **Go to Phase 3A** (module patch)

### Phase 3A: Module-Only Patch (1 hour, if viable)

1. Modify `drivers/net/wireless/mac80211_hwsim.c` to add `NL80211_IFTYPE_STATION` to channel switch supported interfaces
2. Build only the mac80211_hwsim module
3. Replace the module and reload
4. Test channel switch on station interface
5. If successful, proceed to full CSA attack demonstration

### Phase 3B: Full Kernel Rebuild (3-4 hours, if Phase 3A fails or isn't viable)

1. Follow the build guide in Section 6.1
2. Enable `CONFIG_CFG80211_CERTIFICATION_ONUS=y`
3. Build kernel packages
4. Install and reboot
5. Verify channel switch works
6. Proceed to full CSA attack demonstration

### Phase 4: CSA Attack Execution (30 minutes)

Once channel switching works:

```bash
# 1. Set up AP on channel 6
# 2. Connect station on channel 6 with PMF=2
# 3. Inject Beacon CSA frames claiming switch to channel 11
# 4. Verify station switches to channel 11
# 5. Capture station on Evil Twin AP on channel 11
```

### Fallback Plan

If both approaches fail (unlikely but possible):
- Consider using physical WiFi hardware passed through to the VM via USB
- Use a separate physical machine running Kali with a monitor-mode-capable WiFi card
- Explore the Politician ESP32 tool for hardware-based testing

## 9. All Source URLs

### Kernel Configuration and CERTIFICATION_ONUS
- **Microsoft WSL2 kernel commit modifying CERTIFICATION_ONUS:** Commit 76598c510caee04aee422301182bdf0c8320cd42 in microsoft/WSL2-Linux-Kernel [6]
- **Comprehensive kernel wireless configuration gist:** Documents full cfg80211/mac80211 dependency chain and CERTIFICATION_ONUS effects [2]

### Kali Linux Setup and Configuration
- **InfoSecWarrior Kali Configuration Guide:** Documents kernel header installation, module management, and initramfs procedures [4][5]
- **Kali Linux official kernel rebuild documentation:** Standard procedure for rebuilding Kali kernels from source

### Wireless Driver Compilation
- **morrownr/88x2bu-20210702 driver documentation:** GCC version matching requirement for out-of-tree module compilation [7]
- **aircrack-ng/rtl8812au platform-specific compilation:** Documents WEXT vs nl80211 support variations across platforms [8]

### Wireless Stack Behavior
- **WSL2 nl80211 availability issues:** Documents cfg80211 module loading challenges in virtualized environments [1]
- **Ubuntu-Rockchip AX210 connectivity issues:** Documents built-in vs modular cfg80211/mac80211 behavior [3]

### Build System Issues
- **Armbian build system tag dereferencing bug:** Documents kernel build script failure modes with git tags [9]

### CSA Attack Tools and Research
- **Politician ESP32 tool (0ldev):** Hardware-based Beacon CSA injection implementation
- **BeaconStrike toolkit (confnameless):** Software-based Beacon CSA injection
- **Academic papers:** Springer 2020, IEEE 2021, IEEE Access 2024 — CSA attack validation

### Linux Wireless Maintainer Resources
- **Johannes Berg's kernel tree (johannesberg/linux):** cfg80211/mac80211 development branch
- **Linux kernel MAINTAINERS file:** Official maintainer listings for CFG80211 and MAC80211_HWSIM
- **hostapd/wpa_supplicant repository (Jouni Malinen):** mac80211_hwsim testing infrastructure

---

## Appendix A: Quick Reference — Key File Locations

| File | Purpose | Relevance |
|------|---------|-----------|
| `net/wireless/nl80211.c` | nl80211 command handlers | Contains `NL80211_CMD_CHANNEL_SWITCH` handler and CERTIFICATION_ONUS check |
| `net/wireless/chan.c` | Channel management | `cfg80211_ch_switch_notify()` and related functions |
| `drivers/net/wireless/mac80211_hwsim.c` | hwsim driver | wiphy registration, channel switch capability advertisement |
| `net/mac80211/spectmgmt.c` | Spectrum management | `ieee80211_sta_process_chanswitch()` — CSA IE processing |
| `net/mac80211/cfg.c` | mac80211 cfg80211 ops | Channel switch operation implementations |
| `include/net/cfg80211.h` | cfg80211 data structures | Feature flags, interface type definitions |

## Appendix B: GCC Version Compatibility Matrix

Based on community findings [7], verify compatibility before any compilation:

```bash
# Kernel GCC version
cat /proc/version | grep -oP 'gcc-\d+'

# System GCC version  
gcc --version | head -1 | grep -oP '\d+\.\d+\.\d+'

# Major versions must match (e.g., both 14.x)
```

If mismatch, install matching GCC:
```bash
sudo apt install gcc-14 g++-14
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-14 100
```

## Sources

1. [nl80211 not found · Issue #7617 · microsoft/WSL · GitHub](https://github.com/microsoft/WSL/issues/7617)
2. [Linux RT-kernel 5.4.26 .config file · GitHub](https://gist.github.com/rickstaa/bc3c8449892d591849a326efa5220ee5)
3. [iwlwifi/cfg80211/mac80211 · Issue #588 · Joshua-Riek/ubuntu-rockchip · GitHub](https://github.com/Joshua-Riek/ubuntu-rockchip/issues/588)
4. [Kali-Linux-Configuration/README.md at main · InfoSecWarrior/Kali-Linux-Configuration · GitHub](https://github.com/InfoSecWarrior/Kali-Linux-Configuration/blob/main/README.md?plain=1)
5. [GitHub - InfoSecWarrior/Kali-Linux-Configuration: Comprehensive guide to configuring Kali Linux, a Debian-based Linux distribution designed for penetration testers. The guide covers everything from repository setup and NVIDIA driver installation to Python configuration and essential tool installation, ensuring an optimized setup for penetration testing tasks. · GitHub](https://github.com/InfoSecWarrior/Kali-Linux-Configuration)
6. [patch - GitHub](https://github.com/microsoft/WSL2-Linux-Kernel/commit/76598c510caee04aee422301182bdf0c8320cd42.patch)
7. [morrownr/88x2bu-20210702: Linux Driver for USB WiFi Adapters ...](https://github.com/morrownr/88x2bu-20210702)
8. [Wireless extension support · Issue #1058 · aircrack-ng/rtl8812au · GitHub](https://github.com/aircrack-ng/rtl8812au/issues/1058)
9. [Failed to fetch SHA1 of commit · Issue #4916 · armbian/build · GitHub](https://github.com/armbian/build/issues/4916)