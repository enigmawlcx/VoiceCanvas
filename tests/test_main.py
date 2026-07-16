import json
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import create_app, find_free_port


def test_fastapi_uses_voicecanvas_brand():
    assert create_app().title == "声绘魔法 / VoiceCanvas"


def test_main_uses_voicecanvas_window_title(monkeypatch):
    calls = {}
    fake_app = object()

    class FakeThread:
        def __init__(self, target, args, daemon):
            calls["thread"] = (target, args, daemon)

        def start(self):
            calls["thread_started"] = True

    fake_webview = SimpleNamespace(
        create_window=lambda title, url: calls.setdefault("window", (title, url)),
        start=lambda: calls.setdefault("webview_started", True),
    )

    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(main_module, "_force_chinese_native_menu", lambda: None)
    monkeypatch.setattr(main_module, "_restore_native_context_menu", lambda: None)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "create_app", lambda: fake_app)
    monkeypatch.setattr(main_module, "find_free_port", lambda: 43123)
    monkeypatch.setattr(main_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(main_module.time, "sleep", lambda _: None)

    main_module.main()

    assert calls["window"] == ("声绘魔法", "http://127.0.0.1:43123")
    assert calls["thread"] == (main_module.run_server, (fake_app, 43123), True)
    assert calls["thread_started"] is True
    assert calls["webview_started"] is True


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_index_is_served():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "声绘魔法" in response.text


def test_find_free_port_returns_valid_port():
    port = find_free_port()

    assert isinstance(port, int)
    assert 1024 <= port <= 65535


async def test_unhandled_exception_response_does_not_disclose_exception():
    app = create_app()

    from fastapi import Request

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [],
            "query_string": b"",
            "server": ("127.0.0.1", 80),
        }
    )
    handler = app.exception_handlers[Exception]
    response = await handler(request, RuntimeError("敏感内部细节"))

    assert response.status_code == 500
    assert json.loads(response.body) == {"detail": "服务器内部错误"}
    assert "敏感内部细节" not in response.body.decode()
