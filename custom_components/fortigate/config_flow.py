"""Config flow and options flow for FortiGate."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import FortigateApiError, FortigateAuthError, FortigateClient, FortigateConnectionError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_PREFIX,
    CONF_ENABLE_INTERFACE_SWITCHES,
    CONF_ENABLE_SDWAN_SENSOR,
    CONF_INTERFACE_MODE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_INTERFACES,
    CONF_VDOM,
    DEFAULT_API_PREFIX,
    DEFAULT_PORT,
    DEFAULT_VDOM,
    DOMAIN,
    INTERFACE_MODE_ALL,
    INTERFACE_MODE_SELECTED,
)
from .helpers import merge_entry_options, normalize_interface_results

_LOGGER = logging.getLogger(__name__)


def fortigate_client_from_entry(hass, entry: config_entries.ConfigEntry) -> FortigateClient:
    data = entry.data
    return FortigateClient(
        hass,
        data[CONF_HOST],
        int(data[CONF_PORT]),
        data[CONF_ACCESS_TOKEN],
        vdom=data.get(CONF_VDOM) or DEFAULT_VDOM,
        api_prefix=data.get(CONF_API_PREFIX) or DEFAULT_API_PREFIX,
        verify_ssl=bool(data[CONF_VERIFY_SSL]),
    )


def _schema_defaults() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST): selector.TextSelector(),
            vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=1,
                    max=65535,
                )
            ),
            vol.Required(CONF_ACCESS_TOKEN): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_VDOM, default=DEFAULT_VDOM): selector.TextSelector(),
            vol.Optional(CONF_API_PREFIX, default=DEFAULT_API_PREFIX): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["v2", "v1"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_VERIFY_SSL, default=False): selector.BooleanSelector(),
        }
    )


async def validate_input(hass, data: dict[str, Any]) -> dict[str, str]:
    """Validate credentials and return title + serial for unique_id."""
    client = FortigateClient(
        hass,
        data[CONF_HOST],
        int(data[CONF_PORT]),
        data[CONF_ACCESS_TOKEN],
        vdom=data.get(CONF_VDOM) or DEFAULT_VDOM,
        api_prefix=data.get(CONF_API_PREFIX) or DEFAULT_API_PREFIX,
        verify_ssl=bool(data[CONF_VERIFY_SSL]),
    )
    state = await client.validate()
    serial = state.get("serial")
    if not serial:
        raise FortigateApiError("Missing serial in /monitor/web-ui/state response")
    results = state.get("results") or {}
    hostname = state.get("hostname") or results.get("hostname") or data[CONF_HOST]
    return {"title": f"{hostname} ({serial})", "serial": serial}


class FortigateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UI config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> FortigateOptionsFlow:
        return FortigateOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except FortigateConnectionError:
                errors["base"] = "cannot_connect"
            except FortigateAuthError:
                errors["base"] = "invalid_auth"
            except FortigateApiError:
                errors["base"] = "api_error"
            except Exception:
                _LOGGER.exception("Unexpected exception validating FortiGate")
                errors["base"] = "unknown"
            else:
                vdom_key = (user_input.get(CONF_VDOM) or DEFAULT_VDOM).lower()
                await self.async_set_unique_id(f"{info['serial']}_{vdom_key}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        schema = _schema_defaults()
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class FortigateOptionsFlow(config_entries.OptionsFlow):
    """Options for polling, interface scope, SD-WAN, and CMDB switches."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        entry = self.config_entry
        opts = merge_entry_options(entry)
        errors: dict[str, str] = {}

        client = fortigate_client_from_entry(self.hass, entry)
        iface_labels: list[dict[str, str]] = []
        try:
            iface_resp = await client.get_monitor_interfaces()
            results = normalize_interface_results(iface_resp.get("results"))
            for name in sorted(results.keys(), key=str.lower):
                iface_labels.append({"value": name, "label": name})
        except (FortigateApiError, FortigateConnectionError, FortigateAuthError):
            _LOGGER.debug("Could not list interfaces for options flow", exc_info=True)

        if not iface_labels:
            iface_labels.append(
                {
                    "value": "__none__",
                    "label": "(Could not load interfaces — check connection, then reopen)",
                }
            )

        if user_input is not None:
            tracked = user_input.get(CONF_TRACKED_INTERFACES) or []
            if not isinstance(tracked, list):
                tracked = [tracked]
            tracked = [
                str(t) for t in tracked if str(t).strip() and not str(t).startswith("__")
            ]
            if (
                user_input[CONF_INTERFACE_MODE] == INTERFACE_MODE_SELECTED
                and not tracked
            ):
                errors["base"] = "no_interfaces_selected"
            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: max(
                            5, min(int(user_input[CONF_SCAN_INTERVAL]), 3600)
                        ),
                        CONF_INTERFACE_MODE: user_input[CONF_INTERFACE_MODE],
                        CONF_TRACKED_INTERFACES: tracked,
                        CONF_ENABLE_INTERFACE_SWITCHES: bool(
                            user_input[CONF_ENABLE_INTERFACE_SWITCHES]
                        ),
                        CONF_ENABLE_SDWAN_SENSOR: bool(
                            user_input[CONF_ENABLE_SDWAN_SENSOR]
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=opts[CONF_SCAN_INTERVAL]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        min=5,
                        max=3600,
                    )
                ),
                vol.Required(
                    CONF_INTERFACE_MODE, default=opts[CONF_INTERFACE_MODE]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {
                                "value": INTERFACE_MODE_ALL,
                                "label": "All (hide FortiOS ssl./naf.* noise)",
                            },
                            {
                                "value": INTERFACE_MODE_SELECTED,
                                "label": "Only selected interfaces",
                            },
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_TRACKED_INTERFACES, default=opts.get(CONF_TRACKED_INTERFACES, [])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=iface_labels,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_ENABLE_INTERFACE_SWITCHES,
                    default=opts[CONF_ENABLE_INTERFACE_SWITCHES],
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_SDWAN_SENSOR, default=opts[CONF_ENABLE_SDWAN_SENSOR]
                ): selector.BooleanSelector(),
            }
        )
        schema = self.add_suggested_values_to_schema(schema, user_input or opts)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
