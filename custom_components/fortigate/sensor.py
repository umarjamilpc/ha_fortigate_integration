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
from .helpers import merge_entry_options, sdwan_get_field

# (internal_field, title fragment, unit, decimals)
SDWAN_NUMERIC_SPECS: tuple[tuple[str, str, str | None, int], ...] = (
    ("latency", "latency", "ms", 2),
    ("jitter", "jitter", "ms", 2),
    ("packet_loss", "packet loss", PERCENTAGE, 2),
    ("sla", "SLA", None, 0),
)


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
        FortigateNpuSessionsSensor(coordinator, entry, base_uid),
        FortigateNturboSessionsSensor(coordinator, entry, base_uid),
    ]

    for if_name in coordinator.get_tracked_interface_names():
        slug = iface_slug(if_name)
        entities.append(
            FortigateInterfaceMbpsSensor(
                coordinator, entry, base_uid, if_name, slug, "rx_mbps", "RX Mbps"
            )
        )
        entities.append(
            FortigateInterfaceMbpsSensor(
                coordinator, entry, base_uid, if_name, slug, "tx_mbps", "TX Mbps"
            )
        )

    if opts.get(CONF_ENABLE_SDWAN_SENSOR):
        members = (coordinator.data or {}).get("sdwan_members") or {}
        for member_slug, block in members.items():
            if not isinstance(block, dict):
                continue
            for field_key, title_frag, unit, decimals in SDWAN_NUMERIC_SPECS:
                if field_key == "packet_loss":
                    raw = sdwan_get_field(block, "packet_loss", "packet-loss")
                    uid_field = "packet_loss"
                else:
                    raw = sdwan_get_field(block, field_key)
                    uid_field = field_key
                if raw is None:
                    continue
                lookup_names: tuple[str, ...] = (
                    ("packet_loss", "packet-loss")
                    if field_key == "packet_loss"
                    else (field_key,)
                )
                entities.append(
                    FortigateSdwanNumericSensor(
                        coordinator,
                        entry,
                        base_uid,
                        member_slug,
                        uid_field,
                        lookup_names,
                        title_frag,
                        unit,
                        decimals,
                    )
                )
            entities.append(
                FortigateSdwanRawSensor(coordinator, entry, base_uid, member_slug)
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


class FortigateNpuSessionsSensor(FortigateEntity, SensorEntity):
    """NPU / hardware offload session count (if reported by firmware)."""

    entity_description = SensorEntityDescription(
        key="npu_sessions",
        name="NPU sessions",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_npu_sessions"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        res = self.coordinator.data.get("resources", {}).get("results") or {}
        npu = res.get("npu_session") or []
        if not npu:
            return None
        cur = npu[0].get("current")
        return int(cur) if cur is not None else None


class FortigateNturboSessionsSensor(FortigateEntity, SensorEntity):
    """nTurbo session count (if reported by firmware)."""

    entity_description = SensorEntityDescription(
        key="nturbo_sessions",
        name="nTurbo sessions",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_nturbo_sessions"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        res = self.coordinator.data.get("resources", {}).get("results") or {}
        nt = res.get("nturbo_session") or []
        if not nt:
            return None
        cur = nt[0].get("current")
        return int(cur) if cur is not None else None


class FortigateSdwanNumericSensor(FortigateEntity, SensorEntity):
    """One numeric SD-WAN health metric (latency, jitter, loss, SLA, …)."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        member_slug: str,
        uid_field: str,
        lookup_names: tuple[str, ...],
        title_fragment: str,
        unit: str | None,
        decimals: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._member_slug = member_slug
        self._lookup_names = lookup_names
        self._decimals = decimals
        self._attr_unique_id = f"{base_uid}_sdwan_{member_slug}_{uid_field.replace('-', '_')}"
        self._attr_name = f"SD-WAN {member_slug} {title_fragment}"
        self._attr_native_unit_of_measurement = unit
        if decimals:
            self._attr_suggested_display_precision = decimals

    @property
    def native_value(self) -> float | int | None:
        block = self.coordinator.get_sdwan_member_block(self._member_slug)
        raw = sdwan_get_field(block, *self._lookup_names)
        if raw is None:
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return None
        if self._decimals:
            return round(val, self._decimals)
        return int(val)


class FortigateSdwanRawSensor(FortigateEntity, SensorEntity):
    """All scalar SD-WAN health fields for one member (for dashboards / debugging)."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        member_slug: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._member_slug = member_slug
        self._attr_unique_id = f"{base_uid}_sdwan_{member_slug}_raw"
        self._attr_name = f"SD-WAN {member_slug} data"

    @property
    def native_value(self) -> str | None:
        block = self.coordinator.get_sdwan_member_block(self._member_slug)
        if not block:
            return None
        st = sdwan_get_field(block, "status", "state")
        return str(st) if st is not None else "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        block = self.coordinator.get_sdwan_member_block(self._member_slug)
        if not block:
            return {}
        out: dict[str, Any] = {}
        for k, v in block.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[str(k)] = v
        return out


class FortigateInterfaceMbpsSensor(FortigateEntity, SensorEntity):
    """Per-interface throughput from byte counter deltas (Mbps only; no byte entities)."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "Mbps"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        interface_name: str,
        interface_slug: str,
        rate_key: str,
        short_label: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._rate_key = rate_key
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_{rate_key}"
        self._attr_name = f"{interface_name} {short_label}"

    @property
    def native_value(self) -> float | None:
        rates = self.coordinator.get_interface_rates(self._interface_name)
        val = rates.get(self._rate_key)
        if val is None:
            return None
        return round(float(val), 2)
