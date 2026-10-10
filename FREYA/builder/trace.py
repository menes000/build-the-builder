"""Run trace: start/end, every model call (model + purpose), what was created on Freya, every test. Plain text + JSONL."""
from __future__ import annotations

import json
import time
from pathlib import Path


class Trace:
    def __init__(self, dir_path: str = "traces", label: str = "run"):
        self.dir = Path(dir_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.txt = self.dir / f"{stamp}-{label}.txt"
        self.jsonl = self.dir / f"{stamp}-{label}.jsonl"
        self.t0 = time.time()
        self._write("start", {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "label": label})

    def _write(self, kind: str, data: dict):
        rec = {"t": round(time.time() - self.t0, 1), "kind": kind, **data}
        with self.jsonl.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        line = f"[{rec['t']:7.1f}s] {kind}: " + " ".join(f"{k}={v}" for k, v in data.items() if k != "at")
        with self.txt.open("a") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def note(self, text: str):
        self._write("note", {"text": text})

    def model_call(self, model: str, purpose: str, seconds: float, cost_usd=None, tokens=None):
        self._write("model_call", {"model": model, "purpose": purpose, "seconds": round(seconds, 1), "cost_usd": cost_usd, "tokens": tokens})

    def created(self, what: str, **ids):
        self._write("created_on_freya", {"what": what, **ids})

    def test(self, name: str, passed: int, total: int, seconds: float, failed: list[str], simulation_id: str = ""):
        self._write("test", {"name": name, "passed": passed, "total": total, "seconds": round(seconds), "failed": failed, "simulation_id": simulation_id})

    def end(self, **data):
        self._write("end", {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "total_seconds": round(time.time() - self.t0), **data})
