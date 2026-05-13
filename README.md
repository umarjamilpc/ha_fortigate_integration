# FortiGate (Home Assistant custom integration)

Config-flow integration for Fortinet FortiGate firewalls using the FortiOS JSON REST API (token auth, VDOM-aware, dynamic interface entities).

## Installation (HACS)

1. Open **HACS** → **Integrations** → **⋮** → **Custom repositories**.
2. Add repository: `https://github.com/umarjamilpc/ha_fortigate_integration`  
   Category: **Integration**.
3. Search for **FortiGate**, install, then restart Home Assistant.
4. **Settings** → **Devices & services** → **Add integration** → **FortiGate**.

### Manual install

Copy the `custom_components/fortigate` folder into your Home Assistant `config` directory so you have `config/custom_components/fortigate/`, then restart.

## FortiGate setup

Create a **REST API** administrator (System → Administrators), assign a read-only profile for monitoring; enable **read-write** on network/interface objects only if you turn on **interface administrative switches** in the integration options.

## Options

After setup, use **Configure** on the integration card to set poll interval, which interfaces to expose (all vs selected), SD-WAN polling, and optional CMDB interface switches.

## Security

- This repository contains **no** Home Assistant `secrets.yaml` and **no** hard-coded FortiGate tokens. The token is stored only in the Home Assistant config entry after you add the integration.
- Never commit your full HA `config/` folder into this repo; use `secrets.yaml` locally and keep it out of Git.

## Versioning

Releases and tags follow **semantic versioning** (e.g. `v0.2.0`). The integration reports the same version in `manifest.json` for HACS.

## Links

- Repository: [umarjamilpc/ha_fortigate_integration](https://github.com/umarjamilpc/ha_fortigate_integration)
- Issues: [github.com/umarjamilpc/ha_fortigate_integration/issues](https://github.com/umarjamilpc/ha_fortigate_integration/issues)
