"""Job metadata store. Interface-first: SQLite for the MVP, swappable for
PostgreSQL later. NEVER stores audio bytes -- only paths + metadata."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

TERMINAL_STATES = {"completed", "failed", "cancelled", "expired"}
ACTIVE_STATES = {"uploaded", "validating", "queued", "processing", "encoding"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class JobStore(ABC):
    @abstractmethod
    def create_upload(self, *, filename: str, size_bytes: int, meta: dict,
                      path: str, expires_at: datetime) -> dict: ...
    @abstractmethod
    def get_upload(self, upload_id: str) -> dict | None: ...
    @abstractmethod
    def delete_upload(self, upload_id: str) -> None: ...
    @abstractmethod
    def create_job(self, *, upload_id: str, mode: str, model: str | None,
                   stems: list[str] | None, export: dict, expires_at: datetime) -> dict: ...
    @abstractmethod
    def get_job(self, job_id: str) -> dict | None: ...
    @abstractmethod
    def list_jobs(self, limit: int = 50) -> list[dict]: ...
    @abstractmethod
    def update_job(self, job_id: str, **fields) -> dict | None: ...
    @abstractmethod
    def add_output(self, job_id: str, *, output_id: str, kind: str, stem: str,
                   label: str, fmt: str, path: str, size_bytes: int,
                   duration_s: float, sample_rate: int, channels: int,
                   bitrate_kbps: int | None) -> dict: ...
    @abstractmethod
    def get_outputs(self, job_id: str) -> list[dict]: ...
    @abstractmethod
    def get_output(self, job_id: str, output_id: str) -> dict | None: ...
    @abstractmethod
    def delete_job(self, job_id: str) -> None: ...
    @abstractmethod
    def due_for_expiry(self, now: datetime) -> list[dict]: ...
    @abstractmethod
    def expired_uploads(self, now: datetime) -> list[dict]: ...


class SQLiteJobStore(JobStore):
    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL, meta_json TEXT NOT NULL,
                    path TEXT NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, upload_id TEXT NOT NULL,
                    mode TEXT NOT NULL, model TEXT, stems_json TEXT,
                    export_json TEXT NOT NULL, status TEXT NOT NULL,
                    stage_detail TEXT, progress_json TEXT,
                    error_json TEXT, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, output_id TEXT NOT NULL,
                    kind TEXT NOT NULL, stem TEXT NOT NULL, label TEXT NOT NULL,
                    format TEXT NOT NULL, path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL, duration_s REAL NOT NULL,
                    sample_rate INTEGER NOT NULL, channels INTEGER NOT NULL,
                    bitrate_kbps INTEGER,
                    UNIQUE(job_id, output_id)
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_outputs_job ON outputs(job_id);
                """
            )

    # -- uploads ---------------------------------------------------------
    def create_upload(self, *, filename, size_bytes, meta, path, expires_at) -> dict:
        uid = new_id("upl")
        row = {
            "id": uid, "filename": filename, "size_bytes": size_bytes,
            "meta": meta, "path": path,
            "created_at": _iso(utcnow()), "expires_at": _iso(expires_at),
        }
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO uploads VALUES (?,?,?,?,?,?,?)",
                (uid, filename, size_bytes, json.dumps(meta), path,
                 row["created_at"], row["expires_at"]),
            )
        return row

    def get_upload(self, upload_id: str) -> dict | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone()
        return self._row_to_upload(r) if r else None

    def delete_upload(self, upload_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM uploads WHERE id=?", (upload_id,))

    # -- jobs ------------------------------------------------------------
    def create_job(self, *, upload_id, mode, model, stems, export, expires_at) -> dict:
        jid = new_id("job")
        now = _iso(utcnow())
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (jid, upload_id, mode, model, json.dumps(stems or []),
                 json.dumps(export), "uploaded", "", json.dumps({"measurable": False}),
                 None, now, now, _iso(expires_at)),
            )
        return self.get_job(jid)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row_to_job(r) if r else None

    def list_jobs(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def update_job(self, job_id: str, **fields) -> dict | None:
        allowed = {"status", "stage_detail", "progress_json", "error_json"}
        sets = {k: (json.dumps(v) if k in ("progress_json", "error_json") else v)
                for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_job(job_id)
        sets["updated_at"] = _iso(utcnow())
        cols = ", ".join(f"{k}=?" for k in sets)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE jobs SET {cols} WHERE id=?",
                               (*sets.values(), job_id))
        return self.get_job(job_id)

    def add_output(self, job_id, *, output_id, kind, stem, label, fmt, path,
                   size_bytes, duration_s, sample_rate, channels, bitrate_kbps) -> dict:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO outputs
                   (job_id, output_id, kind, stem, label, format, path, size_bytes,
                    duration_s, sample_rate, channels, bitrate_kbps)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, output_id, kind, stem, label, fmt, path, size_bytes,
                 duration_s, sample_rate, channels, bitrate_kbps),
            )
        row = self.get_output(job_id, output_id)
        assert row is not None
        return row

    def get_outputs(self, job_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM outputs WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_output(self, job_id: str, output_id: str) -> dict | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM outputs WHERE job_id=? AND output_id=?", (job_id, output_id)
            ).fetchone()
        return dict(r) if r else None

    def delete_job(self, job_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM outputs WHERE job_id=?", (job_id,))
            self._conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    def due_for_expiry(self, now: datetime) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE expires_at <= ? AND status != 'expired'",
                (_iso(now),),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def expired_uploads(self, now: datetime) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM uploads WHERE expires_at <= ?", (_iso(now),)
            ).fetchall()
        return [self._row_to_upload(r) for r in rows]

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _row_to_upload(r: sqlite3.Row) -> dict:
        d = dict(r)
        d["meta"] = json.loads(d.pop("meta_json"))
        return d

    @staticmethod
    def _row_to_job(r: sqlite3.Row) -> dict:
        d = dict(r)
        d["stems"] = json.loads(d.pop("stems_json") or "[]")
        d["export"] = json.loads(d.pop("export_json") or "{}")
        d["progress"] = json.loads(d.pop("progress_json") or "{}")
        err = d.pop("error_json")
        d["error"] = json.loads(err) if err else None
        return d
