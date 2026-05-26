from .base import VendorProfile


_EXICOM_ERROR_MAP = {
    "InsufficientGridSupply": "UnderVoltage",
    "ChargerOverTemp": "HighTemperature",
    "RelayStuck": "PowerSwitchFailure",
    "EmergencyShutdown": "OtherError",
    "EarthLeakage": "GroundFailure",
    "CommunicationLost": "WeakSignal",
}


class ExicomProfile(VendorProfile):
    vendor_name = "exicom"

    def normalize_error_code(self, raw_code: str | None) -> str:
        # Exicom sometimes omits error_code field on Faulted status — default to OtherError
        # so the rule engine treats it as a real fault rather than NoError noise.
        if not raw_code:
            return "OtherError"
        return _EXICOM_ERROR_MAP.get(raw_code, raw_code)

    def normalize_status(self, raw_status: str) -> str:
        # Some Exicom firmwares report "Error" instead of OCPP-spec "Faulted".
        if raw_status == "Error":
            return "Faulted"
        return raw_status
