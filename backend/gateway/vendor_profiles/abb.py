from .base import VendorProfile


# ABB Terra series: vendor-specific error codes mapped to OCPP standard set.
_ABB_ERROR_MAP = {
    "PowerModuleFault": "PowerSwitchFailure",
    "DcLeakageDetected": "GroundFailure",
    "AcInputVoltageOutOfRange": "UnderVoltage",
    "AcInputOverVoltage": "OverVoltage",
    "AcInputUnderVoltage": "UnderVoltage",
    "RcdTripped": "GroundFailure",
    "EmergencyStopPressed": "OtherError",
    "CcsCommTimeout": "EVCommunicationError",
}


class ABBProfile(VendorProfile):
    vendor_name = "abb"

    def normalize_error_code(self, raw_code: str | None) -> str:
        if not raw_code:
            return "NoError"
        return _ABB_ERROR_MAP.get(raw_code, raw_code)

    def get_heartbeat_interval(self) -> int:
        # ABB chargers ignore intervals shorter than 30s.
        return 60

    def get_meter_sample_interval(self) -> int:
        # Terra defaults are 30s; aligning explicitly avoids drift.
        return 30
