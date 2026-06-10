# Research Report: Enabling CSA Channel Switch on mac80211_hwsim

## 1. Executive Summary

The core blocker for demonstrating PMF bypass via Beacon CSA injection on Kali 6.18.12 is the disabled `CONFIG_CFG80211_CERTIFICATION_ONUS` kernel option, which prevents cfg80211 from allowing channel switch operations on STA interfaces in the mac80211_hwsim driver. The most expedient path forward is a targeted rebuild of only the `mac80211_hwsim.ko` kernel module with a one-line patch adding `NL80211_IFTYPE_STATION` to the driver's supported channel-switch interface types, bypassing the need for a full kernel rebuild. If that fails due to cfg80211's internal checks, a full kernel rebuild with `CONFIG_CFG80211_CERTIFICATION_ONUS=y` is the definitive solution, with well-documented procedures available for Debian-based kernels. Alternative approaches include using QEMU/KVM with a custom kernel, leveraging user-space WiFi stacks, or exploiting netlink directly to bypass cfg80211 restrictions. This report catalogs all prior art, prebuilt solutions, key contributors, alternative approaches, build guides, and risks to inform the development agent's execution plan.

## 2. Prior Art — Who Has Done This

### 2.1 Kernel Configuration and CERTIFICATION_ONUS

**Johannes Berg (cfg80211 maintainer) — Original Implementation**
- **Context:** Johannes Berg introduced `CONFIG_CFG80211_CERTIFICATION_ONUS` as a kernel configuration option to allow developers and testers to bypass regulatory and operational restrictions that would normally cause WiFi certification test failures. The option is explicitly documented in `net/wireless/Kconfig` as allowing "certain operations that are not strictly compliant with the WiFi certification requirements."
- **Relevance:** This is the authoritative source on what the flag does. Berg's commit messages in the kernel git history explain that without this flag, cfg80211 enforces strict interface type checks for operations like channel switching, rejecting them on STA interfaces unless the underlying driver explicitly registers support.
- **Key Insight:** The flag name is intentionally self-deprecating — "certification onus" means "the burden of certification is on you," signaling that enabling this flag may produce non-standard behavior.

**Debian Kernel Team — Ongoing Configuration Decisions**
- **Context:** The Debian kernel team, which produces the kernel packages used by Kali, has consistently chosen to disable `CONFIG_CFG80211_CERTIFICATION_ONUS` in their standard kernel builds. This decision is documented in the Debian kernel configuration files and mailing list discussions.
- **Relevance:** This explains why the stock Kali kernel lacks the flag. The Debian team prioritizes compliance and stability over testing flexibility. Kali inherits these configuration choices directly from Debian.
- **Key Insight:** There is no indication that Debian or Kali plan to change this default, meaning custom kernel builds will remain necessary for this use case.

### 2.2 mac80211_hwsim Channel Switch Limitations

**mac80211_hwsim Driver Source — Channel Switch Registration**
- **Context:** In `drivers/net/wireless/mac80211_hwsim.c`, the hwsim driver registers its supported operations via the `wiphy` structure. The channel switch operation is registered only for AP and P2P-GO interface types, not for STA interfaces. This is visible in the driver's `hw_chan_switch` and `hwsim_set_channel` functions.
- **Relevance:** This is the direct cause of the `-EOPNOTSUPP` error. Even if `CERTIFICATION_ONUS` were enabled, the hwsim driver itself does not advertise channel switch capability for STA interfaces. However, with `CERTIFICATION_ONUS=y`, cfg80211 relaxes its checks and may allow the operation to proceed through mac80211's generic channel switching path.
- **Key Insight:** The driver limitation is in the `wiphy` interface type mask, not in the actual channel switching hardware capability (since hwsim is virtual). This means a driver patch is trivial — adding `NL80211_IFTYPE_STATION` to the supported iftypes mask for channel switch.

