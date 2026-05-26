from .base import VendorProfile


# Delta DC-60kW / DC-30kW: error codes seen in Indian deployments.
_DELTA_ERROR_MAP = {
    "OverTemperature": "HighTemperature",
    "OverTemp": "HighTemperature",
    "ContactorWelded": "PowerSwitchFailure",
    "AcMainsBrownout": "UnderVoltage",
    "InsulationCheckFail": "GroundFailure",
    "CommModuleTimeout": "WeakSignal",
}


class DeltaProfile(VendorProfile):
    vendor_name = "delta"

    def normalize_error_code(self, raw_code: str | None) -> str:
        if not raw_code:
            return "NoError"
        return _DELTA_ERROR_MAP.get(raw_code, raw_code)

    def normalize_meter_values(self, raw_values: list) -> list:
        # Delta sometimes labels per-phase voltage as "Voltage.L1" instead of
        # "Voltage" with phase="L1". Flatten so downstream features see "Voltage".
        for mv in raw_values or []:
            for sv in mv.get("sampled_value", []) or []:
                meas = sv.get("measurand") or ""
                if meas.startswith("Voltage."):
                    sv["measurand"] = "Voltage"
                    sv["phase"] = meas.split(".", 1)[1]
                elif meas.startswith("Current."):
                    parts = meas.split(".", 1)
                    if parts[1] in ("L1", "L2", "L3"):
                        sv["measurand"] = "Current.Import"
                        sv["phase"] = parts[1]
        return raw_values
