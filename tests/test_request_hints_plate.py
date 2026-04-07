from app.intake.request_hints import (
    has_invalid_vehicle_plate_format,
    operational_gate_heuristic,
)


def test_invalid_plate_format_detected_when_targa_is_mentioned():
    txt = "Devo fare il tagliando, targa AB12CDE, 82000 km."
    assert has_invalid_vehicle_plate_format(txt) is True
    assert operational_gate_heuristic(txt) is False


def test_valid_plate_format_passes_plate_check():
    txt = "Devo fare il tagliando, targa AB123CD, 82000 km."
    assert has_invalid_vehicle_plate_format(txt) is False
    assert operational_gate_heuristic(txt) is True