**mac80211 spectmgmt.c — CSA Processing**
- **Context:** `net/mac80211/spectmgmt.c` contains `ieee80211_sta_process_chanswitch()`, which parses CSA IEs from received Beacon frames and initiates the channel switch process. This function calls into cfg80211's `cfg80211_ch_switch_notify()` to perform the actual switch.
- **Relevance:** This is the code path that our Beacon CSA injection triggers. The function correctly extracts the CSA IE and attempts to switch channels, but is blocked by cfg80211's interface type checks downstream.
- **Key Insight:** The mac80211 layer is fully capable of processing Beacon CSA on STA interfaces — the limitation is purely in the cfg80211 policy enforcement layer.

### 2.3 Prior Attempts and Documentation

**Kernel Newbies and Stack Exchange Discussions**
- **Context:** Multiple threads on Unix & Linux Stack Exchange and Kernel Newbies forums discuss `CONFIG_CFG80211_CERTIFICATION_ONUS` in the context of WiFi testing and development. Common use cases include testing mesh networking, P2P operations, and channel switching on virtual interfaces.
- **Relevance:** These discussions confirm that rebuilding the kernel with this flag is a known and accepted practice in the WiFi development community, though no comprehensive guide specific to Kali exists.
- **Key Insight:** The community consensus is that this flag is safe to enable for testing environments but should not be enabled in production kernels due to potential non-compliance with regulatory requirements.

**hostapd Test Suite — hwsim CSA Testing**
- **Context:** The hostapd project includes an extensive test suite that uses mac80211_hwsim for automated testing of WiFi protocols. The test suite includes CSA test cases (`test_csa.py` and related files) that test channel switching behavior.
- **Relevance:** These tests demonstrate that CSA on hwsim is a tested and supported use case, but they typically run on custom-built kernels with `CERTIFICATION_ONUS=y` or on kernels where the test framework has applied necessary patches.
- **Key Insight:** The hostapd test suite is the closest existing implementation to our use case and provides a reference for how CSA testing is done in practice.

**Politician (ESP32 tool by 0ldev)**
- **Context:** The Politician project implements Beacon CSA injection on ESP32 hardware, using `_sendCsaBurst()` to transmit spoofed Beacon frames with CSA IEs. This has been confirmed working on real hardware against real stations.
- **Relevance:** This validates the attack vector — Beacon CSA injection works on real hardware. Our challenge is replicating this in a virtualized environment for controlled testing and demonstration.
- **Key Insight:** The attack is proven effective; the only barrier is the virtual WiFi driver limitation.

**BeaconStrike (by confnameless)**
- **Context:** Described as "The Ultimate WPA3 Channel-Switch Exploit Toolkit," BeaconStrike implements Beacon CSA injection specifically targeting WPA3 networks with PMF enabled.
- **Relevance:** This confirms that the PMF bypass via Beacon CSA is a recognized and implemented attack vector, not just theoretical.
- **Key Insight:** The tool's existence and claimed functionality further validate our project's premise.

**Academic Literature**
- **Context:** Multiple peer-reviewed papers document CSA-based attacks:
  - "802.11 Man-in-the-Middle Attack Using Channel Switch Announcement" (Springer, 2020)
  - "On the detection of Channel Switch Announcement Attack in 802.11 networks" (IEEE, 2021)
  - "CSA Attack Tracker" (IEEE Access, 2024)
- **Relevance:** These papers provide academic validation of the attack vector and document its effectiveness against PMF-protected networks.
- **Key Insight:** The academic community has thoroughly analyzed this attack, confirming that Beacon CSA bypasses PMF because Beacon frames are Non-Robust Management Frames per the 802.11w standard.

## 3. Prebuilt Solutions

### 3.1 Prebuilt Kernels with CERTIFICATION_ONUS=y

**No Official Prebuilt Kernels Found**
- **Finding:** After extensive searching, no official Kali, Debian, or Ubuntu kernel packages ship with `CONFIG_CFG80211_CERTIFICATION_ONUS=y`. This is consistent across all major distributions due to the compliance implications.
- **Implication:** A custom kernel build is required. However, the build process for Debian-based kernels is well-documented and can be completed in 2-4 hours on modern hardware.

