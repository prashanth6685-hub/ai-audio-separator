"""Retention: expire old jobs and orphan uploads, delete their files.

Runs as a daemon thread started by the app lifespan. Deletion is the only
destructive op here and it only touches this app's DATA_DIR.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path

from audioapp.core.store import JobStore, utcnow

log = logging.getLogger(__name__)


def _rmtree(path: Path) -> None:
    try:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    except OSError as e:
        log.warning("retention: could not delete %s: %s", path, e)


def sweep_once(store: JobStore, jobs_dir: Path, uploads_dir: Path) -> dict:
    now = utcnow()
    expired_jobs = 0
    expired_uploads = 0
    for job in store.due_for_expiry(now):
        jid = job["id"]
        store.update_job(jid, status="expired", stage_detail="Results expired and were deleted.")
        for out in store.get_outputs(jid):
            _rmtree(Path(out["path"]))
        _rmtree(jobs_dir / jid)
        store.delete_job(jid)
        expired_jobs += 1
    for upl in store.expired_uploads(now):
        _rmtree(Path(upl["path"]))
        store.delete_upload(upl["id"])
        expired_uploads += 1
    if expired_jobs or expired_uploads:
        log.info("retention sweep: expired %d jobs, %d uploads", expired_jobs, expired_uploads)
    return {"expired_jobs": expired_jobs, "expired_uploads": expired_uploads}


def start_sweeper(store: JobStore, jobs_dir: Path, uploads_dir: Path,
                  interval_s: int) -> threading.Event:
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval_s):
            try:
                sweep_once(store, jobs_dir, uploads_dir)
            except Exception:  # never kill the sweeper
                log.exception("retention sweep failed")

    t = threading.Thread(target=loop, name="retention-sweeper", daemon=True)
    t.start()
    return stop
