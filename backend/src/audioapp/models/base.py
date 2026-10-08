"""Separator adapter interface.

Every source-separation model plugs in here. The pipeline only talks to this
ABC, so a new model (Open-Unmix, a commercially-licensed model, ...) can be
added without touching API/worker/encoding code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path


class SeparatorAdapter(ABC):
    """Real model adapter. `separate` must produce genuine separated audio."""

    name: str = "base"

    @property
    @abstractmethod
    def stems(self) -> list[str]:
        """Stem names this model genuinely outputs, e.g. ['drums','bass','other','vocals']."""
        ...

    @property
    def sample_rate(self) -> int:
        return 44100

    def warmup(self) -> None:
        """Download/cache the checkpoint. Called explicitly, never silently per job."""

    @abstractmethod
    def separate(
        self,
        input_wav: Path,
        out_dir: Path,
        stems: list[str] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_stage: Callable[[str], None] | None = None,
    ) -> dict[str, Path]:
        """Separate `input_wav` (PCM WAV at `sample_rate`) into stems.

        Returns {stem_name: wav_path}. Must write real model outputs.
        Should poll `is_cancelled` between chunks and abort promptly.
        `on_stage` receives human-readable stage messages (no fake %).
        """
        ...
