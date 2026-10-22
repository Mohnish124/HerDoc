FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system herdoc && adduser --system --ingroup herdoc --home /app herdoc

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=herdoc:herdoc app ./app
COPY --chown=herdoc:herdoc alembic ./alembic
COPY --chown=herdoc:herdoc alembic.ini ./alembic.ini

USER herdoc
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)"

# Single-instance hosts (e.g. Render) set RUN_MIGRATIONS_ON_START=1 to migrate before serving;
# the container exits if the migration fails. Kubernetes leaves it unset and uses k8s/migration-job.yaml.
CMD ["/bin/sh", "-c", "if [ \"${RUN_MIGRATIONS_ON_START:-0}\" = \"1\" ]; then alembic upgrade head || exit 1; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
