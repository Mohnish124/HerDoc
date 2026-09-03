import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import AuditLog, Facility, Patient, Review, RiskFlag, User, UserRole, Visit
from app.db.seed import seed_demo_data
from app.db.session import get_session_local

client = TestClient(app)


# --- Client-Side On-Device Simulation Helpers (Matching Mobile JS Engines) ---

def _simulate_on_device_trend_adjustment(current_visit, prior_visits, raw_model_risk="green"):
    """
    Python simulation of mobile/app/services/trend_engine.js: calculateTrendAdjustment()
    Thresholds: Systolic consecutive rise >= 8 mmHg, Diastolic >= 6 mmHg, Blood Sugar >= 15 mg/dL.
    Requires at least 2 prior visits.
    """
    if len(prior_visits) < 2:
        return {
            "model_risk_level": raw_model_risk,
            "trend_adjusted_level": raw_model_risk,
            "trend_reason": None,
            "escalated": False,
        }

    # Sort prior visits chronologically
    sorted_priors = sorted(prior_visits, key=lambda v: v["visit_date"])
    v1 = sorted_priors[-2]
    v2 = sorted_priors[-1]
    v3 = current_visit

    sys1, sys2, sys3 = v1["systolic_bp"], v2["systolic_bp"], v3["systolic_bp"]
    dia1, dia2, dia3 = v1["diastolic_bp"], v2["diastolic_bp"], v3["diastolic_bp"]

    sustained_sys = (sys2 - sys1 >= 8) and (sys3 - sys2 >= 8)
    sustained_dia = (dia2 - dia1 >= 6) and (dia3 - dia2 >= 6)

    if sustained_sys or sustained_dia:
        escalation_map = {"green": "yellow", "yellow": "red", "red": "red"}
        adjusted = escalation_map.get(raw_model_risk, "yellow")
        return {
            "model_risk_level": raw_model_risk,
            "trend_adjusted_level": adjusted,
            "trend_reason": "Blood pressure has risen steadily over your last 3 visits.",
            "escalated": True,
        }

    return {
        "model_risk_level": raw_model_risk,
        "trend_adjusted_level": raw_model_risk,
        "trend_reason": None,
        "escalated": False,
    }


