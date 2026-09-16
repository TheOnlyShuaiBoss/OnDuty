"""运行态持久化: state/state.json + state/runs.jsonl + state/logs/(主方案 §6)。"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime


class StateStore:
    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, "state.json")
        os.makedirs(os.path.join(root, "logs"), exist_ok=True)
        os.makedirs(os.path.join(root, "ctl"), exist_ok=True)

    def load(self) -> dict:
        if not os.path.isfile(self.path):
            return {"jobs": {}}
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def job(self, name: str) -> dict:
        return self.load().get("jobs", {}).get(name, {})

    def update_job(self, name: str, **fields) -> dict:
        data = self.load()
        merged = {**data.get("jobs", {}).get(name, {}), **fields}
        data.setdefault("jobs", {})[name] = merged
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.save(data)
        return merged

    def append_run(self, record: dict) -> None:
        with open(os.path.join(self.root, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def new_log_path(self, job_name: str, started: datetime) -> str:
        d = os.path.join(self.root, "logs", job_name)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, started.strftime("%Y%m%d-%H%M%S") + ".log")
