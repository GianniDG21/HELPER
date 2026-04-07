from app.tools.intake_tools import validate_open_ticket_gate


def test_validate_open_ticket_gate_blocks_vehicle_without_required_data():
    msg = "Buon pomeriggio, ho un problema con il furgone."
    out = validate_open_ticket_gate(msg)
    assert out is not None
    assert "chilometraggio" in out.lower() or "identificativo del veicolo" in out.lower()


def test_validate_open_ticket_gate_allows_vehicle_with_identity_and_km():
    msg = "Problema al furgone Ducato 2019, targa AB123CD, 98000 km."
    out = validate_open_ticket_gate(msg)
    assert out is None
