"""Sensors for FortiGate monitor data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_SDWAN_SENSOR, DOMAIN
from .coordinator import FortigateCoordinator
from .entity import FortigateEntity, iface_slug
from .helpers import merge_entry_options


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FortigateCoordinator = hass.data[DOMAIN][entry.entry_id]
    base_uid = entry.unique_id or entry.entry_id
    opts = merge_entry_options(entry)

    entities: list[SensorEntity] = [
        FortigateFirmwareSensor(coordinator, entry, base_uid),
        FortigateCpuSensor(coordinator, entry, base_uid),
        FortigateMemorySensor(coordinator, entry, base_uid),
        FortigateSessionsSensor(coordinator, entry, base_uid),
    ]
    if opts.get(CONF_ENABLE_SDWAN_SENSOR):
        entities.append(FortigateSdwanSensor(coordinator, entry, base_uid))

    for if_name in coordinator.get_tracked_interface_names():
        slug = iface_slug(if_name)
        entities.append(
            FortigateInterfaceCounterSensor(
                coordinator, entry, base_uid, if_name, slug, "rx_bytes", "RX bytes"
            )
        )
        entities.append(
            FortigateInterfaceCounterSensor(
                coordinator, entry, base_uid, if_name, slug, "tx_bytes", "TX bytes"
            )
        )

    async_add_entities(entities)


class FortigateFirmwareSensor(FortigateEntity, SensorEntity):
    """Firmware / build string from web-ui state."""

    entity_description = SensorEntityDescription(
        key="firmware",
        name="Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_firmware"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        web = self.coordinator.data.get("web_ui", {})
        return web.get("version")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        web = self.coordinator.data.get("web_ui", {})
        results = web.get("results") or {}
        return {
            "serial": web.get("serial"),
            "build": web.get("build"),
            "model_number": results.get("model_number"),
            "vdom": web.get("vdom"),
        }


class FortigateCpuSensor(FortigateEntity, SensorEntity):
    """CPU usage percentage."""

    entity_description = SensorEntityDescription(
        key="cpu_usage",
        name="CPU usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_cpu_usage"

    @property
    def native_value(self) -> int | float | None:
        if not self.coordinator.data:
            return None
        res = self.coordinator.data.get("resources", {}).get("results") or {}
        cpu = res.get("cpu") or []
        if not cpu:
            return None
        return cpu[0].get("current")


class FortigateMemorySensor(FortigateEntity, SensorEntity):
    """Memory usage percentage."""

    entity_description = SensorEntityDescription(
        key="memory_usage",
        name="Memory usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_memory_usage"

    @property
    def native_value(self) -> int | float | None:
        if not self.coordinator.data:
            return None
        res = self.coordinator.data.get("resources", {}).get("results") or {}
        mem = res.get("mem") or []
        if not mem:
            return None
        return mem[0].get("current")


class FortigateSessionsSensor(FortigateEntity, SensorEntity):
    """Session table size from resource usage."""

    entity_description = SensorEntityDescription(
        key="sessions",
        name="Sessions",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_sessions"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        res = self.coordinator.data.get("resources", {}).get("results") or {}
        sess = res.get("session") or []
        if not sess:
            return None
        cur = sess[0].get("current")
        return int(cur) if cur is not None else None


class FortigateSdwanSensor(FortigateEntity, SensorEntity):
    """SD-WAN health-check summary (disable in options if unused)."""

    entity_description = SensorEntityDescription(
        key="sdwan_health",
        name="SD-WAN health",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_sdwan_health"

    @property
    def native_value(self) -> int | str | None:
        if not self.coordinator.data:
            return None
        sd = self.coordinator.data.get("sdwan")
        if not sd:
            return None
        results = sd.get("results")
        if isinstance(results, dict):
            return len(results)
        if isinstance(results, list):
            return len(results)
        return "ok"


class FortigateInterfaceCounterSensor(FortigateEntity, SensorEntity):
    """Per-interface byte counter from monitor (TOTAL_INCREASING for HA statistics)."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        interface_name: str,
        interface_slug: str,
        field: str,
        short_label: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._field = field
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_{field}"
        self._attr_name = f"{interface_name} {short_label}"
        self._attr_native_unit_of_measurement = "B"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> int | None:
        payload = self.coordinator.get_interface_payload(self._interface_name)
        val = payload.get(self._field)
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        payload = self.coordinator.get_interface_payload(self._interface_name)
        if not payload:
            return {}
        return {
            k: payload[k]
            for k in (
                "speed",
                "duplex",
                "ip",
                "mask",
                "status",
                "link",
                "type",
            )
            if k in payload
        }
