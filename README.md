# HerDoc: Offline-First AI Maternal Risk Triage Platform

**HerDoc** is an offline-first clinical decision support and maternal risk escalation platform designed for frontline health workers (ASHA / ANM) and Primary Health Centre (PHC) doctors in rural and low-resource healthcare settings.

The platform enables continuous maternal health tracking in zero-connectivity environments, runs on-device Machine Learning inference directly on mobile phones, detects progressive deterioration via consecutive-visit trend analysis, and synchronizes securely with a centralized hospital database upon network restoration.

---

## 1. System Architecture

```
                                  ┌───────────────────────────────┐
                                  │   Frontline Health Worker     │
                                  │    (ASHA / ANM on Android)    │
                                  └───────────────┬───────────────┘
                                                  │
                                   Offline-First Mobile Stack
                                   • Expo / React Native
                                   • Local SQLite Encrypted DB
                                   • On-Device ML Inference Engine
                                   • 3-Visit Trend Escalation Engine
                                   • Idempotent Sync Queue
                                                  │
                                                  │ (When Online via /api/sync)
                                                  ▼
┌───────────────────────────────┐          ┌───────────────────────────────┐
│     PHC Medical Doctor        │◄────────►│     HerDoc FastAPI Backend    │
│  • React + Vite Portal        │  HTTPS   │  • Auth & Session Security    │
│  • Triage Queue (Red/Yellow)  │  Bearer/ │  • Bidirectional Sync Engine  │
│  • Trajectory Vitals Matrix   │  Cookie  │  • RBAC & Facility Isolation  │
│  • Clinical Review Decision   │          │  • Audit Logging Pipeline     │
└───────────────────────────────┘          └───────────────┬───────────────┘
                                                           │
                                                           ▼
                                           ┌───────────────────────────────┐
                                           │    Authoritative Server DB    │
                                           │    • MySQL 8.0+ (InnoDB)      │
                                           │    • UUID Binary(16) Keys     │
                                           │    • Alembic Schema Migration │
                                           └───────────────────────────────┘
```

---

## 2. System Requirements

- **Python**: `3.10` or higher (tested on Python 3.11, 3.12, 3.14)
- **Node.js**: `18.x` or higher (with `npm` 9+)
- **Database**: MySQL `8.0` or higher (InnoDB engine with `utf8mb4`)
- **Mobile Development**: Expo CLI (`npx expo`), Android Studio / Android SDK (or Expo Go / EAS Build)

---

## 3. MySQL Database Setup

1. Start your local or cloud MySQL server instance.
2. Log into the MySQL client:
   ```sql
   CREATE DATABASE herdoc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER IF NOT EXISTS 'herdoc_user'@'localhost' IDENTIFIED BY 'HerDocSecurePass!2024';
   GRANT ALL PRIVILEGES ON herdoc.* TO 'herdoc_user'@'localhost';
   FLUSH PRIVILEGES;
   ```
3. Your database connection string will follow the standard SQLAlchemy format:
   ```text
   DATABASE_URL=mysql+pymysql://herdoc_user:HerDocSecurePass!2024@127.0.0.1:3306/herdoc?charset=utf8mb4
   ```

---

## 4. Backend Setup (FastAPI & Python)

1. Open a terminal in the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     py -3 -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Configure environment variables in `backend/.env` (see Section 7).
5. Apply database migrations and seed baseline accounts:
   ```bash
   alembic upgrade head
   python -m app.db.seed
   ```
6. Start the API development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   - Swagger / OpenAPI Documentation: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`

---

## 5. Web Portal Setup (React + Vite)

1. Open a terminal in the `web/` directory:
   ```bash
   cd web
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Configure environment variables in `web/.env`:
   ```bash
   VITE_API_BASE_URL=http://localhost:8000
   ```
4. Start the Vite local development server:
   ```bash
   npm run dev
   ```
   The portal will be accessible at `http://localhost:5173`.

---