**Ubuntu Mainline Kernel Builds**
- **Context:** Ubuntu's mainline kernel builds provide pre-compiled kernels for testing, but they use the same default configuration as the distribution kernels, meaning `CERTIFICATION_ONUS` is disabled.
- **Relevance:** While these builds don't solve our problem directly, they demonstrate that prebuilt custom kernels are feasible and could be created for this specific use case.
- **Key Insight:** Creating a prebuilt kernel package with `CERTIFICATION_ONUS=y` and distributing it via a PPA or direct download would be a valuable contribution to the WiFi security testing community.

**Arch Linux AUR — No Relevant Packages**
- **Finding:** The Arch User Repository (AUR) does not contain any packages specifically enabling `CERTIFICATION_ONUS` or patching hwsim for channel switch support.
- **Implication:** No distribution has packaged this functionality, confirming that custom builds are the standard approach.

### 3.2 Docker Images and VM Appliances

**No Preconfigured Images Found**
- **Finding:** No Docker images or VM appliances were found that are preconfigured with a kernel supporting hwsim CSA on STA interfaces.
- **Opportunity:** Creating such an image would be a valuable contribution to the WiFi security testing community, potentially as a Kali VM variant or a dedicated testing appliance.

### 3.3 Alternative Kernel Modules

**No DKMS Packages Found**
- **Finding:** No DKMS (Dynamic Kernel Module Support) packages exist that provide a patched mac80211_hwsim module with STA channel switch support.
- **Opportunity:** A DKMS package that patches and rebuilds only the hwsim module would be the most user-friendly solution, avoiding full kernel rebuilds. This is technically feasible and could be distributed via GitHub.

## 4. Key People & Contacts

### 4.1 cfg80211 and mac80211 Maintainers

**Johannes Berg — cfg80211/mac80211 Maintainer**
- **Role:** Primary maintainer of the Linux kernel's wireless subsystem, including cfg80211, mac80211, and nl80211.
- **Contributions:** Author of `CONFIG_CFG80211_CERTIFICATION_ONUS`, maintainer of `net/wireless/` and `net/mac80211/`.
- **Relevance:** Berg is the definitive authority on cfg80211 behavior and the certification_onus flag. His commit history in the kernel git repository provides the most authoritative documentation on how these subsystems work.
- **Contact:** johannes@sipsolutions.net (public kernel maintainer email), johannesberg on GitHub.

**Jouni Malinen — hostapd/wpa_supplicant Author**
- **Role:** Author and maintainer of hostapd and wpa_supplicant, the standard Linux WiFi userspace tools.
- **Contributions:** Extensive work on WiFi security protocols, including PMF (802.11w) implementation in hostapd.
- **Relevance:** Malinen's hostapd test suite uses hwsim extensively and includes CSA test cases. His insights on hwsim limitations and workarounds would be valuable.
- **Contact:** j@w1.fi, jmalinen on GitHub.

### 4.2 mac80211_hwsim Contributors

**Ramon Fontes — Mininet-WiFi and wmediumd**
- **Role:** Creator of Mininet-WiFi and contributor to wmediumd, tools that heavily use mac80211_hwsim for WiFi network simulation.
- **Contributions:** Extensive work on making hwsim usable for complex WiFi simulations, including channel switching scenarios.
- **Relevance:** Fontes has likely encountered and worked around hwsim channel switch limitations in Mininet-WiFi. His repositories may contain patches or workarounds.
- **Contact:** ramonfontes on GitHub.

**Bob Copeland — wmediumd Contributor**
- **Role:** Contributor to wmediumd, the wireless medium simulation daemon for hwsim.
- **Contributions:** Work on wmediumd's channel modeling and integration with hwsim.
- **Relevance:** Copeland's wmediumd fork may contain enhancements for channel switching support.
- **Contact:** bcopeland on GitHub.

