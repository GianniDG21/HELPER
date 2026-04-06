import uuid

from app.uuid_utils import uuid_equal


def test_uuid_equal_same_canonical():
    u = uuid.uuid4()
    assert uuid_equal(u, str(u))
    assert uuid_equal(str(u).upper(), str(u).lower())


def test_uuid_equal_different():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert not uuid_equal(a, b)


def test_uuid_equal_invalid():
    assert not uuid_equal("not-a-uuid", uuid.uuid4())
    assert not uuid_equal("", "")
