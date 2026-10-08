"""Real Demucs v4 (Hybrid Transformer) adapter. No training, no mocks.

Uses the inference-only `demucs-infer` package (maintained fork lineage of
facebookresearch/demucs, PyTorch 2.x compatible). Checkpoints download on
first `warmup()` / `separate()` from the official Meta file host into the
torch hub cache -- they are NOT bundled in this repo or the docker image.

License note (surfaced in /api/v1/models and Settings): Demucs code is MIT;
the official pretrained weights are stated by the author to be "provided only
for scientific purposes" with no commercial grant. Suitable for personal /
prototype use; resolve rights before any commercial deployment.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import torch

from audioapp.models.base import SeparatorAdapter

log = logging.getLogger(__name__)

_lock = threading.Lock()  # one model in memory; serialize inference on CPU


def _import_demucs():
    try:
        import demucs_infer.pretrained as pretrained
        import demucs_infer.apply as apply_mod
        return pretrained, apply_mod, "demucs-infer"
    except ImportError:
        pass
    try:
        import demucs.pretrained as pretrained
        import demucs.apply as apply_mod
        return pretrained, apply_mod, "demucs"
    except ImportError:
        raise RuntimeError(
            "No Demucs package installed. Install with: pip install demucs-infer "
            "(and CPU torch first, see README)."
        )


class DemucsAdapter(SeparatorAdapter):
    name = "demucs"

    def __init__(self, model_id: str = "htdemucs", device: str = "auto"):
        self.model_id = model_id
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self._model = None
        self._stems: list[str] | None = None

    @property
    def stems(self) -> list[str]:
        if self._stems is None:
            self.warmup()
        assert self._stems is not None
        return self._stems

    def warmup(self) -> None:
        if self._model is not None:
            return
        pretrained, _, pkg = _import_demucs()
        log.info("loading Demucs model '%s' via %s on %s", self.model_id, pkg, self.device)
        with _lock:
            model = pretrained.get_model(self.model_id)
            model.to(self.device)
            model.eval()
            self._model = model
            self._stems = list(model.sources)
        log.info("Demucs model '%s' ready, stems=%s", self.model_id, self._stems)

    def separate(
        self,
        input_wav: Path,
        out_dir: Path,
        stems: list[str] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_stage: Callable[[str], None] | None = None,
    ) -> dict[str, Path]:
        self.warmup()
        _, apply_mod, _ = _import_demucs()
        assert self._model is not None and self._stems is not None

        def cancelled() -> bool:
            return bool(is_cancelled and is_cancelled())

        if cancelled():
            raise _Cancelled()

        import soundfile as sf

        if on_stage:
            on_stage("Loading audio into the AI model…")
        # NOTE: torchaudio.load/save now require the optional torchcodec
        # package, so WAV I/O goes through soundfile (a demucs-infer dep).
        data, sr = sf.read(str(input_wav), dtype="float32", always_2d=True)  # [T, C]
        wav = torch.from_numpy(data.T).contiguous()  # [C, T]
        if sr != self.sample_rate:
            import torchaudio.functional as F  # pure-torch, no torchcodec needed
            wav = F.resample(wav, sr, self.sample_rate)
        if wav.shape[0] == 1:
            wav = wav.repeat(2, 1)
        elif wav.shape[0] > 2:
            wav = wav[:2]

        if on_stage:
            on_stage("Separating vocals and instruments…")
        with _lock, torch.no_grad():
            out = apply_mod.apply_model(
                self._model, wav[None].to(self.device), device=self.device, progress=False
            )[0].cpu()  # [S, C, T]

        if cancelled():
            raise _Cancelled()

        if on_stage:
            on_stage("Saving separated stems…")
        out_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Path] = {}
        want = stems or self._stems
        for i, stem in enumerate(self._stems):
            if stem not in want:
                continue
            if cancelled():
                raise _Cancelled()
            dst = out_dir / f"{stem}.wav"
            sf.write(str(dst), out[i].numpy().T, self.sample_rate, subtype="PCM_16")
            result[stem] = dst
        return result


class _Cancelled(Exception):
    pass
