from datetime import UTC, datetime

from app.db.repositories.pratiche import row_as_ticket_api_shape


def test_row_as_ticket_api_shape_maps_fields():
    created = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
    accepted = datetime(2026, 1, 15, 11, 30, 0, tzinfo=UTC)
    row = {
        "id": 7,
        "department": "manutenzione",
        "sector_ticket_id": 99,
        "requested_by_name": "Mario Rossi",
        "requested_by_email": "mario@esempio.it",
        "requested_by_phone": None,
        "company_id": None,
        "title": "Test tagliando",
        "full_summary": "Polo 2018, km 80000",
        "vehicle": "Polo",
        "part_code": None,
        "status": "pending_acceptance",
        "assigned_to": None,
        "created_at": created,
        "accepted_at": accepted,
    }
    out = row_as_ticket_api_shape(row)
    assert out["id"] == "7"
    assert out["department"] == "manutenzione"
    assert out["sector_ticket_id"] == "99"
    assert out["customer_name"] == "Mario Rossi"
    assert out["customer_email"] == "mario@esempio.it"
    assert out["status"] == "pending_acceptance"
    assert out["assigned_to"] is None
    assert out["opened_at"] == created.isoformat()
    assert out["accepted_at"] == accepted.isoformat()
