"""FortiGate integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback

from .api import FortigateClient
from .const import CONF_ACCESS_TOKEN, CONF_API_PREFIX, CONF_VDOM, DEFAULT_API_PREFIX, DEFAULT_VDOM, DOMAIN
from .coordinator import FortigateCoordinator

PLATFORMS: list[str] = ["sensor", "binary_sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    data = entry.data
    client = FortigateClient(
        hass,
        data[CONF_HOST],
        int(data[CONF_PORT]),
        data[CONF_ACCESS_TOKEN],
        vdom=data.get(CONF_VDOM) or DEFAULT_VDOM,
        api_prefix=data.get(CONF_API_PREFIX) or DEFAULT_API_PREFIX,
        verify_ssl=bool(data[CONF_VERIFY_SSL]),
    )
    coordinator = FortigateCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _async_reload_on_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
