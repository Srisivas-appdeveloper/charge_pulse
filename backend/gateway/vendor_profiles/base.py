"""Base vendor profile. Override per-vendor for quirks."""
from __future__ import annotations


class VendorProfile:
    vendor_name: str = "generic"

    def normalize_status(self, raw_status: str) -> str:
        return raw_status

    def normalize_error_code(self, raw_code: str | None) -> str:
        return raw_code or "NoError"

    def normalize_meter_values(self, raw_values: list) -> list:
        return raw_values

    def get_heartbeat_interval(self) -> int:
        return 60

    def get_meter_sample_interval(self) -> int:
        return 30
