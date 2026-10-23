# HERDOC — Deployment Overview

## 1. Project Overview

HERDOC is an offline-first maternal risk triage application built with a FastAPI backend, SQLAlchemy, Alembic migrations, a React/Vite web portal, and an Expo mobile client.

The web portal and backend have been deployed on Render, with the backend configured to connect to a MySQL database. The project also includes GitHub Actions CI, Docker, Ansible, Kubernetes manifests, Prometheus, and Grafana for DevOps implementation and monitoring.

### Live Deployment

- **Web Portal:** https://herdoc-web-demo.onrender.com
- **Backend API:** https://herdoc.onrender.com
- **Backend Health Check:** https://herdoc.onrender.com/health
- **Backend Metrics:** https://herdoc.onrender.com/metrics
- **GitHub Repository:** https://github.com/Mohnish124/HerDoc

> Note: The health and metrics endpoints may have different access or availability requirements depending on the production configuration. Verify them against the live service.

## 2. System Architecture

```mermaid
flowchart TD
    User[Healthcare Worker / Doctor / Admin]
    Web[React + Vite Web Portal]
    Mobile[Expo Mobile Application]
    API[FastAPI Backend on Render]
    DB[(MySQL Database)]
    Git[GitHub Repository]
    CI[GitHub Actions CI]
    Monitoring[Prometheus + Grafana]
    Docker[Docker Image]
    K8s[Kubernetes Deployment]
    Ansible[Ansible Configuration Management]

    User --> Web
    User --> Mobile
    Web -->|HTTPS API| API
    Mobile -->|HTTPS API and Sync| API
    API --> DB
    Git --> CI
    Git -. Deployment workflow .-> API
    API -->|Metrics endpoint| Monitoring
    API -. Containerization .-> Docker
    Docker -. Manual deployment option .-> K8s
    Ansible -. VM configuration .-> API
```

The production database is MySQL. SQLite is used only for isolated CI tests and local demo-data testing. Production database credentials and application secrets must be configured through protected environment variables rather than committed to Git.

## 3. Render Deployment

HERDOC's web portal and backend API are deployed as separate services on Render.

### Deployment workflow

1. Make changes in the local project.
2. Run the relevant tests and build checks.
3. Review the Git changes and ensure secrets and sensitive data are excluded.
4. Commit and push the approved changes to the configured GitHub branch.
5. Check the Render service build and deployment logs.
6. Open the live website and verify the updated functionality.

### Production verification checklist

- [ ] The web portal loads over HTTPS.
- [ ] The backend health endpoint responds as expected.
- [ ] Login and authentication work.
- [ ] Doctor, administrator, and worker features work according to their permissions.
- [ ] API requests reach the backend.
- [ ] Database-backed features work correctly.
- [ ] Emergency/SOS behavior is verified using a safe test procedure.
- [ ] No secrets or patient information appear in logs or source control.

A successful Git push or local test does not by itself prove that the latest version is live. Confirm the deployment in Render before reporting it as complete.

Render free services may sleep when idle, so the first request after inactivity can take longer.

## 4. CI/CD Pipeline

The GitHub Actions workflow is located at:

`.github/workflows/herdoc-ci.yml`

The workflow validates the backend when changes are pushed or pull requests target the configured branches.

### Pipeline stages

1. Check out the repository.
2. Set up Python 3.11.
3. Install backend dependencies.
4. Run Alembic migrations against the CI-only SQLite database.
5. Execute the backend test suite using pytest.

```mermaid
flowchart TD
    A[GitHub Push or Pull Request] --> B[Checkout Repository]
    B --> C[Set Up Python 3.11]
    C --> D[Install Dependencies]
    D --> E[Run Alembic Migrations]
    E --> F[Run pytest]
    F --> G[Review CI Results]
```

The workflow currently validates the backend. It does not build or publish a Docker image or deploy to Kubernetes. Render deployment should be verified through the configured Render workflow and deployment logs.

## 5. Docker

The backend Dockerfile is located at `backend/Dockerfile`.

It builds the FastAPI backend using Python 3.11, installs the required dependencies, copies the application and migration files, and runs the API using a non-root user.

Build the image from the repository root:

```powershell
docker build -t herdoc-backend:latest -f backend/Dockerfile backend
```

Run the container with a reachable MySQL database and appropriate local environment variables:

```powershell
docker run --rm -p 8000:8000 `
  -e DATABASE_URL='mysql+pymysql://USER:PASSWORD@HOST:3306/herdoc?charset=utf8mb4' `
  -e JWT_SECRET='<random-32+-character-secret>' `
  -e WEB_ORIGIN='http://localhost:3000' `
  herdoc-backend:latest
```

