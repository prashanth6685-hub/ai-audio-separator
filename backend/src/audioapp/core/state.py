"""Shared application state (created once in main.py lifespan)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from audioapp.config import Settings
from audioapp.core.queueing import TaskQueue
from audioapp.core.store import JobStore
from audioapp.models.base import SeparatorAdapter


@dataclass
class AppState:
    settings: Settings
    store: JobStore
    queue: TaskQueue
    jobs_dir: Path
    uploads_dir: Path
    get_adapter: Callable[[str], SeparatorAdapter]
