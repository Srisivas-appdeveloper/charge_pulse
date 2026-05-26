import re

from .base import VendorProfile


_SERVOTECH_ERROR_MAP = {
    "DCContactorFailure": "PowerSwitchFailure",
    "VoltageOutOfRange": "OverVoltage",
    "VoltageDrop": "UnderVoltage",
    "GFCITripped": "GroundFailure",
    "TempSensorFail": "HighTemperature",
    "GSMSignalLow": "WeakSignal",
}


_FW_VERSION_RE = re.compile(r"v?(\d+\.\d+(\.\d+)?)", re.IGNORECASE)


class ServotechProfile(VendorProfile):
    vendor_name = "servotech"

    def normalize_error_code(self, raw_code: str | None) -> str:
        if not raw_code:
            return "NoError"
        return _SERVOTECH_ERROR_MAP.get(raw_code, raw_code)

    @staticmethod
    def normalize_firmware_version(raw: str | None) -> str | None:
        """Servotech firmware strings vary: 'FW v1.4', 'STC-1.4.0', '1.4.0-beta'.
        Extract the dotted version so dashboard grouping is consistent.
        """
        if not raw:
            return raw
        m = _FW_VERSION_RE.search(raw)
        return m.group(1) if m else raw