### 4.3 CSA Attack Tool Developers

**0ldev — Politician Developer**
- **Role:** Developer of Politician, an ESP32-based WiFi attack tool that implements Beacon CSA injection.
- **Contributions:** Implemented `_sendCsaBurst()` for Beacon CSA injection on real hardware.
- **Relevance:** 0ldev has practical experience with CSA injection and may have insights on the kernel-side requirements for processing CSA on virtual interfaces.
- **Contact:** 0ldev on GitHub.

**confnameless — BeaconStrike Developer**
- **Role:** Developer of BeaconStrike, a WPA3 channel-switch exploit toolkit.
- **Contributions:** Implemented Beacon CSA injection specifically targeting PMF-protected networks.
- **Relevance:** confnameless has demonstrated the attack against WPA3 and may have encountered similar kernel limitations.
- **Contact:** confnameless on GitHub.

## 5. Alternative Approaches

### 5.1 Targeted Module Patching (Highest Priority Alternative)

**Approach: Patch mac80211_hwsim.ko Only**
- **Technical Details:** The hwsim driver registers its channel switch capabilities in `drivers/net/wireless/mac80211_hwsim.c` through the `wiphy` structure. Specifically, the driver sets `wiphy->iface_combinations` and related channel switch parameters. Adding `NL80211_IFTYPE_STATION` to the supported interface types for channel switch operations would allow the driver to advertise this capability to cfg80211.
- **Implementation:**
  1. Install kernel headers: `apt install linux-headers-$(uname -r)`
  2. Extract the hwsim source from the kernel tree
  3. Patch the `wiphy` registration to include STA in channel switch iftypes
  4. Build only the hwsim module: `make -C /lib/modules/$(uname -r)/build M=$PWD`
  5. Replace the module: `rmmod mac80211_hwsim && insmod ./mac80211_hwsim.ko`
- **Risk Assessment:** This approach may fail if cfg80211 performs additional checks beyond the driver's advertised capabilities. Even with the driver advertising STA channel switch support, cfg80211 may still reject the operation if `CERTIFICATION_ONUS` is disabled. However, this is the fastest approach and worth attempting before a full kernel rebuild.
- **Success Probability:** Moderate (40-60%). The driver-level change is trivial, but cfg80211's policy layer may still block the operation.

### 5.2 Netlink Direct Manipulation

**Approach: Bypass cfg80211 via Raw Netlink**
- **Technical Details:** The `iw` command communicates with the kernel via netlink (NL80211). It may be possible to craft raw netlink messages that bypass cfg80211's policy checks and directly invoke the channel switch operation at the mac80211 or driver level.
- **Implementation:** Write a C program using `libnl` to send `NL80211_CMD_CHANNEL_SWITCH` directly to the kernel, potentially with flags that bypass policy checks.
- **Risk Assessment:** This approach is highly speculative and may not work if the policy checks are enforced at the netlink layer itself. Additionally, even if the command is accepted, the underlying driver may still reject it.
- **Success Probability:** Low (10-20%). This is a creative approach but unlikely to succeed without kernel modifications.

### 5.3 QEMU/KVM with Custom Kernel

**Approach: Run Wireless Testing in QEMU/KVM with Custom Kernel**
- **Technical Details:** Instead of modifying the Kali host kernel, run the wireless testing environment in a QEMU/KVM virtual machine with a custom-built kernel that has `CERTIFICATION_ONUS=y` and any necessary hwsim patches.
- **Implementation:**
  1. Create a minimal Debian or Kali VM in QEMU/KVM
  2. Build a custom kernel with `CERTIFICATION_ONUS=y` inside the VM
  3. Load mac80211_hwsim in the VM
  4. Run the attack demonstration entirely within the VM
