"""Synthetic demo dataset: contents, target safeguards, idempotency, conflicts, PIN hashing and access scope."""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Facility, Patient, RiskFlag, User, UserRole, Visit
from app.db.session import get_session_local
from app.demo import seed_demo_dataset as seed
from app.main import app
from app.services.auth_service import hash_pin
from app.services.pins import verify_pin

DEMO_PIN = "8523"  # the documented shared demo PIN (tests only; never used in production)
PHONES = ["9000000006", "9000000007", "9000000008", "9000000009", "9000000010"]


@pytest.fixture()
def isolated_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}", future=True)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db


def _counts(db):
    return {
        "workers": db.query(User).filter(User.phone.in_(PHONES)).count(),
        "patients": db.query(Patient).filter(Patient.name.like("Demo Patient %")).count(),
        "visits": db.query(Visit).join(Patient, Visit.patient_id == Patient.id).filter(Patient.name.like("Demo Patient %")).count(),
        "flags": db.query(RiskFlag).join(Visit, RiskFlag.visit_id == Visit.id).join(Patient, Visit.patient_id == Patient.id).filter(Patient.name.like("Demo Patient %")).count(),
    }


# ---------------------------------------------------------------- dataset contents

def test_dataset_shape_and_variety():
    data = seed.load_dataset()
    assert [w["phone"] for w in data["workers"]] == PHONES
    assert [w["name"] for w in data["workers"]] == [f"Demo Worker {i}" for i in range(1, 6)]
    assert len(data["patients"]) == 15
    per_worker = {w["key"]: 0 for w in data["workers"]}
    levels, escalations = set(), 0
    for patient in data["patients"]:
        per_worker[patient["worker_key"]] += 1
        assert patient["name"].startswith("Demo Patient ")
        assert len(patient["visits"]) == 4
        assert [v["days_ago"] for v in patient["visits"]] == sorted((v["days_ago"] for v in patient["visits"]), reverse=True)
        for v in patient["visits"]:
            levels.add(v["trend_adjusted_level"])
            escalations += v["model_risk_level"] != v["trend_adjusted_level"]
    assert set(per_worker.values()) == {3}
    assert levels == {"green", "yellow", "red"}
    assert escalations > 0
    assert "pin" not in Path(seed.DATASET_PATH).read_text(encoding="utf-8").lower()


# ---------------------------------------------------------------- target safeguards

@pytest.mark.parametrize("url", [
    "mysql+pymysql://u:p@herdoc-db-demo.aivencloud.com:12345/defaultdb",
    "postgresql://u:p@dpg-x.oregon-postgres.render.com/db",
    "mysql+pymysql://u:p@db.example.org:3306/herdoc",
])
def test_non_local_or_production_hosts_are_refused(url):
    with pytest.raises(seed.DemoSeedError):
        seed.assess_target(make_url(url), is_production=False, environ={})


def test_production_settings_and_render_are_refused():
    local = make_url("mysql+pymysql://u:p@localhost/herdoc")
    with pytest.raises(seed.DemoSeedError):
        seed.assess_target(local, is_production=True, environ={})
    with pytest.raises(seed.DemoSeedError):
        seed.assess_target(local, is_production=False, environ={"RENDER": "true"})


def test_known_production_host_refused_even_if_explicitly_allowed():
    url = make_url("mysql+pymysql://u:p@herdoc-db.aivencloud.com:12345/defaultdb")
    with pytest.raises(seed.DemoSeedError):
        seed.assess_target(url, is_production=False, environ={}, allow_remote_host="herdoc-db.aivencloud.com")


def test_local_and_explicit_demo_targets_allowed_without_credentials_in_summary():
    local = seed.assess_target(make_url("mysql+pymysql://user:SECRETPW@localhost/herdoc"), is_production=False, environ={})
    assert "localhost" in local and "SECRETPW" not in local and "user" not in local
    assert "demo.db" in seed.assess_target(make_url("sqlite:///./demo.db"), is_production=False, environ={})
    remote = seed.assess_target(make_url("mysql+pymysql://u:SECRETPW@demo-db.internal/herdoc"), is_production=False, environ={}, allow_remote_host="demo-db.internal")
    assert "SECRETPW" not in remote


def test_cli_refuses_without_demo_flag(capsys):
    assert seed.main([]) == 2
    assert "Nothing was written" in capsys.readouterr().err