Run the required Alembic migrations against the intended database before starting the application. Never paste real production credentials into documentation or source control.

The Docker workflow is a separate deployment option; it does not replace the existing Render deployment.

## 6. Kubernetes

The `k8s/` directory contains Kubernetes configuration for the backend, including:

- ConfigMap
- Placeholder-only Secret
- Database migration Job
- Two-replica Deployment
- ClusterIP Service
- Health probes and resource settings

These manifests provide a deployment path for a suitable Kubernetes cluster. They do not automatically provision MySQL, a container registry, TLS, or an ingress controller.

Before deploying, configure valid secrets, a reachable database, and an appropriate image. Apply the migration Job before rolling out the backend Deployment.

Example rollout commands:

```bash
kubectl rollout status deployment/herdoc-backend
kubectl rollout history deployment/herdoc-backend
kubectl rollout undo deployment/herdoc-backend
```

These commands should be reported as deployment evidence only after they have been run against a real cluster.

## 7. Ansible Configuration Management

The `ansible/` directory contains an example inventory and playbook for configuring a Linux VM.

The playbook is designed to install runtime dependencies, create a dedicated service account, configure the application environment, run migrations, and manage the API through systemd.

Configure the local inventory and required environment variables on the Ansible control node before running it.

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --ask-become-pass
```

The example inventory is not a real production host configuration. A successful Ansible deployment should only be claimed after execution and verification on the target VM.

## 8. Monitoring with Prometheus and Grafana

The FastAPI backend exposes a `/metrics` endpoint using the Prometheus Python client.

The metrics implementation records operational information such as:

- Request counts
- HTTP request errors
- Request latency histograms
- Requests currently in progress
- Process uptime

The `monitoring/` directory contains Prometheus configuration, Docker Compose setup, and Grafana provisioning for local monitoring.

Start the monitoring services locally:

```powershell
$env:GRAFANA_ADMIN_PASSWORD = '<temporary-local-dashboard-password>'
docker compose -f monitoring/docker-compose.yml up -d
```

Typical local endpoints:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001
- Local backend metrics: http://localhost:8000/metrics

These local monitoring endpoints are separate from the deployed Render services. To monitor Render, configure an appropriate reachable scrape target and network access; do not assume the local Docker configuration can scrape a remote service without adjustment.

## 9. Logging

The backend includes request logging for operational visibility. Request logs include information such as the HTTP method, route template, status code, and request duration.

Do not log request bodies, authorization headers, tokens, patient information, or secret environment values.

Useful commands for the different deployment environments include:

```bash
docker logs <container-name>
kubectl logs deployment/herdoc-backend --all-pods=true
sudo journalctl -u herdoc-api -f
```

For Render, inspect the relevant service's logs in the Render dashboard.

## 10. Demo Data and Production Safety

HERDOC includes a demo-data seeding utility intended for isolated local SQLite testing and demonstrations.

**Do not run the demo seeding utility against the production Render/Aiven database.**

Demo accounts and synthetic patient records must be provisioned through a separately reviewed and explicitly authorized process. Do not use real patient data in screenshots, test fixtures, or public demonstrations.

## 11. Challenges and Lessons Learned

### Challenges

- The CI workflow initially encountered database schema issues because migrations had not been applied before database-backed tests.
- SQLite exposed a migration compatibility issue involving timestamp defaults, which required a portable migration expression.
- Docker, Ansible, and Kubernetes workflows require the appropriate local services, credentials, and infrastructure.
- A successful local build does not prove that the production service has deployed the same version.

### Lessons learned

- Run database migrations before database-backed tests.
- Validate migrations against the database engine used by the relevant environment.
- Keep secrets outside source control.
- Use health checks, logs, and metrics to diagnose runtime issues.
- Verify deployments in the target environment instead of treating configuration files as proof of execution.
- Keep synthetic demo data separate from production patient records.

## 12. Evidence Checklist

Capture genuine screenshots or command output for the following items when demonstrating the project:

1. Render web service showing the deployed frontend.
2. Render backend service and deployment logs.
3. Live website showing successful login and key workflows.
4. GitHub Actions workflow with migration and test steps completed.
5. Docker image build and container health output.
6. Ansible syntax check and play recap, if executed.
7. Kubernetes Deployment and Service, rollout status, and rollback output, if executed.
8. Prometheus metrics and target status.
9. Grafana dashboard populated with real monitoring data.

Do not present a configuration file or an unexecuted command as evidence that a deployment or monitoring setup has run successfully.

## 13. Optional Bonus Challenge

No external challenge participation is claimed in this documentation. Include such a claim only if HERDOC is actually entered and participation can be verified.
