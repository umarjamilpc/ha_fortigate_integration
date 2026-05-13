"""DataUpdateCoordinator for FortiGate polling."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    FortigateApiError,
    FortigateAuthError,
    FortigateClient,
    FortigateConnectionError,
)
from .const import CONF_ENABLE_SDWAN_SENSOR, CONF_SCAN_INTERVAL, DOMAIN
from .helpers import interfaces_in_scope, merge_entry_options, normalize_interface_results

_LOGGER = logging.getLogger(__name__)


class FortigateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll monitor endpoints and expose merged data to platforms."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: FortigateClient,
        config_entry: ConfigEntry,
    ) -> None:
        opts = merge_entry_options(config_entry)
        interval_sec = max(5, min(int(opts[CONF_SCAN_INTERVAL]), 3600))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_sec),
        )
        self.client = client
        self._iface_prev: dict[str, tuple[int, int, float]] = {}

    def get_tracked_interface_names(self) -> list[str]:
        """Interfaces that should have per-interface entities (from options + API)."""
        if not self.data:
            return []
        raw = self.data.get("interfaces", {}).get("results")
        results = normalize_interface_results(raw)
        opts = merge_entry_options(self.config_entry)
        return interfaces_in_scope(results, opts)

    def get_interface_payload(self, name: str) -> dict[str, Any]:
        """Single interface block from last poll."""
        if not self.data:
            return {}
        raw = self.data.get("interfaces", {}).get("results")
        results = normalize_interface_results(raw)
        return dict(results.get(name, {}))

    def get_interface_rates(self, name: str) -> dict[str, float]:
        """Latest computed RX/TX Mbps for an interface (from byte deltas)."""
        if not self.data:
            return {}
        rates: dict[str, dict[str, float]] = self.data.get("interface_rates") or {}
        return dict(rates.get(name, {}))

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            web_ui = await self.client.validate()
            interfaces = await self.client.get_monitor_interfaces()
            resources = await self.client.get_monitor_resource_usage()
        except FortigateAuthError as err:
            raise UpdateFailed("Authentication failed") from err
        except FortigateConnectionError as err:
            raise UpdateFailed(f"Connection failed: {err}") from err
        except FortigateApiError as err:
            raise UpdateFailed(f"API error: {err}") from err

        sdwan: dict[str, Any] | None = None
        opts = merge_entry_options(self.config_entry)
        if opts.get(CONF_ENABLE_SDWAN_SENSOR):
            try:
                sdwan = await self.client.get_monitor_sdwan_health()
            except FortigateApiError:
                sdwan = None

        results_norm = normalize_interface_results(interfaces.get("results"))
        scope = interfaces_in_scope(results_norm, opts)
        scope_set = set(scope)
        for stale in list(self._iface_prev.keys()):
            if stale not in scope_set:
                del self._iface_prev[stale]

        interface_rates: dict[str, dict[str, float]] = {}
        now = time.monotonic()
        for name in scope:
            payload = results_norm.get(name) or {}
            try:
                rx = int(payload.get("rx_bytes") or 0)
                tx = int(payload.get("tx_bytes") or 0)
            except (TypeError, ValueError):
                self._iface_prev.pop(name, None)
                continue
            prev = self._iface_prev.get(name)
            if prev is not None:
                prx, ptx, pt = prev
                if rx >= prx and tx >= ptx:
                    dt = now - pt
                    if dt > 0.001:
                        drx = rx - prx
                        dtx = tx - ptx
                        interface_rates[name] = {
                            "rx_mbps": min(9999.0, drx * 8.0 / 1_000_000.0 / dt),
                            "tx_mbps": min(9999.0, dtx * 8.0 / 1_000_000.0 / dt),
                        }
            self._iface_prev[name] = (rx, tx, now)

        return {
            "web_ui": web_ui,
            "interfaces": interfaces,
            "resources": resources,
            "sdwan": sdwan,
            "interface_rates": interface_rates,
        }
