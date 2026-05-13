"""Shared entity base for FortiGate platforms."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FortigateCoordinator


def iface_slug(name: str) -> str:
    """Stable slug for unique_id / entity naming."""
    return name.replace(".", "_").replace("-", "_").replace(" ", "_").lower()


class FortigateEntity(CoordinatorEntity[FortigateCoordinator]):
    """Base entity bound to the FortiGate device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FortigateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = entry

    @property
    def device_info(self) -> dict[str, Any]:
        web = self.coordinator.data.get("web_ui", {}) if self.coordinator.data else {}
        results = web.get("results") or {}
        serial = web.get("serial") or "FortiGate"
        host = self.coordinator.client.host
        port = self.coordinator.client.port
        uid = self._config_entry.unique_id or self._config_entry.entry_id
        host_label = str(results.get("hostname") or serial).upper()
        return {
            "identifiers": {(DOMAIN, uid)},
            "name": host_label,
            "manufacturer": "Fortinet",
            "model": results.get("model") or results.get("model_name") or "FortiGate",
            "sw_version": web.get("version"),
            "configuration_url": f"https://{host}:{port}/",
        }
