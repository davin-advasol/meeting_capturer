import pytest

from meeting_digest.errors import DigestError


def test_digest_error_is_an_exception():
    assert issubclass(DigestError, Exception)


def test_digest_error_carries_its_message():
    with pytest.raises(DigestError) as exc:
        raise DigestError("recording has no audio stream")
    assert str(exc.value) == "recording has no audio stream"
