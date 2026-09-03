from fastapi.testclient import TestClient

import app.main as main_module


def test_root_health_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "check_database_connection", lambda: None)
    client = TestClient(main_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
