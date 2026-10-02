# HERDOC DevOps CA — presentation content

## Slide 1 — HERDOC Architecture

- Offline-first Expo app for frontline workers and React/Vite doctor portal.
- FastAPI backend provides authentication, synchronization, and review endpoints.
- MySQL is the server database; Alembic manages schema changes.
- Docker/Kubernetes package and run the existing backend; Prometheus and Grafana observe it.

**Diagram suggestion:** Use the architecture Mermaid diagram in `DEVOPS_CA.md`.

**Evidence to include:** HERDOC architecture diagram and one real application screen (no patient-identifiable data).

## Slide 2 — CI Pipeline

- GitHub Actions runs for pushes and pull requests targeting `main` or `master`.
- Python 3.11 installs `backend/requirements.txt`.
- Alembic initializes the CI-only SQLite database before pytest.
- Migration and tests share the same CI environment variables and database URL.

**Diagram suggestion:** Show Checkout → Python 3.11 → Dependencies → Alembic → pytest.

**Evidence to include:** Actual successful GitHub Actions run with the migration and pytest step results visible.

## Slide 3 — Configuration, Docker, and Kubernetes

- Ansible prepares a Linux host with Python, dedicated user, app files, environment configuration, migrations, and systemd.
- Docker image runs the HERDOC API as a non-root user and excludes `.env` files.
- Kubernetes has two replicas, Service, probes, resources, rolling update, and rollback workflow.
- Database and signing secrets are supplied outside Git.

**Diagram suggestion:** Ansible → Linux VM and Docker image → Kubernetes Deployment → Service.

**Evidence to include:** Successful image build and real Ansible/Kubernetes command output only if run.

## Slide 4 — Monitoring and Logging

- `/metrics` exports request count, 4xx/5xx errors, latency, in-progress requests, and process uptime.
- Prometheus scrapes the backend and provides scrape availability.
- Grafana dashboard shows availability, latency percentiles, error rate, request rate, and uptime.
- Request logs capture route, status, and duration without credentials or request bodies.

**Diagram suggestion:** HERDOC API → Prometheus → Grafana.

**Evidence to include:** Real `/metrics` output, Prometheus target UP page, and populated Grafana dashboard.

## Slide 5 — Challenges and Lessons Learned

- CI's fresh database had no schema until migrations were run.
- SQLite rejected the migration's original `DEFAULT now()` syntax; portable `CURRENT_TIMESTAMP` fixed schema setup.
- Migrations should be validated against the database engine used by CI.
- Deployment configuration is not proof of a running VM, container, cluster, or dashboard; capture actual output.

**Diagram suggestion:** Challenge → fix → validation: empty DB → Alembic → pytest.

**Evidence to include:** The actual workflow result and any genuine infrastructure validation; clearly mark unavailable runtime demonstrations.
