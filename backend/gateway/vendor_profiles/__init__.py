"""Vendor profile registry. Resolves a vendor name to the right profile."""
from __future__ import annotations

from .abb import ABBProfile
from .base import VendorProfile
from .delta import DeltaProfile
from .exicom import ExicomProfile
from .generic import GenericProfile
from .servotech import ServotechProfile

_REGISTRY: dict[str, type[VendorProfile]] = {
    "delta": DeltaProfile,
    "abb": ABBProfile,
    "exicom": ExicomProfile,
    "servotech": ServotechProfile,
}


def resolve(vendor: str | None) -> VendorProfile:
    if not vendor:
        return GenericProfile()
    cls = _REGISTRY.get(vendor.strip().lower())
    return cls() if cls else GenericProfile()


__all__ = ["VendorProfile", "GenericProfile", "resolve"]
