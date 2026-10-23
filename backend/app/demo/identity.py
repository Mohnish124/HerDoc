"""Stable identities of the synthetic demo records (no other imports, so auth code can use it safely).

The demo seed gives every record an id derived from this namespace and its dataset key, so demo accounts can
be recognised explicitly by id — never by phone number alone, which a real user could legitimately have.
"""
import uuid

DEMO_ID_NAMESPACE = uuid.UUID("6f1c2a3e-9b4d-4e0f-8a7c-1d2e3f405162")


def demo_id(key: str) -> uuid.UUID:
    """Stable id for a dataset record, so reruns find what an earlier run created."""
    return uuid.uuid5(DEMO_ID_NAMESPACE, f"herdoc-demo:{key}")


# The five demo workers in app/demo/demo_dataset.json (keys worker-1 .. worker-5).
DEMO_DATASET_WORKER_IDS = frozenset(demo_id(f"worker-{i}") for i in range(1, 6))
