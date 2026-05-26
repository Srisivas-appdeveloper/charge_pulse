"""Vendor profile error-code & status normalisation."""
from gateway.vendor_profiles import resolve
from gateway.vendor_profiles.abb import ABBProfile
from gateway.vendor_profiles.delta import DeltaProfile
from gateway.vendor_profiles.exicom import ExicomProfile
from gateway.vendor_profiles.generic import GenericProfile
from gateway.vendor_profiles.servotech import ServotechProfile


def test_resolve_known_vendors_case_insensitive():
    assert isinstance(resolve("Delta"), DeltaProfile)
    assert isinstance(resolve("ABB"), ABBProfile)
    assert isinstance(resolve("exicom"), ExicomProfile)
    assert isinstance(resolve("servotech"), ServotechProfile)


def test_resolve_unknown_vendor_falls_back_to_generic():
    assert isinstance(resolve(None), GenericProfile)
    assert isinstance(resolve(""), GenericProfile)
    assert isinstance(resolve("Polestar"), GenericProfile)


def test_exicom_maps_error_to_otherror_when_empty():
    p = ExicomProfile()
    assert p.normalize_error_code(None) == "OtherError"
    assert p.normalize_error_code("EmergencyShutdown") == "OtherError"
    # mapped value
    assert p.normalize_error_code("RelayStuck") == "PowerSwitchFailure"


def test_exicom_remaps_error_status_to_faulted():
    assert ExicomProfile().normalize_status("Error") == "Faulted"
    assert ExicomProfile().normalize_status("Available") == "Available"


def test_delta_normalises_voltage_phase_suffix():
    raw = [{"sampled_value": [
        {"value": "230", "measurand": "Voltage.L1"},
        {"value": "5",   "measurand": "Current.L2"},
    ]}]
    normed = DeltaProfile().normalize_meter_values(raw)
    sv = normed[0]["sampled_value"]
    assert sv[0]["measurand"] == "Voltage" and sv[0]["phase"] == "L1"
    assert sv[1]["measurand"] == "Current.Import" and sv[1]["phase"] == "L2"


def test_servotech_firmware_version_extraction():
    f = ServotechProfile.normalize_firmware_version
    assert f("FW v1.4") == "1.4"
    assert f("STC-1.4.0") == "1.4.0"
    assert f("1.4.0-beta") == "1.4.0"
    assert f(None) is None
    assert f("garbage") == "garbage"