# ---------------------------------------------------------------- seeding behaviour

def test_seed_creates_expected_records_with_hashed_pins(isolated_db):
    report = seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    assert report.created == {"workers": 5, "patients": 15, "visits": 60, "risk_flags": 60}
    assert report.facility_created is True
    assert _counts(isolated_db) == {"workers": 5, "patients": 15, "visits": 60, "flags": 60}

    workers = isolated_db.query(User).filter(User.phone.in_(PHONES)).order_by(User.phone).all()
    assert [w.phone for w in workers] == PHONES
    for worker in workers:
        assert worker.role == UserRole.WORKER.value and worker.is_active
        assert worker.pin_hash and worker.pin_hash != DEMO_PIN and DEMO_PIN not in worker.pin_hash
        assert verify_pin(DEMO_PIN, worker.pin_hash)
        assert not verify_pin("8524", worker.pin_hash)
        patients = isolated_db.query(Patient).filter(Patient.worker_id == worker.id).all()
        assert len(patients) == 3
        for patient in patients:
            visits = isolated_db.query(Visit).filter(Visit.patient_id == patient.id).order_by(Visit.created_locally_at).all()
            assert len(visits) == 4
            assert [v.visit_date for v in visits] == sorted(v.visit_date for v in visits)
            assert all(len(v.risk_flags) == 1 for v in visits)


def test_rerun_is_idempotent(isolated_db):
    seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    hashes = {w.phone: w.pin_hash for w in isolated_db.query(User).filter(User.phone.in_(PHONES))}
    again = seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    assert again.created == {"workers": 0, "patients": 0, "visits": 0, "risk_flags": 0}
    assert again.existing == {"workers": 5, "patients": 15, "visits": 60, "risk_flags": 60}
    assert again.facility_created is False
    assert _counts(isolated_db) == {"workers": 5, "patients": 15, "visits": 60, "flags": 60}
    assert {w.phone: w.pin_hash for w in isolated_db.query(User).filter(User.phone.in_(PHONES))} == hashes


def test_conflicting_non_demo_account_stops_before_any_write(isolated_db):
    facility = Facility(id=uuid.uuid4(), name="Real PHC", region="North", type="PHC")
    isolated_db.add(facility)
    real = User(id=uuid.uuid4(), role="worker", name="Real Worker", phone=PHONES[2], pin_hash=hash_pin("2580"),
                facility_id=facility.id, is_active=True, failed_login_attempts=0)
    isolated_db.add(real)
    isolated_db.commit()
    real_hash = real.pin_hash

    with pytest.raises(seed.DemoSeedError, match="Nothing was written"):
        seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    isolated_db.expire_all()
    assert isolated_db.query(User).count() == 1
    assert isolated_db.query(Patient).count() == 0 and isolated_db.query(Visit).count() == 0
    kept = isolated_db.get(User, real.id)
    assert kept.name == "Real Worker" and kept.pin_hash == real_hash


def test_existing_records_are_left_unchanged(isolated_db):
    facility = Facility(id=uuid.uuid4(), name="Demo PHC", region="North", type="PHC")
    other = User(id=uuid.uuid4(), role="worker", name="Existing Worker", phone="8123456789", pin_hash=hash_pin("2580"),
                 facility_id=facility.id, is_active=True, failed_login_attempts=0)
    isolated_db.add_all([facility, other])
    isolated_db.add(Patient(id=uuid.uuid4(), worker_id=other.id, name="Existing Patient", age=30, village="V"))
    isolated_db.commit()
    report = seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN, facility_name="Demo PHC")
    assert report.facility_created is False
    assert isolated_db.query(Facility).count() == 1
    assert isolated_db.query(Patient).filter(Patient.worker_id == other.id).count() == 1
    assert isolated_db.get(User, other.id).name == "Existing Worker"


def test_weak_demo_pin_is_rejected_without_writes(isolated_db):
    with pytest.raises(seed.DemoSeedError, match="PIN"):
        seed.seed_demo_dataset(isolated_db, pin="1234")
    assert isolated_db.query(User).count() == 0


# ---------------------------------------------------------------- through the running application

@pytest.fixture(scope="module")
def seeded_app_db():
    db = get_session_local()()
    try:
        seed.seed_demo_dataset(db, pin=DEMO_PIN, facility_name="Seed Test Facility")
    finally:
        db.close()


