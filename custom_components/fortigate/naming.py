"""Uppercase display names and SD-WAN label helpers."""

from __future__ import annotations


def iface_uc(name: str) -> str:
    """Interface name for UI (uppercase)."""
    return str(name).strip().upper()


def slug_parts_uc(slug: str) -> str:
    """Stable slug -> space-separated uppercase tokens (e.g. wan1_wan1 -> WAN1 WAN1)."""
    return " ".join(p.upper() for p in slug.replace(".", "_").split("_") if p)


def sdwan_entity_name(member_slug: str, suffix_uc: str) -> str:
    """SD-WAN naming: SD-WAN <ZONE> — <SUFFIX>."""
    zone = slug_parts_uc(member_slug)
    return f"SD-WAN {zone} — {suffix_uc.strip().upper()}"
