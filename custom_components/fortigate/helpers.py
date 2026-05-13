"""Shared helpers for FortiGate integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_INTERFACE_MODE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_INTERFACES,
    DEFAULT_OPTIONS,
    INTERFACE_MODE_ALL,
    INTERFACE_MODE_SELECTED,
    INTERFACE_NAME_PREFIX_DENYLIST,
)


def merge_entry_options(entry: ConfigEntry) -> dict[str, Any]:
    """Merge config entry options with defaults."""
    return {**DEFAULT_OPTIONS, **(entry.options or {})}


def normalize_interface_results(raw: Any) -> dict[str, dict[str, Any]]:
    """Return interface name -> payload from monitor/system/interface ``results``."""
    if isinstance(raw, dict):
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("interface")
            if name:
                out[str(name)] = item
        return out
    return {}


def interface_allowed_in_all_mode(name: str) -> bool:
    if not name:
        return False
    lower = name.lower()
    if lower == "modem":
        return False
    return not any(lower.startswith(p) for p in INTERFACE_NAME_PREFIX_DENYLIST)


def interfaces_in_scope(
    results: dict[str, dict[str, Any]], options: dict[str, Any]
) -> list[str]:
    """Ordered list of interface names to expose as entities."""
    mode = options.get(CONF_INTERFACE_MODE, INTERFACE_MODE_ALL)
    names = sorted(results.keys(), key=str.lower)
    if mode == INTERFACE_MODE_ALL:
        return [n for n in names if interface_allowed_in_all_mode(n)]
    selected = options.get(CONF_TRACKED_INTERFACES) or []
    if not isinstance(selected, list):
        selected = [selected]
    selected_set = {str(s) for s in selected}
    return [n for n in names if n in selected_set]


def _sdwan_slug(path: str) -> str:
    return path.replace(".", "_").replace("-", "_").replace(" ", "_").lower()


def _sdwan_leaf_candidate(node: dict[str, Any]) -> bool:
    """True if dict looks like SD-WAN health metrics (not a pure branch of nested dicts)."""
    if not node:
        return False
    if all(isinstance(v, dict) for v in node.values()):
        return False
    keys_lower = {str(k).lower() for k in node}
    markers = {
        "latency",
        "jitter",
        "packet_loss",
        "packet-loss",
        "status",
        "state",
        "sla",
    }
    if keys_lower & markers:
        return True
    return any("loss" in str(k).lower() for k in node)


def iter_sdwan_health_members(results: Any) -> list[tuple[str, dict[str, Any]]]:
    """Depth-first walk of ``results``; yield (stable_slug, leaf dict)."""
    found: list[tuple[str, dict[str, Any]]] = []

    def walk(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            if path and _sdwan_leaf_candidate(node):
                found.append((_sdwan_slug("_".join(path)), node))
                return
            for key, val in node.items():
                if isinstance(val, dict):
                    walk(val, path + [str(key)])
                elif isinstance(val, list):
                    for idx, item in enumerate(val):
                        walk(item, path + [str(key), str(idx)])
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk(item, path + [str(idx)])

    walk(results, [])
    return found


def pick_sdwan_block_for_interface(
    members: dict[str, Any], interface_name: str
) -> tuple[str, dict[str, Any]] | None:
    """Pick one SD-WAN health leaf whose slug references *interface_name* (e.g. WAN1 → …_wan1)."""
    if not members or not interface_name:
        return None
    ikey = (
        str(interface_name).replace(".", "_").replace("-", "_").strip().lower()
    )
    if not ikey:
        return None
    hits: list[tuple[str, dict[str, Any], int]] = []
    for slug, block in members.items():
        if not isinstance(block, dict):
            continue
        raw = str(slug).replace(".", "_")
        parts = [p.lower() for p in raw.split("_") if p]
        if ikey not in parts:
            continue
        score = 0
        if parts and parts[-1] == ikey:
            score = 2
        elif parts and parts[0] == ikey:
            score = 1
        hits.append((str(slug), block, score))
    if not hits:
        return None
    hits.sort(key=lambda x: (-x[2], len(x[0]), x[0].lower()))
    slug, block, _ = hits[0]
    return (slug, block)


def sdwan_get_field(block: dict[str, Any], *field_names: str) -> Any:
    """Read field allowing hyphen vs underscore keys."""
    for field in field_names:
        for key in (field, field.replace("_", "-"), field.replace("-", "_")):
            if key in block:
                return block[key]
    return None
