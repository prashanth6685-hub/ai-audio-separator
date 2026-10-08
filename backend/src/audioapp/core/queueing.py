"""Task queue abstraction.

MVP: LocalThreadQueue (ThreadPoolExecutor with a concurrency limit).
The interface mirrors what a Redis/RQ/Celery backend would expose, so the
pipeline code does not change when we swap implementations for scale.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class JobHandle:
    job_id: str
    future: Future
    cancel_event: threading.Event = field(default_factory=threading.Event)


class TaskQueue(ABC):
    @abstractmethod
    def submit(self, job_id: str, fn) -> JobHandle: ...
    @abstractmethod
    def cancel(self, job_id: str) -> bool: ...
    @abstractmethod
    def stats(self) -> dict: ...


class LocalThreadQueue(TaskQueue):
    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers), thread_name_prefix="separator"
        )
        self._handles: dict[str, JobHandle] = {}
        self._lock = threading.Lock()

    def submit(self, job_id: str, fn) -> JobHandle:
        handle = JobHandle(job_id=job_id, future=None)  # type: ignore[arg-type]
        handle.future = self._executor.submit(self._guarded, handle, fn)
        with self._lock:
            self._handles[job_id] = handle
        return handle

    @staticmethod
    def _guarded(handle: JobHandle, fn):
        try:
            return fn(handle.cancel_event)
        finally:
            pass

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            handle = self._handles.get(job_id)
        if handle is None:
            return False
        handle.cancel_event.set()
        # If it hasn't started, drop it from the pool too.
        return handle.future.cancel() or True

    def get_handle(self, job_id: str) -> JobHandle | None:
        with self._lock:
            return self._handles.get(job_id)

    def stats(self) -> dict:
        with self._lock:
            handles = list(self._handles.values())
        active = sum(1 for h in handles if h.future.running())
        queued = sum(1 for h in handles if not h.future.done() and not h.future.running())
        return {
            "queued": queued,
            "active": active,
            "max_workers": self._executor._max_workers,
        }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
