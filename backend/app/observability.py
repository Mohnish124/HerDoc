"""Prometheus metrics for the HerDoc API."""

import time

from prometheus_client import Counter, Gauge, Histogram

PROCESS_START_TIME = time.monotonic()

HTTP_REQUESTS = Counter(
    "herdoc_http_requests_total",
    "HTTP requests served by HerDoc",
    ("method", "path", "status_code"),
)
HTTP_ERRORS = Counter(
    "herdoc_http_errors_total",
    "HTTP requests that returned a 4xx or 5xx response",
    ("method", "path", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "herdoc_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "herdoc_http_requests_in_progress",
    "HTTP requests currently being processed",
)
PROCESS_UPTIME = Gauge(
    "herdoc_process_uptime_seconds",
    "Time in seconds since this HerDoc process started",
)
