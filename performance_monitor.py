import math
import threading
import time
from collections import deque
from typing import Iterable


_lock = threading.Lock()
_samples: dict[str, deque[float]] = {}
_errors: dict[str, int] = {}


def record_latency(name: str, elapsed_seconds: float) -> None:
    elapsed_ms = max(0.0, elapsed_seconds * 1000.0)
    with _lock:
        samples = _samples.setdefault(name, deque(maxlen=2000))
        samples.append(elapsed_ms)


def record_error(name: str) -> None:
    with _lock:
        _errors[name] = _errors.get(name, 0) + 1


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 2)


def snapshot() -> dict[str, object]:
    with _lock:
        metrics: dict[str, object] = {}
        for name, samples in _samples.items():
            values = tuple(samples)
            metrics[name] = {
                "count": len(values),
                "avg_ms": round(sum(values) / len(values), 2) if values else 0.0,
                "p50_ms": _percentile(values, 0.50),
                "p95_ms": _percentile(values, 0.95),
                "p99_ms": _percentile(values, 0.99),
                "max_ms": round(max(values), 2) if values else 0.0,
            }
        return {"metrics": metrics, "errors": dict(_errors)}

