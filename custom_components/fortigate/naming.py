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


def if_entity_label(interface_name: str, *suffix_tokens: str) -> str:
    """Per-interface entity name: ``WAN1 LATENCY``, ``WAN1 SDWAN STATUS`` (all uppercase)."""
    tail = " ".join(t.strip().upper() for t in suffix_tokens if t and str(t).strip())
    base = iface_uc(interface_name)
    return f"{base} {tail}".strip() if tail else base
