import keyring

from app.config import (
    KEYRING_CLEARED_SENTINEL,
    delete_api_key,
    get_api_key,
    set_api_key,
)


class FakeKeyring:
    def __init__(self, failing_services=()):
        self._store: dict[tuple[str, str], str] = {}
        self._failing_services = set(failing_services)

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        if service in self._failing_services:
            raise keyring.errors.KeyringError("denied")
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        key = (service, username)
        if key not in self._store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self._store[key]


def test_set_and_get_api_key(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    set_api_key("sk-test-123")

    assert get_api_key() == "sk-test-123"


def test_get_api_key_returns_none_when_missing(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)

    assert get_api_key() is None


def test_delete_api_key_marks_value_as_cleared(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)
    set_api_key("sk-test-123")

    delete_api_key()

    assert get_api_key() is None
    assert (
        fake.get_password("VoiceCanvas", "minimax_api_key")
        == KEYRING_CLEARED_SENTINEL
    )


def test_delete_api_key_marks_missing_value_as_cleared(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    delete_api_key()

    assert (
        fake.get_password("VoiceCanvas", "minimax_api_key")
        == KEYRING_CLEARED_SENTINEL
    )


def test_get_api_key_prefers_voicecanvas_value(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    fake.set_password("VoiceCanvas", "minimax_api_key", "new")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    assert get_api_key() == "new"


def test_get_api_key_migrates_legacy_value(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    assert get_api_key() == "old"
    assert fake.get_password("VoiceCanvas", "minimax_api_key") == "old"
    assert fake.get_password("VoiceMax", "minimax_api_key") == "old"


def test_get_api_key_uses_legacy_value_when_copy_fails(monkeypatch):
    fake = FakeKeyring(failing_services={"VoiceCanvas"})
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    assert get_api_key() == "old"


def test_delete_api_key_does_not_resurrect_legacy_value(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    delete_api_key()

    assert get_api_key() is None
    assert (
        fake.get_password("VoiceCanvas", "minimax_api_key")
        == KEYRING_CLEARED_SENTINEL
    )
    assert fake.get_password("VoiceMax", "minimax_api_key") == "old"
