import pytest


@pytest.fixture
def isolated_app_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICEMAX_APP_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def db(isolated_app_dir):
    from app.db import init_db

    init_db()
    return isolated_app_dir
