"""Emergency SOS tests. Telegram and the database are mocked: no network, no MySQL."""
import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

import app.api.emergency as emergency_module
import app.main as main_module
from app.services import telegram_service
from app.services.telegram_service import TelegramError


class FakeUser:
    id = uuid.uuid4()
    name = "ASHA Test"
    role = "worker"
    phone = "9000000001"
    facility_id = None


@pytest.fixture
def db_mock(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(emergency_module, "_get_db", lambda: db)
    return db


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "check_database_connection", lambda: None)
    return TestClient(main_module.app)


@pytest.fixture
def authed(client):
    main_module.app.dependency_overrides[emergency_module.require_emergency_user] = lambda: FakeUser()
    yield client
    main_module.app.dependency_overrides.clear()


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_service, "send_emergency_alert", lambda **kw: calls.append(kw))
    return calls


def test_unauthenticated_request_rejected(client, sent):
    assert client.post("/api/emergency", json={}).status_code == 401
    bad = client.post("/api/emergency", json={}, headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert sent == []


def test_authenticated_sos_with_location(authed, db_mock, sent):
    r = authed.post("/api/emergency", json={"latitude": 18.5, "longitude": 73.5, "message": " help "})
    assert r.status_code == 200
    assert r.json() == {"status": "sent", "location_included": True}
    assert sent[0]["latitude"] == 18.5 and sent[0]["note"] == "help"
    assert sent[0]["user_name"] == "ASHA Test"
    db_mock.add.assert_called_once()
    audit = db_mock.add.call_args[0][0]
    assert audit.event_type == "emergency.sos" and audit.event_metadata["outcome"] == "sent"
    db_mock.commit.assert_called()


def test_authenticated_sos_without_location(authed, db_mock, sent):
    r = authed.post("/api/emergency", json={})
    assert r.status_code == 200 and r.json()["location_included"] is False
    assert sent[0]["latitude"] is None


def test_telegram_failure_returns_502_and_audits(authed, db_mock, monkeypatch):
    def boom(**kw):
        raise TelegramError("Telegram request failed")

    monkeypatch.setattr(telegram_service, "send_emergency_alert", boom)
    r = authed.post("/api/emergency", json={})
    assert r.status_code == 502
    assert "token" not in r.text.lower()
    assert db_mock.add.call_args[0][0].event_metadata["outcome"] == "failed"


def test_telegram_not_configured_returns_503(authed, db_mock, monkeypatch):
    monkeypatch.setattr(
        telegram_service.get_settings(), "TELEGRAM_BOT_TOKEN", "", raising=False
    )
    monkeypatch.setattr(telegram_service.get_settings(), "TELEGRAM_CHAT_ID", "", raising=False)
    r = authed.post("/api/emergency", json={})
    assert r.status_code == 503
    assert db_mock.add.call_args[0][0].event_metadata["outcome"] == "not_configured"


@pytest.mark.parametrize(
    "body",
    [
        {"latitude": 10.0},
        {"longitude": 10.0},
        {"latitude": 91, "longitude": 0},
        {"latitude": 0, "longitude": 181},
        {"latitude": "abc", "longitude": 0},
        {"message": "x" * 301},
    ],
)
def test_invalid_input_rejected(authed, db_mock, sent, body):
    assert authed.post("/api/emergency", json=body).status_code == 422
    assert sent == []


def test_audit_failure_does_not_mask_success(authed, db_mock, sent):
    db_mock.commit.side_effect = RuntimeError("db down")
    assert authed.post("/api/emergency", json={}).status_code == 200
    db_mock.rollback.assert_called()


# ---- telegram_service unit tests (httpx mocked) ----

@pytest.fixture
def tg_settings(monkeypatch):
    s = telegram_service.get_settings()
    monkeypatch.setattr(s, "TELEGRAM_BOT_TOKEN", "123:SECRET", raising=False)
    monkeypatch.setattr(s, "TELEGRAM_CHAT_ID", "-10042", raising=False)


def test_service_posts_to_telegram_api(monkeypatch, tg_settings):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update(url=url, json=json)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(telegram_service.httpx, "post", fake_post)
    telegram_service.send_emergency_alert(
        user_name="A", role="worker", phone=None, facility_name="PHC",
        latitude=1.0, longitude=2.0, note=None,
    )
    assert captured["url"] == "https://api.telegram.org/bot123:SECRET/sendMessage"
    assert captured["json"]["chat_id"] == "-10042"
    assert "EMERGENCY" in captured["json"]["text"] and "maps.google.com" in captured["json"]["text"]


def test_service_network_error_does_not_leak_token(monkeypatch, tg_settings, caplog):
    def fake_post(url, json, timeout):
        raise httpx.ConnectError(f"failed {url}")

    monkeypatch.setattr(telegram_service.httpx, "post", fake_post)
    with pytest.raises(TelegramError) as ei:
        telegram_service.send_telegram_message("hi")
    assert "SECRET" not in str(ei.value) and "SECRET" not in caplog.text


@pytest.mark.parametrize("resp", [httpx.Response(401, json={"ok": False}), httpx.Response(200, json={"ok": False}), httpx.Response(200, text="<html>")])
def test_service_bad_responses(monkeypatch, tg_settings, resp):
    monkeypatch.setattr(telegram_service.httpx, "post", lambda url, json, timeout: resp)
    with pytest.raises(TelegramError):
        telegram_service.send_telegram_message("hi")
