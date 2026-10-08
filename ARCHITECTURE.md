# AI Audio Separator — Architecture & Build Plan (Phase 1 MVP)

## 1. Proposed architecture

```
┌─────────────────────────────┐
│  Frontend (Next.js + React + TS + Tailwind)  │  desktop / tablet / mobile browsers
│  pages: Home, Separator, Karaoke, Extract,   │  (PWA + Chrome extension in Phase 3)
│  Converter, Projects, Settings               │
└──────────────┬──────────────────────────────┘
               │  REST / JSON  (OpenAPI from FastAPI)
┌──────────────▼──────────────────────────────┐
│  Backend API (Python + FastAPI)              │
│  - /api/v1/uploads   (multipart, ffprobe     │
│    validation: REAL codec via ffprobe, not   │
│    just extension; size/duration/integrity)  │
│  - /api/v1/jobs      (mode/stem/export       │
│    validation → job_id → enqueue)            │
│  - status / results / download / cancel /   │
│    delete endpoints; expiring results        │
├─────────────────────────────────────────────┤
│  JobStore (interface) → SQLite impl (MVP)    │  never stores audio bytes in DB
│  TaskQueue (interface) → LocalThreadQueue    │  ThreadPoolExecutor, CPU concurrency
│  (MVP); Redis/RQ-compatible swap later      │  limit, retry, timeout, cancel events
├─────────────────────────────────────────────┤
│  Pipeline: validate → separate (model       │
│  adapter) → encode (ffmpeg) → store results  │
│  SeparatorAdapter (ABC): DemucsAdapter (real │  CPU default; CUDA optional
│  model), FakeAdapter (tests only, injected)  │
│  ffmpeg: decode/resample/encode/inspect via  │
│  subprocess ARG LISTS only (no shell, no    │
│  user-filename interpolation)               │
└─────────────────────────────────────────────┘
Storage: local filesystem DATA_DIR/{uploads,jobs,models}; object-storage
interface placeholder for scale. Retention sweeper deletes expired jobs.
Config: env vars (.env.example). Structured logging, no audio content in logs.
```

Same backend powers web now; PWA/extension/native later reuse the API (Phase 3).

## 2. Folder structure

```
ai-audio-separator/
├── ARCHITECTURE.md  README.md  .env.example  .gitignore
├── docker-compose.yml
├── backend/
│   ├── Dockerfile  requirements.txt  requirements-dev.txt
│   └── src/audioapp/
│       ├── __init__.py  main.py  config.py
│       ├── api/{__init__.py,routes.py,schemas.py}
│       ├── core/{__init__.py,store.py,queueing.py,retention.py,logging_setup.py}
│       ├── audio/{__init__.py,ffmpeg.py,validate.py}
│       ├── models/{__init__.py,base.py,demucs_adapter.py,registry.py}
│       └── workers/{__init__.py,pipeline.py}
│   └── tests/{conftest.py,test_validation.py,test_api_jobs.py,
│              test_worker.py,test_integration_real_model.py,testdata/make_testdata.sh}
└── frontend/
    ├── Dockerfile  package.json  next.config.ts  tailwind.config.ts
    └── src/
        ├── app/{layout.tsx,page.tsx,separator/page.tsx,karaoke/page.tsx,
        │        extract/page.tsx,convert/page.tsx,projects/page.tsx,settings/page.tsx}
        ├── components/{UploadDropzone.tsx,WaveformPlayer.tsx,ModeSelect.tsx,
        │        ExportSettings.tsx,JobProgress.tsx,ResultsScreen.tsx,Nav.tsx}
        └── lib/{api.ts,types.ts}
```

## 3. API contract (base `/api/v1`, JSON)

- `POST /uploads` — multipart: `file` (binary), `rights_confirmed` (bool, must be true).
  `201 {upload_id, filename, size_bytes, meta:{format_name,codec_name,duration_s,sample_rate,channels,bit_depth}, warnings[]}`
  Errors: `400` rights not confirmed / empty / unsupported codec / corrupted / bad extension-vs-codec mismatch that can't be decoded; `413` over size limit.
- `POST /jobs` — `{upload_id, mode, model?, stems?, export:{format,bitrate_kbps?,sample_rate?,channels?,filename?}}`
  Modes: `vocal_isolation | karaoke | vocal_instrumental | acapella | instruments | custom | convert`.
  `201 {job_id, status:"uploaded"}` → worker moves it through states.
  `400` unknown upload / unsupported mode+model+stem combination / invalid export settings.
- `GET /jobs/{job_id}` — `{job_id,status,mode,model,stage_detail,progress:{measurable:bool,fraction?:0..1,message},created_at,updated_at,expires_at,error?:{code,message},upload:{filename,meta}}`
- `GET /jobs/{job_id}/results` — `{job_id,status,outputs:[{output_id,kind:"stem"|"mix",stem,label,format,size_bytes,duration_s,sample_rate,channels,bitrate_kbps?,download_url}]}` (`download_url` is a relative API path, never a storage path)
- `GET /jobs/{job_id}/download/{output_id}` — file bytes, `Content-Disposition: attachment`; `404` unknown, `410` expired.
- `POST /jobs/{job_id}/cancel` — `409` if already terminal; else `{job_id,status:"cancelled"}`.
- `DELETE /jobs/{job_id}` — `204`, deletes files + record.
- `GET /models` — `[{id,name,stems[],description,license_note,maintenance_note,default}]`
- `GET /health` — `{status,ffmpeg:bool,models_cached:[],queue:{queued,active,max_workers},retention_hours}`

