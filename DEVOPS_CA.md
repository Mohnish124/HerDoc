# HERDOC DevOps CA

## 1. Project overview

HERDOC is an offline-first maternal risk triage application. This DevOps setup works with the existing FastAPI backend, SQLAlchemy models and Alembic migrations, React/Vite web portal, and Expo mobile client. It does not replace the backend or claim a public deployment.

## 2. Architecture

```mermaid
flowchart LR
  Mobile[Expo mobile app] -->|HTTPS API and sync| API[FastAPI HERDOC backend]
  Web[React and Vite portal] -->|HTTPS API| API
  API --> DB[(MySQL database)]
  API -->|/metrics| Prom[Prometheus]
  Prom --> Grafana[Grafana dashboard]
  Git[GitHub push or pull request] --> Actions[GitHub Actions CI]
  Actions --> Alembic[Alembic migrations]
  Alembic --> Test[pytest]
  API -. Docker image and Kubernetes manifests .-> K8s[Kubernetes Deployment and Service]
  Ansible[Ansible playbook] -. configures Linux VM .-> API
```

The application database remains MySQL. SQLite is configured only for the isolated GitHub Actions CI run. In Kubernetes or on a VM, HERDOC expects a reachable MySQL database URL supplied through a secret or protected environment file.

## 3. CI/CD pipeline

`.github/workflows/herdoc-ci.yml` runs on pushes and pull requests targeting `main` or `master`: checkout, Python 3.11, install `backend/requirements.txt`, run `alembic upgrade head`, and run `pytest`. Both database commands use the same CI-only SQLite URL and environment variables (`PYTHONPATH`, `DATABASE_URL`, `JWT_SECRET`, and `WEB_ORIGIN`). The initial migration uses `CURRENT_TIMESTAMP`, which is accepted by SQLite and MySQL; this fixes the SQLite syntax failure discovered while validating the migration step.

The workflow currently validates the backend; it does not build/publish an image or deploy to Kubernetes. Docker build and Kubernetes deployment are manual release steps documented below. No registry or cluster credentials are configured in CI.

```mermaid
flowchart TD
  Push[GitHub push or pull request] --> Checkout[Checkout]
  Checkout --> Python[Set up Python 3.11]
  Python --> Deps[Install backend requirements]
  Deps --> Migrate[alembic upgrade head on CI SQLite]
  Migrate --> Pytest[pytest with the same database]
```

## 4. Ansible configuration management

`ansible/inventory.example.ini` provides a reserved example address and the account `vboxuser`. Ansible is installed on the Ubuntu target itself, so copy it to the ignored local `ansible/inventory.ini` and use `ansible_connection=local` while running the controller as `vboxuser`; this avoids putting a machine-specific address in the inventory. A separate Linux controller can instead set `ansible_host` to the target's reachable address. `ansible/playbook.yml` installs Python runtime packages, creates a dedicated system user and group, copies only backend runtime and migration files, creates a virtual environment, installs dependencies, writes a root-managed mode `0640` environment file, runs Alembic once, and manages a systemd service. The systemd unit uses a restricted service account and basic process hardening.

The operator supplies `HERDOC_DATABASE_URL` and a random `HERDOC_JWT_SECRET` in their shell. No secret values or machine-specific host addresses are stored in the committed example inventory. The user reports that the Ubuntu VM is running and SSH has been verified; this Windows environment has no Ansible CLI or WSL, so no Ansible syntax check or live playbook run has been performed here. Run the following commands on the Linux Ansible control node after copying and configuring its local inventory:

```powershell
read -rsp 'MySQL URL: ' HERDOC_DATABASE_URL; echo
export HERDOC_DATABASE_URL
export HERDOC_JWT_SECRET="$(openssl rand -hex 32)"
test -f ansible/inventory.ini || cp ansible/inventory.example.ini ansible/inventory.ini
# Edit ansible/inventory.ini locally; use ansible_connection=local and ansible_user=vboxuser.
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --ask-become-pass
unset HERDOC_DATABASE_URL HERDOC_JWT_SECRET
```

The VM needs outbound package access and network access to the database. A real VM deployment must be run by the operator; the example reserved IP is intentionally not deployable.

## 5. Docker

`backend/Dockerfile` builds the real FastAPI backend on Python 3.11 slim, installs the backend requirements, copies app and Alembic files, runs as a non-root account, exposes port 8000, and starts Uvicorn. `backend/.dockerignore` excludes local environment files, virtual environments, test data, and caches. Configuration is passed through environment variables, not copied secrets.

From the repository root, with a reachable MySQL database and safe local environment values:

```powershell
docker build -t herdoc-backend:latest -f backend/Dockerfile backend
docker run --rm -p 8000:8000 `
  -e DATABASE_URL='mysql+pymysql://USER:PASSWORD@HOST:3306/herdoc?charset=utf8mb4' `
  -e JWT_SECRET='<random-32+-character-secret>' `
  -e WEB_ORIGIN='http://localhost:3000' `
  herdoc-backend:latest
```

Run `alembic upgrade head` against that database once before starting the API container. `/health` is configured as the container health check. The image has not been published to a registry by this project.

## 6. Kubernetes