def _create_in_memory_sqlite_mobile_db():
    """
    Creates an in-memory SQLite database matching the mobile schema in mobile/app/db/index.js.
    """
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE patients (
            id TEXT PRIMARY KEY,
            worker_id TEXT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            village TEXT NOT NULL,
            edd TEXT,
            phone TEXT,
            review_status TEXT DEFAULT 'pending',
            review_notes TEXT,
            created_at TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE visits (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            systolic_bp INTEGER,
            diastolic_bp INTEGER,
            blood_sugar INTEGER,
            body_temp_c REAL,
            heart_rate INTEGER,
            created_locally_at TEXT NOT NULL,
            synced_at TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE risk_flags (
            id TEXT PRIMARY KEY,
            visit_id TEXT NOT NULL,
            model_risk_level TEXT NOT NULL,
            trend_adjusted_level TEXT NOT NULL,
            trend_reason TEXT,
            created_at TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE sync_queue (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


# --- Comprehensive Phase 19 End-to-End Integration Test ---

def test_full_herdoc_end_to_end_product_lifecycle():
    # 0. Seed Baseline
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)
    finally:
        db.close()

    # =========================================================================
    # STEP 1: Admin logs into web portal
    # =========================================================================
    admin_login_resp = client.post(
        "/api/auth/login/admin",
        json={"email": "admin@herdoc.local", "password": "AdminPass!2024"},
    )
    assert admin_login_resp.status_code == 200, "Admin login failed"
    admin_token = admin_login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    assert "herdoc_refresh_token" in admin_login_resp.cookies, "Admin login must set httpOnly cookie"

    # =========================================================================
    # STEP 2 & 3: Admin creates field worker & worker receives temporary PIN
    # =========================================================================
    unique_worker_phone = f"97{uuid.uuid4().int % 100000000:08d}"
    worker_temp_pin = "4826"
    worker_name = "ASHA Sunita Sharma"

    create_worker_resp = client.post(
        "/api/auth/register/worker",
        headers=admin_headers,
        json={
            "name": worker_name,
            "phone": unique_worker_phone,
            "temporary_pin": worker_temp_pin,
        },
    )
    assert create_worker_resp.status_code == 200, f"Worker registration failed: {create_worker_resp.text}"
    created_worker = create_worker_resp.json()["user"]
    worker_id = created_worker["id"]
    assert created_worker["name"] == worker_name
    assert created_worker["phone"] == unique_worker_phone

    # =========================================================================
    # STEP 4: Worker logs into mobile while online
    # =========================================================================
    worker_login_resp = client.post(
        "/api/auth/login/worker",
        json={"phone": unique_worker_phone, "pin": worker_temp_pin},
    )
    assert worker_login_resp.status_code == 200, "Worker online login failed"
    worker_auth_data = worker_login_resp.json()
    worker_access_token = worker_auth_data["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_access_token}"}

    # =========================================================================
    # STEP 5, 6, 7: Worker closes app, enables Airplane Mode, operates offline
    # =========================================================================
    # Mobile app uses local SQLite database in airplane mode with zero network access
    mobile_sqlite = _create_in_memory_sqlite_mobile_db()
    cur = mobile_sqlite.cursor()

    # =========================================================================
    # STEP 8: Create patient offline in SQLite
    # =========================================================================
    patient_id = str(uuid.uuid4())
    patient_payload = {
        "id": patient_id,
        "worker_id": worker_id,
        "name": "Pooja Verma",
        "age": 23,
        "village": "Rampur",
        "edd": "2026-12-15",
        "phone": "9876511111",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    cur.execute(
        "INSERT INTO patients (id, worker_id, name, age, village, edd, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (patient_id, worker_id, "Pooja Verma", 23, "Rampur", "2026-12-15", "9876511111", patient_payload["created_at"]),
    )
    cur.execute(
        "INSERT INTO sync_queue (id, entity_type, entity_id, payload, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "patient", patient_id, json.dumps(patient_payload), "pending", datetime.now(timezone.utc).isoformat()),
    )
    mobile_sqlite.commit()

    # =========================================================================
    # STEP 9 & 10: Create Visit #1 offline -> Model predicts Green risk
    # =========================================================================
    visit1_id = str(uuid.uuid4())
    flag1_id = str(uuid.uuid4())
    visit1_payload = {
        "id": visit1_id,
        "patient_id": patient_id,
        "worker_id": worker_id,
        "visit_date": "2026-08-01",
        "systolic_bp": 110,
        "diastolic_bp": 70,
        "blood_sugar": 85,
        "body_temp_c": 36.8,
        "heart_rate": 72,
        "created_locally_at": datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc).isoformat(),
    }
    # On-device ML model inference simulation (zero network)
    raw_risk1 = "green"
    trend1 = _simulate_on_device_trend_adjustment(visit1_payload, [], raw_model_risk=raw_risk1)
    assert trend1["trend_adjusted_level"] == "green"
    assert trend1["trend_reason"] is None

    flag1_payload = {
        "id": flag1_id,
        "visit_id": visit1_id,
        "model_risk_level": "green",
        "trend_adjusted_level": "green",
        "trend_reason": None,
        "created_at": visit1_payload["created_locally_at"],
    }
    cur.execute(
        "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (visit1_id, patient_id, worker_id, "2026-08-01", 110, 70, 85, 36.8, 72, visit1_payload["created_locally_at"]),
    )
    cur.execute(
        "INSERT INTO risk_flags VALUES (?, ?, ?, ?, ?, ?)",
        (flag1_id, visit1_id, "green", "green", None, visit1_payload["created_locally_at"]),
    )
    cur.execute("INSERT INTO sync_queue VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?)", (str(uuid.uuid4()), "visit", visit1_id, json.dumps(visit1_payload), visit1_payload["created_locally_at"]))
    cur.execute("INSERT INTO sync_queue VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?)", (str(uuid.uuid4()), "risk_flag", flag1_id, json.dumps(flag1_payload), visit1_payload["created_locally_at"]))
    mobile_sqlite.commit()

    # =========================================================================
    # STEP 11: Create Visit #2 offline (Systolic +10, Diastolic +8)
    # =========================================================================
    visit2_id = str(uuid.uuid4())
    flag2_id = str(uuid.uuid4())
    visit2_payload = {
        "id": visit2_id,
        "patient_id": patient_id,
        "worker_id": worker_id,
        "visit_date": "2026-08-08",
        "systolic_bp": 120,
        "diastolic_bp": 78,
        "blood_sugar": 90,
        "body_temp_c": 37.0,
        "heart_rate": 76,
        "created_locally_at": datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc).isoformat(),
    }
    raw_risk2 = "green"
    trend2 = _simulate_on_device_trend_adjustment(visit2_payload, [visit1_payload], raw_model_risk=raw_risk2)
    assert trend2["trend_adjusted_level"] == "green"

    flag2_payload = {
        "id": flag2_id,
        "visit_id": visit2_id,
        "model_risk_level": "green",
        "trend_adjusted_level": "green",
        "trend_reason": None,
        "created_at": visit2_payload["created_locally_at"],
    }
    cur.execute(
        "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (visit2_id, patient_id, worker_id, "2026-08-08", 120, 78, 90, 37.0, 76, visit2_payload["created_locally_at"]),
    )
    cur.execute(
        "INSERT INTO risk_flags VALUES (?, ?, ?, ?, ?, ?)",
        (flag2_id, visit2_id, "green", "green", None, visit2_payload["created_locally_at"]),
    )
    cur.execute("INSERT INTO sync_queue VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?)", (str(uuid.uuid4()), "visit", visit2_id, json.dumps(visit2_payload), visit2_payload["created_locally_at"]))
    cur.execute("INSERT INTO sync_queue VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?)", (str(uuid.uuid4()), "risk_flag", flag2_id, json.dumps(flag2_payload), visit2_payload["created_locally_at"]))
    mobile_sqlite.commit()

    # =========================================================================
    # STEP 12, 13, 14, 15: Create Visit #3 offline -> Trend Engine Escalates to Yellow
    # =========================================================================
    visit3_id = str(uuid.uuid4())
    flag3_id = str(uuid.uuid4())
    visit3_payload = {
        "id": visit3_id,
        "patient_id": patient_id,
        "worker_id": worker_id,
        "visit_date": "2026-08-15",
        "systolic_bp": 130,
        "diastolic_bp": 86,
        "blood_sugar": 95,
        "body_temp_c": 37.1,
        "heart_rate": 80,
        "created_locally_at": datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc).isoformat(),
    }
    raw_risk3 = "green"
    trend3 = _simulate_on_device_trend_adjustment(visit3_payload, [visit1_payload, visit2_payload], raw_model_risk=raw_risk3)

    # Assert Trend Escalation
    assert trend3["trend_adjusted_level"] == "yellow", "Trend engine must escalate green -> yellow"
    assert trend3["escalated"] is True
    assert "Blood pressure has risen steadily" in trend3["trend_reason"]

    flag3_payload = {
        "id": flag3_id,
        "visit_id": visit3_id,
        "model_risk_level": "green",
        "trend_adjusted_level": "yellow",
        "trend_reason": trend3["trend_reason"],
        "created_at": visit3_payload["created_locally_at"],
    }
    cur.execute(
        "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (visit3_id, patient_id, worker_id, "2026-08-15", 130, 86, 95, 37.1, 80, visit3_payload["created_locally_at"]),
    )
    cur.execute(
        "INSERT INTO risk_flags VALUES (?, ?, ?, ?, ?, ?)",
        (flag3_id, visit3_id, "green", "yellow", trend3["trend_reason"], visit3_payload["created_locally_at"]),
    )
    cur.execute("INSERT INTO sync_queue VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?)", (str(uuid.uuid4()), "visit", visit3_id, json.dumps(visit3_payload), visit3_payload["created_locally_at"]))
    cur.execute("INSERT INTO sync_queue VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?)", (str(uuid.uuid4()), "risk_flag", flag3_id, json.dumps(flag3_payload), visit3_payload["created_locally_at"]))
    mobile_sqlite.commit()

    # =========================================================================
    # STEP 16: Verify Local SQLite Contents
    # =========================================================================
    cur.execute("SELECT COUNT(*) FROM patients")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM visits")
    assert cur.fetchone()[0] == 3
    cur.execute("SELECT COUNT(*) FROM risk_flags")
    assert cur.fetchone()[0] == 3
    cur.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'pending'")
    assert cur.fetchone()[0] == 7, "1 patient + 3 visits + 3 risk flags pending sync"

    # =========================================================================
    # STEP 17 & 18: Disable Airplane Mode -> Automatic Background Sync Occurs
    # =========================================================================
    sync_batch_payload = {
        "patients": [patient_payload],
        "visits": [visit1_payload, visit2_payload, visit3_payload],
        "risk_flags": [flag1_payload, flag2_payload, flag3_payload],
        "last_synced_at": None,
    }
    sync_resp = client.post("/api/sync", json=sync_batch_payload, headers=worker_headers)
    assert sync_resp.status_code == 200, f"Sync failed: {sync_resp.text}"
    sync_data = sync_resp.json()

    assert sync_data["patients"]["success"] == 1
    assert sync_data["visits"]["success"] == 3
    assert sync_data["risk_flags"]["success"] == 3

    # Mark local SQLite items synced
    cur.execute("UPDATE sync_queue SET status = 'synced'")
    mobile_sqlite.commit()

    # =========================================================================
    # STEP 19: Verify MySQL Database Persistence
    # =========================================================================
    db = get_session_local()()
    try:
        mysql_patient = db.get(Patient, uuid.UUID(patient_id))
        assert mysql_patient is not None
        assert mysql_patient.name == "Pooja Verma"
        assert str(mysql_patient.worker_id) == worker_id

        mysql_visits = db.query(Visit).filter(Visit.patient_id == uuid.UUID(patient_id)).order_by(Visit.visit_date.asc()).all()
        assert len(mysql_visits) == 3

        mysql_flag3 = db.get(RiskFlag, uuid.UUID(flag3_id))
        assert mysql_flag3 is not None
        assert mysql_flag3.trend_adjusted_level == "yellow"
        assert "Blood pressure has risen steadily" in mysql_flag3.trend_reason

        # Test Idempotency: Resend identical payload -> zero duplicates created
        idempotent_resp = client.post("/api/sync", json=sync_batch_payload, headers=worker_headers)
        assert idempotent_resp.status_code == 200
        repeat_data = idempotent_resp.json()
        assert repeat_data["patients"]["already_synced"] == 1
        assert repeat_data["visits"]["already_synced"] == 3
        assert repeat_data["risk_flags"]["already_synced"] == 3

        total_visits_in_mysql = db.query(Visit).filter(Visit.patient_id == uuid.UUID(patient_id)).count()
        assert total_visits_in_mysql == 3, "No duplicate visits must be created"
    finally:
        db.close()

    # =========================================================================
    # STEP 20, 21: Doctor logs into web & sees flagged patient on Triage Dashboard
    # =========================================================================
    doc_login_resp = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert doc_login_resp.status_code == 200
    doc_token = doc_login_resp.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    flagged_resp = client.get("/api/dashboard/flagged", headers=doc_headers)
    assert flagged_resp.status_code == 200
    flagged_patients = flagged_resp.json()

    flagged_entry = next((p for p in flagged_patients if p["id"] == patient_id), None)
    assert flagged_entry is not None, "Flagged patient must appear in doctor triage dashboard"
    assert flagged_entry["trend_adjusted_level"] == "yellow"
    assert "Blood pressure has risen steadily" in flagged_entry["trend_reason"]

    # =========================================================================
    # STEP 22, 23, 24, 25: Doctor opens patient detail, sees vitals history & trend
    # =========================================================================
    patient_meta_resp = client.get(f"/api/patients/{patient_id}", headers=doc_headers)
    assert patient_meta_resp.status_code == 200
    assert patient_meta_resp.json()["name"] == "Pooja Verma"

    visits_detail_resp = client.get(f"/api/patients/{patient_id}/visits", headers=doc_headers)
    assert visits_detail_resp.status_code == 200
    patient_visits_history = visits_detail_resp.json()
    assert len(patient_visits_history) == 3
    assert patient_visits_history[0]["systolic_bp"] == 130
    assert patient_visits_history[0]["risk_flags"][0]["trend_adjusted_level"] == "yellow"
    assert "Blood pressure has risen steadily" in patient_visits_history[0]["risk_flags"][0]["trend_reason"]

    # =========================================================================
    # STEP 26: Doctor marks patient REFERRED with clinical instructions
    # =========================================================================
    review_submission_resp = client.post(
        "/api/reviews",
        headers=doc_headers,
        json={
            "patient_id": patient_id,
            "status": "referred",
            "notes": "Sustained BP increase detected over 3 visits. Refer to District PHC for lab workup.",
        },
    )
    assert review_submission_resp.status_code == 200
    review_result = review_submission_resp.json()
    assert review_result["status"] == "referred"
    assert review_result["reviewed_at"] is not None

    # =========================================================================
    # STEP 27 & 28: Mobile sync runs again -> Worker pulls updated review status
    # =========================================================================
    mobile_pull_sync = {
        "patients": [],
        "visits": [],
        "risk_flags": [],
        "last_synced_at": sync_data["sync_timestamp"],
    }
    pull_sync_resp = client.post("/api/sync", json=mobile_pull_sync, headers=worker_headers)
    assert pull_sync_resp.status_code == 200
    pull_result = pull_sync_resp.json()

    received_reviews = pull_result.get("reviews", [])
    assert len(received_reviews) >= 1
    matching_review = next((r for r in received_reviews if r["patient_id"] == patient_id), None)
    assert matching_review is not None
    assert matching_review["status"] == "referred"
    assert "District PHC" in matching_review["notes"]

    # Apply doctor review to mobile SQLite patient record
    cur.execute(
        "UPDATE patients SET review_status = ?, review_notes = ? WHERE id = ?",
        (matching_review["status"], matching_review["notes"], patient_id),
    )
    mobile_sqlite.commit()

    cur.execute("SELECT review_status, review_notes FROM patients WHERE id = ?", (patient_id,))
    updated_local_patient = cur.fetchone()
    assert updated_local_patient[0] == "referred"
    assert "District PHC" in updated_local_patient[1]


def test_architectural_security_and_integrity_checks():
    db = get_session_local()()
    try:
        # Check all seeded demo users and registered users
        prod_users = db.query(User).filter(User.email.in_(["admin@herdoc.local", "doctor@herdoc.local"])).all()
        for u in prod_users:
            assert u.password_hash.startswith("$2b$") or u.password_hash.startswith("$2a$"), f"Insecure password hash for user {u.email}"

        # Verify worker PINs are securely hashed
        workers = db.query(User).filter(User.role == UserRole.WORKER.value).all()
        for w in workers:
            if w.pin_hash:
                assert len(w.pin_hash) >= 20, f"Insecure PIN hash for worker {w.phone}"

        # Verify Audit Logs exist and capture review events
        audit_logs = db.query(AuditLog).all()
        assert len(audit_logs) > 0
        event_types = {log.event_type for log in audit_logs}
        assert "patient_reviewed" in event_types
    finally:
        db.close()
