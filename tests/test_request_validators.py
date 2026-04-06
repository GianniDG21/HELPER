import pytest
from pydantic import ValidationError


def test_intake_contact_all_required_when_any_field_set():
    from app.schemas.api import IntakeChatRequest

    with pytest.raises(ValidationError):
        IntakeChatRequest(
            message="ciao",
            contact_first_name="A",
            contact_last_name="",
            contact_email="",
        )


def test_intake_contact_optional_when_all_empty():
    from app.schemas.api import IntakeChatRequest

    r = IntakeChatRequest(message="solo messaggio senza modulo")
    assert r.contact_first_name is None
    assert "solo messaggio" in r.human_message_content()


def test_intake_rejects_bad_email_format():
    from app.schemas.api import IntakeChatRequest

    with pytest.raises(ValidationError, match="email"):
        IntakeChatRequest(
            message="x",
            contact_first_name="A",
            contact_last_name="B",
            contact_email="non-email",
        )