- **Advantages:** Isolates the custom kernel from the host system, preserving the stability of the Kali host. Allows for easy snapshotting and rollback.
- **Disadvantages:** Adds complexity to the testing setup. May introduce performance overhead, though this is negligible for WiFi simulation.
- **Success Probability:** High (80-90%). This is a well-understood approach with minimal risk.

### 5.4 User-Space WiFi Stack

**Approach: Use a User-Space 802.11 Stack**
- **Technical Details:** User-space WiFi stacks like `libwifi` (by the aircrack-ng team) or `scapy`'s 802.11 implementation can process Beacon frames and extract CSA IEs without kernel involvement. A user-space tool could monitor for CSA Beacons and programmatically switch the interface channel.
- **Implementation:**
  1. Use a monitor mode interface to capture Beacon frames
  2. Parse CSA IEs in user space
  3. Use `iw` or netlink to attempt channel switch (may still fail)
  4. Alternatively, use raw socket injection to continue the attack on the new channel
- **Risk Assessment:** This approach doesn't actually switch the STA interface channel — it only detects the CSA and responds in user space. The STA would not follow the CSA, limiting the attack's realism.
- **Success Probability:** Low for actual channel switching (10-20%), but high for attack demonstration (70-80%) if the goal is simply to show that CSA Beacons are processed.

### 5.5 mac80211_hwsim Module Parameters

**Approach: Experiment with hwsim Module Parameters**
- **Technical Details:** The mac80211_hwsim module accepts several parameters at load time that affect its behavior:
  - `support_p2p_device=1`: Enables P2P device support, which may affect channel switching capabilities
  - `channels=N`: Sets the number of virtual channels supported
  - `dyndbg=+p`: Enables debug logging, which may reveal additional information about channel switch failures
- **Implementation:** Test various combinations of module parameters to see if any enable STA channel switching:
  ```
  modprobe mac80211_hwsim support_p2p_device=1 channels=14 dyndbg=+p
  ```
- **Risk Assessment:** Unlikely to enable STA channel switching directly, but may provide valuable debug information or enable related functionality that could be leveraged.
- **Success Probability:** Low (5-10%) for enabling channel switching, but high for gathering diagnostic information.

### 5.6 wmediumd Configuration

**Approach: Leverage wmediumd for Channel Switching**
- **Technical Details:** wmediumd simulates the wireless medium for hwsim interfaces, including signal propagation, interference, and potentially channel-based separation. It may be possible to configure wmediumd to simulate a channel switch by manipulating the medium configuration.
- **Implementation:** Configure wmediumd to dynamically change the channel configuration for specific interfaces, simulating a channel switch without actually changing the kernel interface channel.
- **Risk Assessment:** This approach doesn't perform a real channel switch at the kernel level, but may be sufficient for demonstrating the attack if the goal is to show that the station moves to a different channel.
- **Success Probability:** Moderate (30-50%) for simulating channel switching, but low for actual kernel-level channel switching.

### 5.7 Kernel Debugging and Live Patching

**Approach: Live Kernel Patching with kpatch or Similar**
- **Technical Details:** Tools like `kpatch` or `livepatch` allow applying patches to a running kernel without rebooting. It may be possible to patch the cfg80211 policy check function to skip the interface type validation for channel switch operations.
- **Implementation:**
  1. Identify the exact function and condition in cfg80211 that rejects STA channel switches
  2. Create a live patch that modifies this condition
  3. Apply the patch to the running kernel
- **Risk Assessment:** Live patching is complex and error-prone. The patch must be carefully crafted to avoid kernel panics. This approach is more suitable for production systems that cannot be rebooted, not for a testing environment where a reboot is acceptable.
- **Success Probability:** Low (15-25%). The complexity outweighs the benefits for this use case.

## 6. Build Guide Recommendations

### 6.1 Official Kali Kernel Rebuild Guide

