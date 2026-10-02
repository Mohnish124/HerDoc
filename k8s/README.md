# HERDOC Kubernetes deployment

These manifests deploy the real backend image. They do not include a database; configure a reachable MySQL service in the Kubernetes Secret. `k8s/secret.yaml` contains conspicuous placeholders only. Create `k8s/secret.local.yaml` from it, replace the placeholders locally (that filename is gitignored), and apply the local file; never commit actual credentials.

Build the backend image at the repository root and load it into your local cluster (for Minikube, use `minikube image load herdoc-backend:latest`). Before the first deployment, create/update the ConfigMap and Secret, then run the one-off migration Job. Apply the Deployment only after migration completes:

```bash
docker build -t herdoc-backend:latest -f backend/Dockerfile backend
kubectl apply -f k8s/configmap.yaml
```

In PowerShell, make and edit the ignored local Secret file before applying:

```powershell
Copy-Item k8s/secret.yaml k8s/secret.local.yaml
# Edit k8s/secret.local.yaml with the database URL and a random JWT secret.
kubectl apply -f k8s/secret.local.yaml
```

Then continue with the migration and application resources:

```bash
kubectl apply -f k8s/migration-job.yaml
kubectl wait --for=condition=complete job/herdoc-db-migrate --timeout=180s
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/herdoc-backend
```

The Deployment uses two replicas and the `RollingUpdate` strategy. To demonstrate an update, build/load a new image tag and apply it, for example:

```bash
kubectl set image deployment/herdoc-backend api=herdoc-backend:v2
kubectl rollout status deployment/herdoc-backend
kubectl rollout history deployment/herdoc-backend
kubectl rollout undo deployment/herdoc-backend
kubectl rollout status deployment/herdoc-backend
```

For local access, use `kubectl port-forward service/herdoc-backend 8000:8000`; the health and metrics endpoints are then at `http://localhost:8000/health` and `http://localhost:8000/metrics`. Runtime rollout and rollback are not claimed unless actually run against a cluster. The API startup checks database connectivity, so pods remain unready if the configured MySQL endpoint is unavailable.
