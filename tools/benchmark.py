"""Diagnostic in-process API timings on synthetic data; not a network benchmark."""

from pathlib import Path
import json
import math
import statistics
import tempfile
import time

from fastapi.testclient import TestClient
from workflow.api import create_app


def run():
    headers = {"Authorization": "Bearer demo-alice"}
    runs = []
    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(Path(directory) / "benchmark.sqlite3")) as client:
            ids = []
            for i in range(500):
                response = client.post("/tasks", json={"title": f"Benchmark task {i:04d}"}, headers=headers)
                if response.status_code != 201:
                    raise RuntimeError("benchmark setup failed")
                ids.append(response.json()["id"])
            for i in range(20):
                if client.get(f"/tasks/{ids[i]}", headers=headers).status_code != 200:
                    raise RuntimeError("benchmark warmup failed")
            for repetition in range(3):
                values = []
                for i in range(100):
                    started = time.perf_counter_ns()
                    response = client.get(f"/tasks/{ids[i]}", headers=headers)
                    elapsed = (time.perf_counter_ns() - started) / 1_000_000
                    if response.status_code != 200:
                        raise RuntimeError("benchmark request failed")
                    values.append(elapsed)
                ordered = sorted(values)
                runs.append({"repetition": repetition + 1, "requests": len(values),
                             "p50_ms": statistics.median(values),
                             "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1],
                             "min_ms": min(values), "max_ms": max(values)})
    return {"boundary": "TestClient in-process request including application and SQLite; no TCP",
            "dataset_tasks": 500, "warmup_requests": 20, "concurrency": 1,
            "clock": "perf_counter_ns", "units": "milliseconds", "runs": runs,
            "acceptance_threshold": None}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
