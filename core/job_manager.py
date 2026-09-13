"""Persistent, pausable local task manager for the workbench."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable

from core.workspace import WorkspaceStore


@dataclass
class JobRecord:
    job_id: str
    module: str
    title: str
    skill_ids: list[str] = field(default_factory=list)
    status: str = "queued"
    progress: int = 0
    message: str = "等待开始"
    output_file: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class JobControl:
    def __init__(self) -> None:
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()

    def checkpoint(self) -> bool:
        while self.pause_event.is_set() and not self.cancel_event.is_set():
            time.sleep(0.2)
        return not self.cancel_event.is_set()


class JobManager:
    ACTIVE_STATUSES = {"queued", "running", "paused", "cancelling"}
    _lock = threading.RLock()
    _controls: dict[str, JobControl] = {}
    _threads: dict[str, threading.Thread] = {}

    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store
        self.path = store.root / "任务记录" / "jobs.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._recover_stale_jobs()

    def _load(self) -> list[JobRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [JobRecord(**item) for item in data]
        except (OSError, ValueError, TypeError):
            return []

    def _recover_stale_jobs(self) -> None:
        """Mark in-memory jobs lost during an app restart as interrupted."""
        with self._lock:
            records = self._load()
            changed = False
            for record in records:
                if record.status in self.ACTIVE_STATUSES and record.job_id not in self._threads:
                    record.status = "interrupted"
                    record.message = "应用重启后任务未恢复，请重新启动"
                    record.updated_at = datetime.now().isoformat(timespec="seconds")
                    changed = True
            if changed:
                self._save(records)

    def active_job(self, module: str) -> JobRecord | None:
        """Return the current active job for a module, if one exists."""
        return next((job for job in self._load() if job.module == module and job.status in self.ACTIVE_STATUSES), None)

    def _save(self, records: list[JobRecord]) -> None:
        payload = json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)
    def list_jobs(self) -> list[JobRecord]:
        return list(reversed(self._load()))

    def get(self, job_id: str) -> JobRecord | None:
        return next((job for job in self._load() if job.job_id == job_id), None)

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            records = self._load()
            for record in records:
                if record.job_id == job_id:
                    for key, value in changes.items():
                        setattr(record, key, value)
                    record.updated_at = datetime.now().isoformat(timespec="seconds")
                    break
            self._save(records)

    def update_progress(self, job_id: str, progress: int, message: str) -> None:
        """Publish progress through the public task-manager API."""
        self._update(job_id, progress=max(0, min(100, progress)), message=message)
    def start(
        self,
        module: str,
        title: str,
        skill_ids: list[str],
        processor: Callable[[JobControl, JobRecord], str],
    ) -> JobRecord:
        job = JobRecord(job_id=self.store.new_id(), module=module, title=title, skill_ids=skill_ids)
        with self._lock:
            records = self._load()
            records.append(job)
            self._save(records)
        control = JobControl()
        self._controls[job.job_id] = control

        def run() -> None:
            self._update(job.job_id, status="running", message="正在处理")
            try:
                output_file = processor(control, job)
                if control.cancel_event.is_set():
                    self._update(job.job_id, status="cancelled", progress=0, message="已终止")
                else:
                    self._update(job.job_id, status="completed", progress=100, message="已完成", output_file=output_file)
            except Exception as exc:
                self._update(job.job_id, status="failed", message=str(exc))

        thread = threading.Thread(target=run, name=f"job-{job.job_id}", daemon=True)
        self._threads[job.job_id] = thread
        thread.start()
        return job

    def pause(self, job_id: str) -> None:
        control = self._controls.get(job_id)
        if control:
            control.pause_event.set()
            self._update(job_id, status="paused", message="已暂停")

    def resume(self, job_id: str) -> None:
        control = self._controls.get(job_id)
        if control:
            control.pause_event.clear()
            self._update(job_id, status="running", message="继续处理")

    def cancel(self, job_id: str) -> None:
        control = self._controls.get(job_id)
        if control:
            control.cancel_event.set()
            control.pause_event.clear()
            self._update(job_id, status="cancelling", message="正在终止")



