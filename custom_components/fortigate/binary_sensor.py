"""Binary sensors for FortiGate (e.g. interface link)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FortigateCoordinator
from .entity import FortigateEntity, iface_slug
from .helpers import interface_monitor_admin_up
from .naming import if_entity_label


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FortigateCoordinator = hass.data[DOMAIN][entry.entry_id]
    base_uid = entry.unique_id or entry.entry_id
    entities: list[BinarySensorEntity] = []
    for if_name in coordinator.get_tracked_interface_names():
        slug = iface_slug(if_name)
        entities.append(
            FortigateInterfaceLinkBinary(coordinator, entry, base_uid, if_name, slug)
        )
        entities.append(
            FortigateInterfaceStatusBinary(coordinator, entry, base_uid, if_name, slug)
        )
    async_add_entities(entities)


class FortigateInterfaceLinkBinary(FortigateEntity, BinarySensorEntity):
    """Physical / data link status for an interface."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description = BinarySensorEntityDescription(
        key="link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    )

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
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_link"
        self._attr_name = if_entity_label(interface_name, "LINK")

    @property
    def is_on(self) -> bool | None:
        payload = self.coordinator.get_interface_payload(self._interface_name)
        if not payload:
            return None
        link = payload.get("link")
        if link is None:
            return None
        return bool(link)


class FortigateInterfaceStatusBinary(FortigateEntity, BinarySensorEntity):
    """Monitor administrative status (up/down) from system/interface — read-only."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description = BinarySensorEntityDescription(
        key="status",
    )

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
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_status"
        self._attr_name = if_entity_label(interface_name, "STATUS")

    @property
    def is_on(self) -> bool | None:
        payload = self.coordinator.get_interface_payload(self._interface_name)
        return interface_monitor_admin_up(payload)
