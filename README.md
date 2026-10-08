# AI Audio Separator, Karaoke Maker & Music Converter

Upload an audio file, separate it into **vocals / drums / bass / other** stems with a real
AI model (Demucs v4 Hybrid Transformer), make **karaoke tracks**, and **convert** between
MP3 / WAV / FLAC / OGG / M4A — from a responsive web UI that works on desktop, tablet,
and mobile browsers.

Phase 1 MVP. The same backend API is designed to later power a PWA, a Chrome extension,
and native mobile clients.

## Quick start

### Prerequisites

- Python 3.10+, Node 20+
- **ffmpeg + ffprobe** on PATH (`apt install ffmpeg` / `brew install ffmpeg`)
- ~1 GB free disk for the PyTorch CPU wheels + the Demucs checkpoint (downloaded once)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
# CPU-only PyTorch FIRST (so pip never pulls the multi-GB CUDA wheels):
pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install --no-cache-dir -r requirements.txt
cp ../.env.example ../.env   # optional; defaults work for dev
PYTHONPATH=src uvicorn audioapp.main:app --port 8000
```

**Model download (one time):** the Demucs `htdemucs` checkpoint downloads automatically
from the official Meta file host on first separation (a few hundred MB, cached in the
torch hub cache). To prefetch:

```bash
PYTHONPATH=src python -c "
from audioapp.models.demucs_adapter import DemucsAdapter
DemucsAdapter('htdemucs').warmup()"
```

Check `GET http://localhost:8000/api/v1/health` → `models_cached` shows what's on disk.

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000  (API calls proxy to :8000)
```

### Docker

```bash
docker compose up --build
# frontend http://localhost:3000, backend http://localhost:8000
```

### Tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=src pytest -q                          # unit + API tests (AI worker mocked)
RUN_REAL_MODEL_TESTS=1 PYTHONPATH=src pytest -q -m realmodel   # real Demucs, 8s synthetic clip
```

Test results (2026-10-08, CPU-only VM):
- Unit/API suite: **39 passed, 1 skipped, 1 xfailed** (`pytest -q`, AI worker mocked)
- Real-model integration: **1 passed** (`RUN_REAL_MODEL_TESTS=1 pytest -m realmodel`;
  real Demucs `htdemucs` on an 8s synthesized clip — duration/channels/integrity
  preserved; no separation-quality claims)
- The 1 xfail is by design: a header-intact truncated file passes ffprobe, so
  upload accepts it and the pipeline fails the job gracefully at decode time.

## How it works

1. **Upload** (`POST /api/v1/uploads`): file is validated by size, then inspected with
   `ffprobe` — the *actual* codec is detected, not just the extension. You also confirm
   you have the rights to process the audio.
2. **Job** (`POST /api/v1/jobs`): pick a mode (Vocal Isolation, Karaoke, Vocal+Instrumental,
   Acapella, Instrument Extractor, Custom stems, or plain Convert), the model, and export
   settings (format, bitrate, sample rate, channels, file naming).
3. A background worker runs the pipeline
   `validating → queued → processing → encoding → completed`
   (terminal: `failed`, `cancelled`, `expired`). Poll `GET /api/v1/jobs/{id}` —
   progress is honest stage text, never an invented percentage.
4. **Results** (`GET /api/v1/jobs/{id}/results`): preview every stem in the browser
   (waveforms, volume/mute/solo, original-vs-processed compare), then download
   individual files or everything at once.
5. Results auto-expire (default 24 h, configurable); uploads without jobs expire after
   2 h. Files are deleted from disk — nothing is kept, nothing trains any model.

API docs (OpenAPI/Swagger): http://localhost:8000/docs

## Modes → stems (model `htdemucs`: vocals / drums / bass / other)

| Mode | Outputs |
|---|---|
| Vocal Isolation | vocals |
| Karaoke Maker | instrumental (drums+bass+other mixed) |
| Vocal + Instrumental | vocals, instrumental |
| Acapella Extraction | vocals (may contain reverb/backing vocals — not guaranteed studio-clean) |
| Instrument Extractor | drums, bass, other (+guitar, piano with `htdemucs_6s`) |
| Custom | any subset the selected model genuinely outputs |
| Convert | re-encoded original, no AI involved |

Export: **MP3** (128/192/320 kbps), **WAV** (16-bit PCM), **FLAC**, **OGG** (q0–q10),
**M4A/AAC**. Note: converting a lossy file to WAV does not restore lost quality.

## Configuration

All settings are env vars (prefix `AUDIOAPP_`), see `.env.example`:
`AUDIOAPP_DATA_DIR`, `AUDIOAPP_MAX_UPLOAD_MB` (200), `AUDIOAPP_MAX_DURATION_S` (600),
`AUDIOAPP_RESULTS_TTL_HOURS` (24), `AUDIOAPP_UPLOAD_TTL_HOURS` (2),
`AUDIOAPP_SEPARATOR_WORKERS` (1 — raise only with GPU workers),
`AUDIOAPP_DEMUCS_MODEL` (htdemucs | htdemucs_ft | htdemucs_6s), `AUDIOAPP_DEVICE` (auto|cpu|cuda).

## Model & license notes

- **Model:** Demucs v4 Hybrid Transformer via the `demucs-infer` package
  (inference-only, PyTorch 2.x compatible; the original `facebookresearch/demucs`
  repo was archived Jan 2025). Nothing is trained — pretrained checkpoints only.
  CPU works; CUDA is used automatically when available.
- **License — read before commercial use:** the Demucs *code* is MIT, but the official
  *pretrained weights* are stated by the author to be "provided only for scientific
  purposes" — there is **no commercial grant** for them. This MVP is fine for
  personal/prototype use. Do not deploy commercially on these weights without
  resolving rights; the `SeparatorAdapter` interface exists precisely so a
  commercially-cleared model can be swapped in later. Weights are downloaded at
  runtime by the operator and are never bundled in this repo or the Docker image.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture, API contract,
folder structure, and build plan.
