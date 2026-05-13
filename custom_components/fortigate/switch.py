"""Switches for FortiGate CMDB (administrative interface up/down)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import FortigateApiError, FortigateAuthError, FortigateConnectionError
from .const import CONF_ENABLE_INTERFACE_SWITCHES, DOMAIN
from .coordinator import FortigateCoordinator
from .entity import FortigateEntity, iface_slug
from .helpers import interface_monitor_admin_up, merge_entry_options
from .naming import if_entity_label


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FortigateCoordinator = hass.data[DOMAIN][entry.entry_id]
    base_uid = entry.unique_id or entry.entry_id
    opts = merge_entry_options(entry)
    entities: list[SwitchEntity] = []
    if opts.get(CONF_ENABLE_INTERFACE_SWITCHES):
        for if_name in coordinator.get_tracked_interface_names():
            slug = iface_slug(if_name)
            entities.append(
                FortigateInterfaceAdminSwitch(
                    coordinator, entry, base_uid, if_name, slug
                )
            )
    async_add_entities(entities)


class FortigateInterfaceAdminSwitch(FortigateEntity, SwitchEntity):
    """Administrative up/down (CMDB status) — can disconnect management; use with care."""

    _attr_has_entity_name = False
    PENDING_TIMEOUT_SEC = 12.0
    _REFRESH_GAP_SEC = (0.75, 1.25)

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        interface_name: str,
        interface_slug: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_admin"
        self._attr_name = if_entity_label(interface_name, "INTERFACE")
        self._pending_target: bool | None = None
        self._pending_set_at: float = 0.0

    @staticmethod
    def _read_admin_up(payload: dict[str, Any] | None) -> bool | None:
        return interface_monitor_admin_up(payload, assume_up_if_absent=True)

    @property
    def is_on(self) -> bool | None:
        payload = self.coordinator.get_interface_payload(self._interface_name)
        actual = self._read_admin_up(payload)
        if self._pending_target is not None:
            if actual is not None and actual == self._pending_target:
                self._pending_target = None
            elif (time.monotonic() - self._pending_set_at) < self.PENDING_TIMEOUT_SEC:
                return self._pending_target
            else:
                self._pending_target = None
        return actual

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, up: bool) -> None:
        self._pending_target = up
        self._pending_set_at = time.monotonic()
        self.async_write_ha_state()
        try:
            await self.coordinator.client.set_interface_admin_status(
                self._interface_name, up
            )
        except FortigateAuthError as err:
            self._pending_target = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                "FortiGate rejected credentials or permissions"
            ) from err
        except FortigateConnectionError as err:
            self._pending_target = None
            self.async_write_ha_state()
            raise HomeAssistantError(f"Connection failed: {err}") from err
        except FortigateApiError as err:
            self._pending_target = None
            self.async_write_ha_state()
            raise HomeAssistantError(str(err)) from err

        # CMDB updates before monitor; stagger refreshes so UI matches FortiOS.
        for gap in self._REFRESH_GAP_SEC:
            await asyncio.sleep(gap)
            await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
