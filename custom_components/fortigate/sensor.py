"""Sensors for FortiGate monitor data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_ENABLE_SDWAN_SENSOR, DOMAIN
from .coordinator import FortigateCoordinator
from .entity import FortigateEntity, iface_slug
from .helpers import (
    compute_uptime_seconds,
    merge_entry_options,
    parse_utc_last_reboot,
    pick_sdwan_block_for_interface,
    sdwan_get_field,
    sdwan_primary_status_text,
    sdwan_safe_attributes,
)
from .naming import if_entity_label


def _resource_session_count(res: dict[str, Any], key: str) -> int | None:
    """Parse FortiOS resource/usage session counter (``current`` is a count, not %)."""
    items = res.get(key) or []
    if not items:
        return None
    cur = items[0].get("current")
    if cur is None:
        return None
    try:
        return int(float(cur))
    except (TypeError, ValueError):
        return None


# (internal_field, display metric name uppercase, unit, decimals)
SDWAN_NUMERIC_SPECS: tuple[tuple[str, str, str | None, int], ...] = (
    ("latency", "LATENCY", "ms", 2),
    ("jitter", "JITTER", "ms", 2),
    ("packet_loss", "PACKET LOSS", PERCENTAGE, 2),
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
        FortigateUptimeSensor(coordinator, entry, base_uid),
        FortigateCpuSensor(coordinator, entry, base_uid),
        FortigateMemorySensor(coordinator, entry, base_uid),
        FortigateSessionsSensor(coordinator, entry, base_uid),
        FortigateSpuSessionsSensor(coordinator, entry, base_uid),
        FortigateNturboSessionsSensor(coordinator, entry, base_uid),
    ]

    for if_name in coordinator.get_tracked_interface_names():
        slug = iface_slug(if_name)
        entities.append(
            FortigateInterfaceMbpsSensor(
                coordinator, entry, base_uid, if_name, slug, "rx_mbps"
            )
        )
        entities.append(
            FortigateInterfaceMbpsSensor(
                coordinator, entry, base_uid, if_name, slug, "tx_mbps"
            )
        )

    if opts.get(CONF_ENABLE_SDWAN_SENSOR):
        members = (coordinator.data or {}).get("sdwan_members") or {}
        for if_name in coordinator.get_tracked_interface_names():
            picked = pick_sdwan_block_for_interface(members, if_name)
            if not picked:
                continue
            member_slug, block = picked
            slug = iface_slug(if_name)
            for field_key, metric_uc, unit, decimals in SDWAN_NUMERIC_SPECS:
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
                        if_name,
                        slug,
                        member_slug,
                        uid_field,
                        lookup_names,
                        metric_uc,
                        unit,
                        decimals,
                    )
                )
            entities.append(
                FortigateInterfaceSdwanStatusSensor(
                    coordinator, entry, base_uid, if_name, slug, member_slug
                )
            )

    async_add_entities(entities)


class FortigateFirmwareSensor(FortigateEntity, SensorEntity):
    """Firmware / build string from web-ui state."""

    entity_description = SensorEntityDescription(
        key="firmware",
        name="FIRMWARE",
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


class FortigateUptimeSensor(FortigateEntity, SensorEntity):
    """Uptime since last reboot from web-ui ``utc_last_reboot``."""

    entity_description = SensorEntityDescription(
        key="uptime",
        name="UPTIME",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_uptime"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        web = self.coordinator.data.get("web_ui", {})
        reboot_ts = parse_utc_last_reboot(web)
        if reboot_ts is None:
            return None
        return compute_uptime_seconds(reboot_ts)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        web = self.coordinator.data.get("web_ui", {})
        reboot_ts = parse_utc_last_reboot(web)
        if reboot_ts is None:
            return {}
        return {
            "last_reboot": dt_util.utc_from_timestamp(reboot_ts).isoformat(),
        }


class FortigateCpuSensor(FortigateEntity, SensorEntity):
    """CPU usage percentage."""

    entity_description = SensorEntityDescription(
        key="cpu_usage",
        name="CPU USAGE",
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
        name="MEMORY USAGE",
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
        name="SESSIONS",
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
        return _resource_session_count(res, "session")


class FortigateSpuSessionsSensor(FortigateEntity, SensorEntity):
    """SPU (NPU) offloaded session count from FortiOS ``npu_session`` resource monitor."""

    entity_description = SensorEntityDescription(
        key="spu_sessions",
        name="SPU SESSIONS",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    )

    def __init__(
        self, coordinator: FortigateCoordinator, entry: ConfigEntry, base_uid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{base_uid}_spu_sessions"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        res = self.coordinator.data.get("resources", {}).get("results") or {}
        return _resource_session_count(res, "npu_session")


class FortigateNturboSessionsSensor(FortigateEntity, SensorEntity):
    """nTurbo offloaded session count from FortiOS ``nturbo_session`` resource monitor."""

    entity_description = SensorEntityDescription(
        key="nturbo_sessions",
        name="NTURBO SESSIONS",
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
        return _resource_session_count(res, "nturbo_session")


class FortigateSdwanNumericSensor(FortigateEntity, SensorEntity):
    """One numeric SD-WAN health metric bound to a tracked interface (e.g. WAN1 LATENCY)."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        interface_name: str,
        interface_slug: str,
        member_slug: str,
        uid_field: str,
        lookup_names: tuple[str, ...],
        metric_uc: str,
        unit: str | None,
        decimals: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._member_slug = member_slug
        self._lookup_names = lookup_names
        self._decimals = decimals
        self._attr_unique_id = (
            f"{base_uid}_if_{interface_slug}_sdwan_{uid_field.replace('-', '_')}"
        )
        self._attr_name = if_entity_label(interface_name, metric_uc)
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


class FortigateInterfaceSdwanStatusSensor(FortigateEntity, SensorEntity):
    """SD-WAN health summary for a tracked interface (scalar state + detail attributes)."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FortigateCoordinator,
        entry: ConfigEntry,
        base_uid: str,
        interface_name: str,
        interface_slug: str,
        member_slug: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._member_slug = member_slug
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_sdwan_summary"
        self._attr_name = if_entity_label(interface_name, "SDWAN STATUS")

    @property
    def native_value(self) -> str | None:
        block = self.coordinator.get_sdwan_member_block(self._member_slug)
        return sdwan_primary_status_text(block)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        block = self.coordinator.get_sdwan_member_block(self._member_slug)
        return sdwan_safe_attributes(block)


class FortigateInterfaceMbpsSensor(FortigateEntity, SensorEntity):
    """Per-interface throughput from byte counter deltas (Mbps)."""

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
    ) -> None:
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._rate_key = rate_key
        self._attr_unique_id = f"{base_uid}_if_{interface_slug}_{rate_key}"
        if rate_key == "rx_mbps":
            self._attr_name = if_entity_label(interface_name, "DOWNLOAD MBPS")
        else:
            self._attr_name = if_entity_label(interface_name, "UPLOAD MBPS")

    @property
    def native_value(self) -> float | None:
        rates = self.coordinator.get_interface_rates(self._interface_name)
        val = rates.get(self._rate_key)
        if val is None:
            return None
        return round(float(val), 2)