def _login(client, phone, pin=DEMO_PIN):
    return client.post("/api/auth/login/worker", json={"phone": phone, "pin": pin})


def test_demo_workers_sign_in_and_see_only_their_patients(seeded_app_db):
    client = TestClient(app)
    tokens = {}
    for phone in PHONES:
        resp = _login(client, phone)
        assert resp.status_code == 200, phone
        assert resp.json()["user"]["role"] == "worker"
        tokens[phone] = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert _login(client, PHONES[0], "9731").status_code == 401

    own = client.get("/api/patients", headers=tokens[PHONES[0]]).json()
    assert len(own) == 3 and all(p["name"].startswith("Demo Patient 1-") for p in own)
    visits = client.get(f"/api/patients/{own[0]['id']}/visits", headers=tokens[PHONES[0]]).json()
    assert len(visits) == 4
    assert [v["created_locally_at"] for v in visits] == sorted((v["created_locally_at"] for v in visits), reverse=True)

    others = client.get("/api/patients", headers=tokens[PHONES[1]]).json()
    for patient in others:
        assert client.get(f"/api/patients/{patient['id']}", headers=tokens[PHONES[0]]).status_code == 403
        assert client.get(f"/api/patients/{patient['id']}/visits", headers=tokens[PHONES[0]]).status_code == 403


# ---------------------------------------------------------------- production safeguards

def _production_settings():
    from app.config import Settings

    return Settings(
        _env_file=None, ENVIRONMENT="production", DATABASE_URL="mysql+pymysql://u:p@db.example.org/h",
        JWT_SECRET="d" * 48, WEB_ORIGIN="https://herdoc-web.onrender.com", TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="",
    )


def test_demo_identity_ids_match_the_dataset():
    from app.demo.identity import DEMO_DATASET_WORKER_IDS, demo_id

    assert {demo_id(w["key"]) for w in seed.load_dataset()["workers"]} == DEMO_DATASET_WORKER_IDS


def test_seed_function_refuses_production_settings_without_writing(isolated_db, monkeypatch):
    monkeypatch.setattr(seed, "get_settings", _production_settings)
    with pytest.raises(seed.DemoSeedError, match="production"):
        seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    assert isolated_db.query(User).count() == 0


def test_seed_function_refuses_render_environment_without_writing(isolated_db, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(seed.DemoSeedError):
        seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    assert isolated_db.query(User).count() == 0


def test_demo_accounts_are_identified_by_demo_id_not_phone(isolated_db):
    from app.demo.identity import demo_id
    from app.services.demo_accounts import count_active_demo_accounts, is_demo_dataset_user

    real = User(id=uuid.uuid4(), role="worker", name="Real Worker", phone=PHONES[0])
    assert is_demo_dataset_user(real) is False  # same phone as a demo worker, but not a demo record
    assert is_demo_dataset_user(User(id=demo_id("worker-1"), role="worker", name="x", phone="1")) is True

    seed.seed_demo_dataset(isolated_db, pin=DEMO_PIN)
    assert count_active_demo_accounts(isolated_db) == 5  # production startup check counts the demo workers


def test_seeded_demo_workers_cannot_sign_in_to_production(seeded_app_db, monkeypatch):
    import app.api.auth as auth_module

    client = TestClient(app)
    ordinary = User(id=uuid.uuid4(), role="worker", name="Ordinary Worker", phone=f"8{uuid.uuid4().int % 900000000:09d}",
                    pin_hash=hash_pin("2580"), is_active=True, failed_login_attempts=0)
    db = get_session_local()()
    try:
        ordinary.facility_id = db.query(Facility).filter(Facility.name == "Seed Test Facility").one().id
        db.add(ordinary)
        db.commit()
        db.refresh(ordinary)
        db.expunge(ordinary)
    finally:
        db.close()

    monkeypatch.setattr(auth_module, "get_settings", _production_settings)
    for phone in PHONES:
        for path in ("/api/auth/login/worker", "/api/auth/login/worker/web"):
            resp = client.post(path, json={"phone": phone, "pin": DEMO_PIN})
            assert resp.status_code == 401, (phone, path)
            assert "access_token" not in resp.json()
    assert client.post("/api/auth/login/worker", json={"phone": ordinary.phone, "pin": "2580"}).status_code == 200
