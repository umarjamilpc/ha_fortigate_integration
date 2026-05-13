"""Switches for FortiGate CMDB (administrative interface up/down)."""

from __future__ import annotations

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
from .helpers import merge_entry_options

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    opts = merge_entry_options(entry)
    if not opts.get(CONF_ENABLE_INTERFACE_SWITCHES):
        return

    coordinator: FortigateCoordinator = hass.data[DOMAIN][entry.entry_id]
    base_uid = entry.unique_id or entry.entry_id
    entities: list[SwitchEntity] = []
    for if_name in coordinator.get_tracked_interface_names():
        slug = iface_slug(if_name)
        entities.append(
            FortigateInterfaceAdminSwitch(coordinator, entry, base_uid, if_name, slug)
        )
    async_add_entities(entities)


class FortigateInterfaceAdminSwitch(FortigateEntity, SwitchEntity):
    """Administrative up/down (CMDB status) — can disconnect management; use with care."""

    _attr_has_entity_name = False

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
        self._attr_name = f"{interface_name} administrative status"

    @property
    def is_on(self) -> bool | None:
        payload = self.coordinator.get_interface_payload(self._interface_name)
        if not payload:
            return None
        status = (payload.get("status") or "up").lower()
        return status == "up"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, up: bool) -> None:
        try:
            await self.coordinator.client.set_interface_admin_status(
                self._interface_name, up
            )
        except FortigateAuthError as err:
            raise HomeAssistantError("FortiGate rejected credentials or permissions") from err
        except FortigateConnectionError as err:
            raise HomeAssistantError(f"Connection failed: {err}") from err
        except FortigateApiError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
