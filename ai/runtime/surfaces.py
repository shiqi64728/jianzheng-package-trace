"""Canonical package-surface vocabulary for MVP v0.2."""

from __future__ import annotations

SUPPORTED_SURFACES = ("front", "left", "right", "top", "back", "bottom", "unknown")
DEFAULT_SURFACES = ("front", "left", "right", "top")
COMPATIBILITY_SURFACE = "front"


def normalize_surface(value: str | None) -> str:
    """Normalize API input while retaining the v0.1 single-image default."""
    normalized = (value or COMPATIBILITY_SURFACE).strip().lower()
    if normalized in {"package_exterior", "package-exterior", ""}:
        normalized = COMPATIBILITY_SURFACE
    if normalized not in SUPPORTED_SURFACES:
        raise ValueError(f"surface must be one of: {', '.join(SUPPORTED_SURFACES)}")
    return normalized
