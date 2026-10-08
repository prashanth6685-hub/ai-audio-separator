"""Upload validation: size, integrity, REAL codec (ffprobe), duration.

Never trust the file extension alone. The extension is only a UX hint;
acceptance is decided by what ffprobe actually finds inside the file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from audioapp.audio.ffmpeg import AudioMeta, FFmpegError, ProbeError, probe_audio
from audioapp.config import Settings

log = logging.getLogger(__name__)


class ValidationError(Exception):
    """User-facing validation failure with a stable machine code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ffprobe codec_name values we can actually decode with this ffmpeg build.
SUPPORTED_CODECS = {
    "mp3",
    "aac",
    "alac",
    "flac",
    "vorbis",
    "opus",
    "wmav1",
    "wmav2",
    "pcm_s16le", "pcm_s16be", "pcm_s24le", "pcm_s24be",
    "pcm_s32le", "pcm_s32be", "pcm_f32le", "pcm_f32be", "pcm_f64le",
    "pcm_u8", "pcm_s8",
    "adpcm_ima_wav", "adpcm_ms",
}

# Extension -> expected family, used only to warn on mismatch.
EXTENSION_HINTS = {
    ".mp3": "mp3", ".wav": "wav", ".flac": "flac", ".m4a": "m4a",
    ".aac": "aac", ".ogg": "ogg", ".opus": "opus", ".wma": "wma", ".aiff": "aiff",
}

# Extension -> codecs that legitimately live in that container.
EXTENSION_CODEC_FAMILIES = {
    ".mp3": {"mp3"},
    ".wav": {"pcm_s16le", "pcm_s16be", "pcm_s24le", "pcm_s24be", "pcm_s32le",
             "pcm_s32be", "pcm_f32le", "pcm_f32be", "pcm_f64le", "pcm_u8",
             "pcm_s8", "adpcm_ima_wav", "adpcm_ms"},
    ".flac": {"flac"},
    ".m4a": {"aac", "alac"},
    ".aac": {"aac"},
    ".ogg": {"vorbis"},
    ".opus": {"opus"},
    ".wma": {"wmav1", "wmav2"},
    ".aiff": {"pcm_s16le", "pcm_s16be", "pcm_s24le", "pcm_s24be", "pcm_s32le",
              "pcm_s32be", "pcm_f32le", "pcm_f32be"},
}


def validate_upload(
    path: Path,
    original_filename: str,
    size_bytes: int,
    settings: Settings,
) -> tuple[AudioMeta, list[str]]:
    warnings: list[str] = []
    if size_bytes <= 0 or not path.exists() or path.stat().st_size == 0:
        raise ValidationError("empty_file", "The file is empty (0 bytes). Please choose a valid audio file.")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationError(
            "file_too_large",
            f"This file is {size_bytes / 1024 / 1024:.1f} MB, over the {settings.max_upload_mb} MB limit.",
        )
    try:
        meta = probe_audio(path)
    except (ProbeError, FFmpegError) as e:
        # FFmpegError: ffprobe exited nonzero (garbage / smashed headers).
        # ProbeError: ffprobe ran but found no usable audio stream.
        raise ValidationError(
            "unreadable_file",
            "This file could not be read as audio. It may be corrupted or in an unsupported format.",
        ) from e

    if meta.codec_name not in SUPPORTED_CODECS:
        raise ValidationError(
            "unsupported_codec",
            f"This file uses the '{meta.codec_name}' codec, which is not supported. "
            "Try MP3, WAV, FLAC, M4A/AAC, OGG, Opus, WMA, or AIFF.",
        )
    if meta.duration_s > settings.max_duration_s:
        raise ValidationError(
            "too_long",
            f"This audio is {meta.duration_s:.0f}s long, over the {settings.max_duration_s}s limit.",
        )

    ext = Path(original_filename).suffix.lower()
    if ext and ext not in EXTENSION_HINTS:
        warnings.append(
            f"The '{ext}' extension is not a recognized audio type; "
            f"the file was accepted because its actual codec ({meta.codec_name}) is supported."
        )
    elif ext:
        expected = EXTENSION_CODEC_FAMILIES.get(ext, set())
        if expected and meta.codec_name not in expected:
            warnings.append(
                f"This file is named '*{ext}' but actually contains "
                f"'{meta.codec_name}' audio. It was accepted because the codec "
                "is supported; consider renaming it to avoid confusion."
            )
    return meta, warnings