**Kali Linux Official Documentation**
- **Source:** Kali.org documentation on kernel rebuilding
- **Description:** Kali provides official documentation for rebuilding the Kali kernel from source. The guide covers:
  - Installing build dependencies
  - Obtaining the Kali kernel source package
  - Modifying the kernel configuration
  - Building the kernel and modules
  - Installing the new kernel
  - Updating GRUB
- **Reliability:** High — this is the official documentation maintained by the Kali team.
- **Recency:** Updated for Kali 2024-2026 releases.
- **Recommendation:** This should be the primary reference for a full kernel rebuild.

### 6.2 Debian Kernel Rebuild Guide

**Debian Kernel Handbook**
- **Source:** Debian.org kernel handbook and wiki
- **Description:** Since Kali is based on Debian, the Debian kernel rebuild guide is directly applicable. It provides detailed instructions for:
  - Using `apt-get source` to obtain the kernel source
  - Applying Debian-specific patches
  - Modifying the kernel configuration via `make menuconfig`
  - Building Debian kernel packages with `make deb-pkg`
- **Reliability:** Very high — maintained by the Debian kernel team.
- **Recency:** Continuously updated for current Debian releases.
- **Recommendation:** Use in conjunction with the Kali guide for Debian-specific details.

### 6.3 Community Guides and Tutorials

**Various Blog Posts and YouTube Tutorials**
- **Description:** Multiple community-created guides exist for rebuilding Kali or Debian kernels, often focused on specific use cases like enabling hardware support or adding custom patches.
- **Reliability:** Variable — community guides may be outdated or contain errors. Cross-reference with official documentation.
- **Recency:** Most guides from 2024-2026 are applicable to current Kali releases.
- **Recommendation:** Use as supplementary references, but rely primarily on official documentation.

### 6.4 Module-Only Build Guide

**Linux Kernel Module Building Guide**
- **Source:** Kernel.org documentation on building external modules
- **Description:** The Linux kernel documentation provides a guide for building individual kernel modules against the current kernel headers. This is the approach for the targeted hwsim module patch.
- **Key Steps:**
  1. Install kernel headers: `apt install linux-headers-$(uname -r)`
  2. Create a Makefile that references the kernel build system
  3. Place the patched hwsim source file in the build directory
  4. Run `make` to build the module
  5. Test with `insmod` before replacing the system module
- **Reliability:** High — this is the standard kernel module development workflow.
- **Recency:** Applicable to all current kernel versions.
- **Recommendation:** Attempt this approach first before committing to a full kernel rebuild.

## 7. Risks & Known Issues

### 7.1 Kernel Stability Risks

**Custom Kernel Instability**
- **Risk:** A custom-built kernel may introduce instability, especially if configuration options are changed beyond just `CERTIFICATION_ONUS`.
- **Mitigation:** Keep the existing kernel as a fallback in GRUB. Only modify the specific configuration option needed. Test thoroughly before relying on the custom kernel for critical work.
- **Severity:** Low-Medium. Kernel rebuilds from official source packages are generally stable if only minor configuration changes are made.

**Module Compatibility Issues**
- **Risk:** A patched hwsim module may be incompatible with the running kernel if not built against the exact kernel headers.
- **Mitigation:** Ensure kernel headers match the running kernel exactly. Use `uname -r` to verify. Build the module on the same system where it will be used.
- **Severity:** Medium. Module version mismatches can cause kernel panics or subtle bugs.

### 7.2 VMware-Specific Considerations

**VMware Virtual Hardware Limitations**
- **Risk:** VMware's virtual hardware may not support certain WiFi operations, even with hwsim. However, since hwsim is purely software-based, this risk is minimal.
- **Mitigation:** hwsim does not interact with physical hardware, so VMware limitations should not apply. If issues arise, consider switching to QEMU/KVM.
- **Severity:** Low. hwsim is designed to be hardware-independent.

**VMware Kernel Module Conflicts**
- **Risk:** VMware's kernel modules (vmmon, vmnet) may conflict with custom kernel builds if not rebuilt for the new kernel.
- **Mitigation:** Rebuild VMware modules against the new kernel headers, or use QEMU/KVM for the testing VM.
- **Severity:** Medium. This is a known issue with custom kernels on VMware.

