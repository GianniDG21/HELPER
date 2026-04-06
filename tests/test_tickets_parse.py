import pytest

from app.db.repositories.tickets import parse_ticket_pk


def test_parse_ticket_pk_ok():
    assert parse_ticket_pk(" 42 ") == 42


def test_parse_ticket_pk_invalid():
    with pytest.raises(ValueError, match="ID pratica"):
        parse_ticket_pk("abc")
    with pytest.raises(ValueError, match="ID pratica"):
        parse_ticket_pk("0")
    with pytest.raises(ValueError, match="ID pratica"):
        parse_ticket_pk("-1")
