"""Constants for the FortiGate integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

DOMAIN = "fortigate"
DEFAULT_PORT = 443
DEFAULT_VDOM = "root"
DEFAULT_API_PREFIX = "v2"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_ACCESS_TOKEN = "access_token"
CONF_VDOM = "vdom"
CONF_API_PREFIX = "api_prefix"

# Config entry options (Options flow)
CONF_SCAN_INTERVAL = "scan_interval"
CONF_INTERFACE_MODE = "interface_mode"
CONF_TRACKED_INTERFACES = "tracked_interfaces"
CONF_ENABLE_INTERFACE_SWITCHES = "enable_interface_switches"
CONF_ENABLE_SDWAN_SENSOR = "enable_sdwan_sensor"

INTERFACE_MODE_ALL = "all"
INTERFACE_MODE_SELECTED = "selected"

DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_SCAN_INTERVAL: 30,
    CONF_INTERFACE_MODE: INTERFACE_MODE_ALL,
    CONF_TRACKED_INTERFACES: [],
    CONF_ENABLE_INTERFACE_SWITCHES: False,
    CONF_ENABLE_SDWAN_SENSOR: True,
}

# Names usually not useful as HA entities (always present on FortiOS)
INTERFACE_NAME_PREFIX_DENYLIST = ("ssl.", "naf.")