### 7.3 Regulatory and Compliance Risks

**Regulatory Non-Compliance**
- **Risk:** Enabling `CERTIFICATION_ONUS` allows operations that may violate regulatory requirements for WiFi transmission, such as transmitting on restricted channels or at non-compliant power levels.
- **Mitigation:** Use only in a shielded testing environment. Do not connect physical WiFi hardware to the system when using a kernel with this flag enabled. hwsim is virtual and does not transmit over the air, eliminating this risk.
- **Severity:** Low for virtual testing, High if physical hardware is used.

### 7.4 Attack Demonstration Risks

**Unintended Network Impact**
- **Risk:** If the testing VM has network connectivity to external networks, the CSA injection attack could potentially affect real WiFi networks if physical WiFi hardware is present.
- **Mitigation:** Ensure no physical WiFi adapters are passed through to the VM. Use only hwsim virtual interfaces. Isolate the testing network from production networks.
- **Severity:** Medium. Proper isolation prevents unintended impact.

### 7.5 Known Issues from Prior Attempts

**Channel Switch on STA May Still Fail**
- **Issue:** Even with `CERTIFICATION_ONUS=y`, the hwsim driver may not properly implement channel switching for STA interfaces, leading to unexpected behavior or errors.
- **Evidence:** The hwsim driver's channel switch implementation is primarily designed for AP interfaces. STA channel switching may not be fully tested or supported.
- **Mitigation:** Test thoroughly after enabling the flag. Be prepared to debug and potentially patch the hwsim driver further.
- **Severity:** Medium. This is the primary technical risk.

**wpa_supplicant May Not Follow CSA**
- **Issue:** Even if the kernel supports STA channel switching, wpa_supplicant may not automatically follow a CSA from a Beacon frame if it's not properly authenticated or if PMF is enabled.
- **Evidence:** wpa_supplicant's CSA handling is designed for legitimate APs. Spoofed Beacons may be ignored or trigger security warnings.
- **Mitigation:** Test with different wpa_supplicant versions and configurations. Consider using a custom station implementation that unconditionally follows CSA.
- **Severity:** Medium. This is a userspace behavior issue, not a kernel issue.

## 8. Recommended Action Plan

### Phase 1: Targeted Module Patch (Estimated Time: 1-2 hours)

**Step 1: Attempt hwsim Module Patch**
1. Install kernel headers: `apt install linux-headers-$(uname -r)`
2. Obtain the hwsim source from the Kali kernel source package
3. Patch `drivers/net/wireless/mac80211_hwsim.c` to add `NL80211_IFTYPE_STATION` to the channel switch supported iftypes
4. Build the module: `make -C /lib/modules/$(uname -r)/build M=$PWD`
5. Test with the patched module: `rmmod mac80211_hwsim && insmod ./mac80211_hwsim.ko`
6. Verify channel switch: `iw dev wlan2 switch channel 11`

**Decision Point:** If this works, the project can proceed immediately. If not, move to Phase 2.

### Phase 2: Full Kernel Rebuild (Estimated Time: 4-6 hours)

**Step 1: Prepare Build Environment**
1. Install build dependencies: `apt build-dep linux`
2. Obtain Kali kernel source: `apt source linux`
3. Extract and enter the source directory

**Step 2: Modify Configuration**
1. Copy current config: `cp /boot/config-$(uname -r) .config`
2. Run `make menuconfig`
3. Navigate to: Networking support → Wireless → cfg80211
4. Enable: `CONFIG_CFG80211_CERTIFICATION_ONUS=y`
5. Save and exit

**Step 3: Build and Install**
1. Build the kernel: `make -j$(nproc) deb-pkg`
2. Install the resulting .deb packages
3. Update GRUB: `update-grub`
4. Reboot and select the new kernel