## 6. Mobile Application Setup (Expo / React Native)

1. Open a terminal in the `mobile/` directory:
   ```bash
   cd mobile
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Configure environment variables in `mobile/.env`:
   ```bash
   EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000
   ```
   *(Note: Use `http://10.0.2.2:8000` for Android Emulator, or your local machine IP e.g. `http://192.168.1.100:8000` for physical devices)*.
4. Start the Expo server:
   ```bash
   npx expo start
   ```

---

## 7. Environment Variables Reference

### Backend (`backend/.env`)
```ini
DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/herdoc?charset=utf8mb4
JWT_SECRET=super_secure_herdoc_jwt_secret_key_minimum_32_characters_long!
WEB_ORIGIN=http://localhost:5173
```

### Web (`web/.env`)
```ini
VITE_API_BASE_URL=http://localhost:8000
```

### Mobile (`mobile/.env`)
```ini
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000
```

---

## 8. Database Migrations (Alembic)

The backend uses **Alembic** to manage database revisions:
- **Run all migrations**:
  ```bash
  alembic upgrade head
  ```
- **Create a new migration after updating models**:
  ```bash
  alembic revision --autogenerate -m "Add new column"
  ```
- **Roll back last migration**:
  ```bash
  alembic downgrade -1
  ```

---

## 9. Seed Data & Default Credentials

Run the database seeder to initialize the standard Primary Health Centre hierarchy, sample patients, and default user accounts:

```bash
python -m app.db.seed
```

| Role | Identifier / Email | Password / PIN | Permissions & Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@herdoc.local` | `AdminPass!2024` | Worker onboarding, PIN provisioning, deactivation, facility metrics |
| **PHC Doctor** | `doctor@herdoc.local` | `DoctorPass!2024` | Triage queue, patient detail history, clinical review decisioning |
| **ASHA Worker** | Phone: `9000000003` | PIN: `2468` | Offline registration, vitals recording, ML inference, sync queue |

---

## 10. Running the Test Suite

Execute the comprehensive automated test suite (167 tests covering authentication, database schema, ML inference, trend escalation, mobile sync, and security):

```bash
cd backend
py -3 -m pytest -v
```

---

## 11. Machine Learning Training Pipeline

The maternal risk classifier is trained on normalized clinical observations (Age, Systolic BP, Diastolic BP, Blood Sugar, Body Temperature, Heart Rate):

1. **Dataset Location**: `backend/ml/data/maternal_health_risk.csv`
2. **Execute Training Script**:
   ```bash
   cd backend
   python ml/train.py
   ```
3. **Artifacts Output**:
   - `backend/ml/exported/maternal_risk_model_bundle.json`: Contains the decision tree ensemble, thresholds, and standard scaler mean/scale vectors.
   - `backend/ml/exported/model_evaluation_metrics.json`: Accuracy, Precision, Recall, and Confusion Matrix.

---

## 12. Mobile Machine Learning Integration

To ensure 100% offline autonomy:
1. The exported JSON tree bundle is bundled directly into the mobile application asset tree at `mobile/app/ml/maternal_risk_model_bundle.json`.
2. The pure JavaScript on-device inference service ([`inference.js`](file:///c:/Users/sidha/Documents/trae_projects/HerDoc/mobile/app/services/inference.js)) parses the decision trees and evaluates feature thresholds recursively with **zero network latency and zero server dependencies**.

---

## 13. Expo Development Build Requirements

HerDoc uses `expo-sqlite` for client-side persistence and `expo-secure-store` for cryptographic token storage.
- **Local Testing**: Run `npx expo start` to test on Expo Go or local simulators.
- **Native Android Build**:
  ```bash
  npx eas-cli build --profile development --platform android
  ```

---

## 14. Production Deployment Guidelines

### Backend (FastAPI + Gunicorn / Uvicorn)
- Deploy behind a reverse proxy (e.g. Nginx, Caddy, or AWS ALB) terminating SSL/TLS.
- Launch with multiple worker processes:
  ```bash
  gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
  ```
- Enforce strict environment variables: set a cryptographically random `JWT_SECRET` ($\ge 64$ chars) and explicit `WEB_ORIGIN`.

### Web Portal (React + Vite)
- Generate optimized static production bundle:
  ```bash
  cd web
  npm run build
  ```
- Serve the generated `dist/` directory via Nginx, Cloudflare Pages, Vercel, or AWS S3 + CloudFront with standard single-page app (SPA) rewrite rules.

---

## 15. Complete End-to-End Demo Walkthrough

Follow this step-by-step clinical scenario to demonstrate the full end-to-end capabilities of HerDoc:

### Step 1: Admin Provisions Field Worker
1. Log into the Web Portal at `http://localhost:5173` as `admin@herdoc.local` (`AdminPass!2024`).
2. Navigate to **Field Workers** (`/workers`) and click **+ Add Field Worker**.
3. Register a new ASHA worker (Name: `ASHA Rekha`, Phone: `9876500001`, Temporary PIN: `3579`).
4. The web portal securely displays the one-time temporary PIN for handover.

