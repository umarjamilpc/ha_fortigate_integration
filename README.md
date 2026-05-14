<p align="center">
  <img src="https://raw.githubusercontent.com/umarjamilpc/ha_fortigate_integration/main/logo.png" width="140" alt="Fortinet logomark" />
</p>

# FortiGate for Home Assistant

Custom integration for **Fortinet FortiGate** firewalls using the FortiOS **JSON REST API** (token authentication, VDOM-aware, dynamic interfaces, optional SD-WAN and CMDB interface controls).

**Install via [HACS](https://www.hacs.xyz/)** (recommended) or manual copy of `custom_components/fortigate`.

HACS and Home Assistant expect brand images under **`custom_components/fortigate/brand/`** (see [HACS integration requirements](https://hacs.xyz/docs/publish/integration/) and [Home Assistant brand images](https://developers.home-assistant.io/docs/creating_integration_file_structure#brand-images---brand)). This repository ships **`brand/icon.png`** (and `brand/dark_icon.png`, `brand/logo.png`) so the Fortinet mark can appear in the HACS list and in **Settings → Devices & services** after installation. A legacy **`icon.png`** next to `manifest.json` is kept for compatibility with older layouts.

---

## Part A — FortiGate (API user and token)

Complete these steps on the FortiGate GUI (or an equivalent path on your firmware build).

### Step A1 — Network access

1. From the Home Assistant host, confirm you can reach the FortiGate management URL over **HTTPS** (default port **443**, or your custom port).
2. If you use a **private CA** or **self-signed** certificate, note that you can disable SSL verification in the integration (less secure; prefer importing the CA on Home Assistant when possible).

### Step A2 — Create a REST API administrator

1. Log in to the FortiGate as an admin.
2. Go to **System** → **Administrators**.
3. Click **Create New** → **REST API Administrator** (wording may vary slightly by FortiOS version).
4. Set a **username** (for your own records; authentication uses the **API key**).
5. Assign an **admin profile** with the minimum rights below (or a read-only super admin for lab use).

### Step A3 — Permissions (least privilege)

| Goal | Typical access |
|------|----------------|
| Sensors (CPU, memory, sessions, firmware, interfaces, Mbps) | **Read** on **System** and **Network** (monitor endpoints). |
| **SD-WAN** health sensors | **Read** access so `monitor/virtual-wan/health-check` succeeds. |
| **Interface admin switches** (bring interface up/down) | **Read/Write** on **Network** / **Interface** (CMDB `system/interface`). |

If a call is denied, FortiGate returns **401/403** — widen read access first, then add write only if you enable interface switches.

### Step A4 — Generate and store the API key

1. Save the administrator — FortiOS shows the **API key once**.
2. Copy it into a password manager; you will paste it into Home Assistant in Part B.  
   **You cannot retrieve the same key again** from the GUI; you must regenerate if lost.

### Step A5 — VDOM (if you use virtual domains)

1. Note the **VDOM name** you want to monitor (often `root`).
2. Use that exact name in the integration setup. Mismatched VDOM is a common cause of empty interface lists or auth errors.

### Step A6 — API version (v1 vs v2)

1. FortiOS 7.x usually uses **`v2`** REST monitor paths (this integration defaults accordingly).
2. If your appliance or policy requires **`v1`**, select API **v1** in the integration options so URLs match your environment.

---

## Part B — Home Assistant (HACS and integration)

### Step B1 — Install HACS (if not already installed)

1. Follow the official guide: [https://www.hacs.xyz/docs/setup/download](https://www.hacs.xyz/docs/setup/download)
2. Restart Home Assistant after HACS is installed.

### Step B2 — Add this repository to HACS

1. Open **HACS** → **Integrations**.
2. Open the **⋮** (three dots) menu → **Custom repositories**.
3. **Repository:** `https://github.com/umarjamilpc/ha_fortigate_integration`  
   **Category:** **Integration**  
4. Click **Add**. The repository appears in HACS with this README (`render_readme` is enabled in `hacs.json`).

### Step B3 — Download the integration

1. In **HACS** → **Integrations**, search for **FortiGate** (or open the new custom repository entry).
2. Click **Download** and choose the **latest release** (recommended) so the version matches `manifest.json`.
3. **Restart Home Assistant** when prompted.

### Step B4 — Add the FortiGate integration

1. Go to **Settings** → **Devices & services** → **Add integration**.
2. Search for **FortiGate** and select it.
3. Fill in the form:

   | Field | Example / notes |
   |-------|-----------------|
   | **Host** | IP or DNS name of the FortiGate management interface. |
   | **Port** | `443` unless you changed the management HTTPS port. |
   | **Verify SSL** | Enable if the certificate is trusted by HA; disable only if you must (see A1). |
   | **API token** | Paste the REST API key from Step A4. |
   | **VDOM** | e.g. `root` (see A5). |
   | **API version** | `v2` unless you require `v1` (see A6). |

4. Submit and wait for the config flow validation (connectivity + token check).

### Step B5 — Tune options (interfaces, polling, SD-WAN, switches)

1. On **Settings** → **Devices & services**, open the **FortiGate** integration entry.
2. Click **Configure**.
3. Adjust:

   - **Scan interval** — how often monitor endpoints are polled (minimum enforced in code).
   - **Interfaces** — **All** (filtered) vs **Only selected** (pick WAN/LAN interfaces you care about).
   - **SD-WAN** — enable if you want per-interface SD-WAN health entities.
   - **Interface switches** — only enable if the API user has **write** permission; misconfiguration can administratively **down** an interface (including one you manage over).

4. Save — entities refresh on the next poll (or reload the integration).

### Step B6 — Confirm entities

1. Open the **FortiGate** device in Home Assistant.
2. You should see sensors (firmware, CPU, memory, sessions, SPU/nTurbo %, per-interface Mbps, etc.), binary sensors (link, status), and optional switches (interface admin) and SD-WAN sensors depending on options.

---

## Manual install (without HACS)

1. Copy the folder `custom_components/fortigate` from this repository into your Home Assistant configuration directory so you have:

   `config/custom_components/fortigate/` (including `manifest.json`, `brand/icon.png`, `icon.png`, and all `.py` files).

2. Restart Home Assistant.
3. Continue from **Part B — Step B4** above.

---

## Links

| Resource | URL |
|----------|-----|
| Repository | [github.com/umarjamilpc/ha_fortigate_integration](https://github.com/umarjamilpc/ha_fortigate_integration) |
| Issues | [github.com/umarjamilpc/ha_fortigate_integration/issues](https://github.com/umarjamilpc/ha_fortigate_integration/issues) |
| YAML entity reference (optional legacy pack, not installed by HACS) | [docs/fortigate_yaml_entity_reference.yaml](docs/fortigate_yaml_entity_reference.yaml) |

---

## Trademark notice

**Fortinet**, **FortiGate**, and the Fortinet logomark are trademarks of **Fortinet, Inc.** This is a community integration and is not affiliated with or endorsed by Fortinet. The logo is used solely to identify compatibility with FortiGate products.
