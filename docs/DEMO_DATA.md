# HerDoc demo dataset (synthetic) — local / isolated databases only

The demo dataset lets you try the worker portal, the doctor dashboard and risk/trend views with
realistic-looking but **entirely fictional** data. It must never be loaded into the production database.

## What it creates

| Item | Count | Notes |
|------|-------|-------|
| Demo workers | 5 | `Demo Worker 1`–`Demo Worker 5`, role `worker`, in the chosen facility (default `Demo PHC`, created if missing) |
| Demo patients | 15 | 3 per worker, named `Demo Patient <worker>-<n>`, villages `Demo Village A/B/C`, no phone numbers |
| Demo visits | 60 | 4 per patient, 84, 56, 28 and 7 days before the seeding date |
| Risk flags | 60 | One per visit |

Each worker has three patients with different synthetic patterns:

- **routine** (every worker) — readings the risk model classifies green at every visit;
- **rising-bp** (workers 1, 3, 5) — blood pressure rising across visits, so the trend engine escalates the result
  (green → yellow → red);
- **recheck** (workers 2, 4) — steady green visits, then blood sugar rises at the latest visit, which the model
  classifies yellow;
- **high-risk** (every worker) — high readings the model classifies red.

By latest visit this gives 5 green, 2 yellow and 8 red patients, so the doctor dashboard shows every risk level.
Across all 60 visits: 28 green, 9 yellow and 23 red, including 6 trend escalations.

The risk results are **not hand-written**: `web/scripts/build-demo-dataset.mjs` classifies every synthetic visit with
the same risk model and trend engine the mobile app and web portal use, and stores the results in
`backend/app/demo/demo_dataset.json`. `npm run check:demo-data` (in `web/`) fails if the stored results ever
differ from the model. These are synthetic readings, not clinical records or real outcomes.

## Demo sign-in details

| Worker | Phone |
|--------|-------|
| Demo Worker 1 | 9000000006 |
| Demo Worker 2 | 9000000007 |
| Demo Worker 3 | 9000000008 |
| Demo Worker 4 | 9000000009 |
| Demo Worker 5 | 9000000010 |

All five demo workers share the demo PIN **8523**. It is supplied when seeding (it is not stored in the code or the
dataset) and saved only as a salted hash, like every other PIN.

> **Never reuse these phone numbers or this PIN in production.** They are published here for local demos only.

## Seeding (from `backend/`, PowerShell)

The seed command refuses to run unless `--demo` is given, and it refuses production settings, Render
environments, Aiven/Render database hosts and any non-local database (unless you name a dedicated demo host with
`--allow-remote-host`). It prints only a credential-free summary of the target before writing.

**Option A — a separate, throwaway SQLite database (recommended):**

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///C:/HerDocDemo/herdoc_demo.db"   # any folder outside the repository
New-Item -ItemType Directory -Force C:\HerDocDemo | Out-Null
.\venv\Scripts\python.exe -m alembic upgrade head
$env:HERDOC_DEMO_WORKER_PIN = "8523"
.\venv\Scripts\python.exe -m app.demo.seed_demo_dataset --demo
Remove-Item Env:HERDOC_DEMO_WORKER_PIN, Env:DATABASE_URL
```

**Option B — your local development database** (the `DATABASE_URL` in `backend/.env`, which must point at `localhost`):

```powershell
cd backend
.\venv\Scripts\python.exe -m app.demo.seed_demo_dataset --demo --facility-name "Demo PHC"
```

Without `HERDOC_DEMO_WORKER_PIN` set, the command asks for the PIN at a hidden prompt.

Example output:

```
Target: isolated SQLite database file 'herdoc_demo.db'
Facility 'Demo PHC': created
workers: 5 created, 0 already present
patients: 15 created, 0 already present
visits: 60 created, 0 already present
risk_flags: 60 created, 0 already present
```

## Safety properties

- **Idempotent:** every record has a stable id, so re-running creates nothing new and reports the records as
  already present. Existing demo workers keep their current PIN.
- **Never overwrites:** if any of the five phone numbers or record ids already belongs to a non-demo record, the run
  stops with "Nothing was written" and lists the conflicts.
- **Additive only:** no tables are dropped or truncated and no records are deleted or modified.
- **One transaction:** a failure part-way rolls everything back.
- **Same validation as the API:** patients and visits are validated with the same request models as
  `POST /api/patients` and `POST /api/patients/{id}/visits`, and the PIN with the normal PIN policy.

## Regenerating the dataset

Only needed if the risk model or the synthetic patterns change (from `web/`):

```powershell
node scripts/build-demo-dataset.mjs   # rewrite backend/app/demo/demo_dataset.json
npm run check:demo-data               # verify it matches the current model
```

## Removing demo data

The seed command never deletes anything. To remove the demo data, delete the throwaway SQLite file (option A). For a
shared database, remove the five demo workers and their patients/visits manually after review.