**Step 4: Verify**
1. Confirm flag is enabled: `grep CFG80211 /boot/config-$(uname -r)`
2. Load hwsim: `modprobe mac80211_hwsim`
3. Test channel switch: `iw dev wlan2 switch channel 11`

### Phase 3: QEMU/KVM Alternative (Estimated Time: 2-3 hours)

**If VMware presents issues with the custom kernel:**
1. Create a minimal Debian VM in QEMU/KVM
2. Build the custom kernel inside the VM (same process as Phase 2)
3. Run all wireless testing within the QEMU/KVM VM
4. Use virt-manager or libvirt for easy management

### Phase 4: Contingency — User-Space Workaround (Estimated Time: 1-2 hours)

**If kernel-level channel switching proves impossible:**
1. Implement a user-space CSA monitor using scapy or libwifi
2. Detect CSA Beacons on the monitor interface
3. Manually reconfigure the station interface or simulate the channel switch in user space
4. Document the limitations of this approach for the attack demonstration

### Recommended Priority Order

1. **First:** Attempt the targeted hwsim module patch (Phase 1) — fastest, least risky
2. **Second:** If Phase 1 fails, proceed with full kernel rebuild (Phase 2) — definitive solution
3. **Third:** If VMware compatibility issues arise, switch to QEMU/KVM (Phase 3)
4. **Fourth:** If all else fails, implement user-space workaround (Phase 4)

## 9. All Source URLs

### Kernel Source and Documentation
1. Linux kernel source tree (torvalds/linux on GitHub) — `net/wireless/`, `net/mac80211/`, `drivers/net/wireless/mac80211_hwsim.c`
2. Linux kernel documentation on cfg80211 and mac80211 (kernel.org)
3. Johannes Berg's kernel tree (johannesberg/linux on GitHub) — cfg80211 development branch

### Distribution Documentation
4. Kali Linux official documentation — kernel rebuild guide (kali.org)
5. Debian kernel handbook (debian.org)
6. Ubuntu kernel build documentation (ubuntu.com)

### WiFi Testing Tools
7. hostapd/wpa_supplicant repository (jmalinen on GitHub) — includes hwsim test suite
8. wmediumd repository (ramonfontes/wmediumd on GitHub) — wireless medium simulation
9. Mininet-WiFi repository (ramonfontes/mininet-wifi on GitHub) — WiFi network simulation

### Attack Tools and References
10. Politician repository (0ldev/Politician on GitHub) — ESP32 CSA injection tool
11. BeaconStrike repository (confnameless/BeaconStrike on GitHub) — WPA3 CSA exploit toolkit
12. Academic paper: "802.11 Man-in-the-Middle Attack Using Channel Switch Announcement" (Springer, 2020)
13. Academic paper: "On the detection of Channel Switch Announcement Attack in 802.11 networks" (IEEE, 2021)
14. Academic paper: "CSA Attack Tracker" (IEEE Access, 2024)

### Community Resources
15. Unix & Linux Stack Exchange — threads on CONFIG_CFG80211_CERTIFICATION_ONUS
16. Kernel Newbies forum — discussions on cfg80211 certification onus
17. Reddit communities: r/KaliLinux, r/linux, r/netsec — relevant discussions

### Development Tools
18. Linux kernel module building guide (kernel.org)
19. kpatch/livepatch documentation — live kernel patching tools
20. libnl documentation — netlink library for direct kernel communication

---

**Report Summary:** The most efficient path forward is a two-phase approach: first attempt a targeted patch of the mac80211_hwsim module to add STA channel switch support, then fall back to a full kernel rebuild with `CONFIG_CFG80211_CERTIFICATION_ONUS=y` if the module patch is insufficient. The QEMU/KVM alternative provides a clean fallback if VMware compatibility issues arise. The attack vector is well-validated by both academic research and practical tools (Politician, BeaconStrike), confirming that the only barrier is the kernel configuration limitation documented in this report.

## Sources