Job states: `uploaded → validating → queued → processing → encoding → completed`
(terminal failures: `failed`, `cancelled`, `expired`).
Progress: `progress.measurable=false` + human message unless the model reports real fractions — never invent a percentage.

Stem mapping (Demucs `htdemucs`: vocals/drums/bass/other; `htdemucs_6s`: +guitar+piano):
vocal_isolation→[vocals]; karaoke→[instrumental mix of drums+bass+other];
vocal_instrumental→[vocals, instrumental]; acapella→[vocals] (UI copy notes possible bleed);
instruments→[drums,bass,other(+guitar,piano if model supports)]; custom→user subset of model stems;
convert→no separation, re-encode original only.

Export formats (MVP): `mp3` (bitrate 128/192/320 kbps, default 192), `wav` (16-bit PCM),
`flac`, `ogg` (quality q0–q10, default q5), `m4a` (AAC bitrate). Defaults chosen for beginners.

## 4. Selected AI model + licensing

**Model: Demucs v4 — Hybrid Transformer Demucs (`htdemucs`, 4 stems: vocals/drums/bass/other),**
via the inference-only package **`demucs-infer`** (community fork of Demucs, PyTorch 2.x compatible; original `facebookresearch/demucs` archived Jan 2025, maintained fork `adefossez/demucs` is bug-fix-only). `htdemucs_ft` (fine-tuned 4-checkpoint bag, better quality, slower, bigger download) selectable via config; `htdemucs_6s` adds guitar/piano and is exposed by the `custom`/`instruments` modes when chosen. **Nothing is trained** — pretrained checkpoints only.

**License verdict (verified 2026-10-08):**
- Demucs *code*: MIT — fine to depend on.
- Demucs *pretrained weights*: **NOT covered by MIT.** The author stated (2022) the weights are "provided only for scientific purposes"; no commercial grant exists (trained on MUSDB18-HQ + internal Meta tracks). 
- Consequence: this MVP is suitable for personal/dev/prototype use with the disclaimer shown in Settings + README. **Do not ship commercially on these weights without resolving rights** (obtain a licensed model or swap in a commercially-cleared model through the `SeparatorAdapter` interface — that is exactly what the adapter layer is for). Weights are downloaded at runtime by the operator, never bundled in the repo/image.
- Memory/compute: checkpoint is a few hundred MB; CPU inference works (roughly realtime-ish to a few × realtime depending on CPU; exact speed measured per deployment, never promised). `SEPARATOR_WORKERS=1` default on CPU; CUDA auto-used if available.

Alternatives considered: Open-Unmix (lighter, weaker quality), Spleeter (unmaintained). Rejected for MVP.

## 5. Local development setup

Prereqs: Python 3.10+, Node 20+, **ffmpeg + ffprobe 6+** on PATH.
```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt          # pulls demucs-infer etc.
cp ../.env.example ../.env               # adjust DATA_DIR, limits
python -m audioapp.main                  # or: uvicorn audioapp.main:app --reload --port 8000
# first run downloads the htdemucs checkpoint (~hundreds of MB) on first separation;
# prefetch with: python -c "from audioapp.models.demucs_adapter import DemucsAdapter; DemucsAdapter().warmup()"
# frontend
cd frontend && npm install && npm run dev  # http://localhost:3000 (proxies /api → :8000)
# tests
cd backend && pytest -q                     # unit/integration (model mocked)
RUN_REAL_MODEL_TESTS=1 pytest -q -m realmodel  # real Demucs on an 8s synthetic clip
```
Docker: `docker compose up --build` (api+worker in one backend container, frontend container).

## 6. Implementation plan (small, testable tasks)

1. Config + logging + error types (env-driven settings).
2. ffmpeg/ffprobe safe wrappers + `AudioMeta` inspection.
3. Upload validation (size, duration, integrity, real codec; honest errors).
4. SQLite JobStore (interface-first) + filesystem layout.
5. LocalThreadQueue with concurrency limit, retry, cancel events.
6. SeparatorAdapter ABC + DemucsAdapter (real inference, chunked, thread-safe, CUDA-optional).
7. Pipeline: validating→queued→processing→encoding→completed/failed/cancelled; ffmpeg mixing for karaoke/instrumental; per-format encoding.
8. FastAPI routes per contract + OpenAPI; expiring download guard; retention sweeper; health.
9. Frontend: layout/nav; Home; upload flow (dropzone, meta, waveform preview, rights checkbox); mode select; export settings; job progress (honest indicator); results (players, waveforms, volume/mute/solo, downloads, download-all); Projects; Settings; responsive CSS.
10. Tests: validation matrix, API state transitions (fake adapter), worker retry/cancel, download auth/expiry, export-setting validation; testdata generator (ffmpeg-synthesized tones, no copyrighted audio); gated real-model integration test (duration/channels/integrity checks only — never claim quality from API success).
11. Dockerfiles + compose + .env.example + README; run full suite green; commit.