`k8s/` contains a ConfigMap, a placeholder-only Secret, a one-off migration Job, a two-replica Deployment, and a ClusterIP Service. Deployment health probes call the existing `/health` endpoint. The Deployment uses a rolling update with zero unavailable replicas and one surge replica, resource requests/limits, and revision history.

Build and load the image into a local cluster, replace Secret placeholders locally, and apply the migration Job before the Deployment. The detailed sequence is in [k8s/README.md](k8s/README.md). Demonstrate an update and rollback with:

```bash
kubectl set image deployment/herdoc-backend api=herdoc-backend:v2
kubectl rollout status deployment/herdoc-backend
kubectl rollout history deployment/herdoc-backend
kubectl rollout undo deployment/herdoc-backend
kubectl rollout status deployment/herdoc-backend
```

Manifests do not provision MySQL, an ingress controller, TLS, or a registry. Supply a database endpoint and container image appropriate to the cluster. A successful runtime rollout/rollback is not claimed unless performed on an actual cluster.

## 7. Monitoring

The backend exposes `/metrics` using the Prometheus Python client. It records request counts, request errors (4xx and 5xx), latency histograms, in-progress requests, and process uptime. Prometheus adds the `up` scrape-health series for availability. Metrics use route templates instead of raw request paths to keep label cardinality bounded.

`monitoring/prometheus/prometheus.yml` scrapes `host.docker.internal:8000`; `monitoring/docker-compose.yml` runs Prometheus and Grafana locally. Grafana provisioning installs the Prometheus datasource and the HERDOC overview dashboard with availability, p50/p95 latency, error rate, request rate, and process uptime panels.

Start the HERDOC backend separately with a reachable database, then start monitoring:

```powershell
$env:GRAFANA_ADMIN_PASSWORD = '<temporary-local-dashboard-password>'
docker compose -f monitoring/docker-compose.yml up -d
```

Open Prometheus at `http://localhost:9090` and Grafana at `http://localhost:3001` (username `admin`, password set in the environment). The backend metrics endpoint is `http://localhost:8000/metrics`. `host.docker.internal` works on Docker Desktop and is mapped to the host gateway in Compose for Linux Docker engines. For Kubernetes scraping, change the Prometheus target to the service DNS name, for example `herdoc-backend.default.svc.cluster.local:8000`, and run Prometheus inside a network that can reach the service.

## 8. Logging

The HTTP middleware writes one operational key/value log line per request with method, route template, status code, and duration; server errors are logged at error level. Existing application services also use Python logging for security and operational events. Do not log request bodies, authorization headers, tokens, or secret environment values.

- Docker: `docker logs <container-name>`
- Kubernetes: `kubectl logs deployment/herdoc-backend --all-pods=true`
- systemd: `sudo journalctl -u herdoc-api -f`

## 9. Challenges

- The initial GitHub Actions run used a fresh SQLite database without running schema migrations, causing missing `users` and `facilities` tables.
- Running the migration locally exposed a second issue: the initial Alembic revision emitted `DEFAULT now()`, which SQLite rejected. The migration now uses portable `CURRENT_TIMESTAMP` defaults so the requested SQLite CI migration can create the schema.
- Real Ansible, Docker, and Kubernetes execution depends on external Linux/daemon/cluster resources and credentials. Configuration files alone are not deployment evidence.

## 10. Lessons learned

- CI databases need a reproducible schema setup before database-backed tests.
- Validate migrations against the same database engine and URL used by CI.
- Keep runtime secrets outside source control and inject them at deploy time.
- Readiness checks and metrics help operators distinguish an unavailable service from a healthy one; a deployment manifest does not prove a rollout happened.

## 11. Commands

Backend CI sequence from `backend/` (PowerShell):

```powershell
$env:PYTHONPATH = '.'
$env:DATABASE_URL = 'sqlite:///./test.db'
$env:JWT_SECRET = 'test-jwt-secret-key-for-ci'
$env:WEB_ORIGIN = 'http://localhost:3000'
alembic upgrade head
pytest
```

Build/run Docker with variables as shown in Section 5. Deploy, check rollout, and rollback with the commands in Section 6. Check metrics at `http://localhost:8000/metrics`, then start Prometheus/Grafana with Section 7. Run Ansible syntax check and deployment with Section 4.

## 12. Evidence checklist

Capture real screenshots/output after running the relevant commands:

1. GitHub Actions run showing the migration and pytest steps succeeding.
2. Ansible syntax-check output and, if available, actual play recap from a Linux VM.
3. Docker image build output and a running container health result.
4. Kubernetes Deployment/Service, `rollout status`, `rollout history`, update, and rollback output from a real cluster.
5. `http://localhost:8000/metrics` output showing HERDOC metrics after requests.
6. Prometheus target page showing `herdoc-backend` UP.
7. Grafana HERDOC API Overview dashboard populated with real scrape/request data.

Do not present configuration screenshots as proof of runtime deployments. No screenshots or runtime evidence are included in this repository.

## 13. Optional bonus challenge

No external challenge participation is claimed or included. Pursue a bonus challenge only if HERDOC is actually entered and participation can be evidenced legitimately.