### Step 2: Worker Logs in Online & Enters Offline Field Mode
1. On the mobile app, log in using Phone: `9876500001` and PIN: `3579`.
2. The app stores the session profile in local secure storage.
3. Switch the device to **Airplane Mode** (simulate entering a remote village with zero cellular connectivity).

### Step 3: Register Patient & Record 3 Consecutive Visits Offline
1. Click **+ Register New Patient** and create `Kavita Devi` (Age: 24, Village: Rampur, EDD: 2026-12-01).
2. **Visit #1 (Baseline)**: Record Systolic BP: `110`, Diastolic BP: `70`, Blood Sugar: `85 mg/dL`.
   - On-device ML predicts: **Green (Low Risk)**.
3. **Visit #2 (Week 2)**: Record Systolic BP: `120`, Diastolic BP: `78`, Blood Sugar: `90 mg/dL`.
   - On-device ML predicts: **Green**. Single rise does not escalate.
4. **Visit #3 (Week 3)**: Record Systolic BP: `130`, Diastolic BP: `86`, Blood Sugar: `95 mg/dL`.
   - On-device ML predicts: **Green**.
   - **Trend Engine Intervenes**: Detects steady, progressive blood pressure rise ($\ge 8\text{ mmHg}$ systolic / $\ge 6\text{ mmHg}$ diastolic across 3 consecutive visits).
   - Risk automatically escalates to **Yellow (Moderate Risk / Trend Escalated)** with reason: *"Blood pressure has risen steadily over your last 3 visits."*
5. All 3 visits and flags remain safely queued in mobile SQLite.

### Step 4: Worker Reconnects & Synchronizes
1. Turn off **Airplane Mode** (reconnecting to network).
2. Tap **Sync Now** or let background sync trigger.
3. All pending offline records are sent in an idempotent batch to `POST /api/sync` and persisted in the MySQL server database.

### Step 5: Doctor Triages & Reviews Flagged Case
1. Log into the Web Portal as `doctor@herdoc.local` (`DoctorPass!2024`).
2. Navigate to the **Triage Queue** (`/dashboard`).
3. `Kavita Devi` appears prominently at the top of the flagged triage list with a **Yellow** trend escalation badge and explicit clinical reason.
4. Click on the patient row to open **Patient Detail** (`/patients/{id}`).
5. Inspect the interactive **Recharts Trajectory Graph** showing systolic and diastolic progression across visits.
6. In the **Doctor Review Panel**, select **Referred to PHC**, add notes (*"Sustained BP increase detected. Schedule lab workup."*), and click **Submit Review Decision**.

### Step 6: Mobile Pulls Review Decision
1. On the mobile app, the worker performs a sync pull.
2. The patient's status updates locally to **Referred** with the doctor's clinical notes displayed on the worker's home screen.
