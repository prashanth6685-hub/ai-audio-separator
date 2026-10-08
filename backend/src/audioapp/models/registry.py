"""Model registry: which models exist, their genuine stems, and how each
product mode maps to stems. Stems are ONLY exposed when the selected model
really outputs them -- never simulated by renaming a full mix."""

from __future__ import annotations

from audioapp.audio.validate import ValidationError
from audioapp.models.base import SeparatorAdapter
from audioapp.models.demucs_adapter import DemucsAdapter

LICENSE_NOTE = (
    "Demucs code is MIT. The official pretrained weights are stated by the "
    "author to be 'provided only for scientific purposes' with no commercial "
    "grant. Fine for personal/prototype use; resolve rights before any "
    "commercial deployment."
)
MAINTENANCE_NOTE = (
    "facebookresearch/demucs archived Jan 2025; officially maintained fork "
    "adefossez/demucs (bug fixes); this app uses the inference-only "
    "demucs-infer package (PyTorch 2.x compatible)."
)

MODELS: dict[str, dict] = {
    "htdemucs": {
        "name": "HTDemucs (recommended)",
        "description": "Hybrid Transformer Demucs v4. Best quality/speed balance for the MVP.",
        "stems": ["drums", "bass", "other", "vocals"],
        "license_note": LICENSE_NOTE,
        "maintenance_note": MAINTENANCE_NOTE,
        "default": True,
    },
    "htdemucs_ft": {
        "name": "HTDemucs fine-tuned (slower, better)",
        "description": "Bag of 4 fine-tuned checkpoints. Better separation, ~4x slower, larger download.",
        "stems": ["drums", "bass", "other", "vocals"],
        "license_note": LICENSE_NOTE,
        "maintenance_note": MAINTENANCE_NOTE,
        "default": False,
    },
    "htdemucs_6s": {
        "name": "HTDemucs 6-stem",
        "description": "Adds guitar and piano stems. Larger download, slower.",
        "stems": ["drums", "bass", "other", "vocals", "guitar", "piano"],
        "license_note": LICENSE_NOTE,
        "maintenance_note": MAINTENANCE_NOTE,
        "default": False,
    },
}

# Modes exposed by the product.
MODES: dict[str, dict] = {
    "vocal_isolation": {"name": "Vocal Isolation", "description": "Extract the lead vocal, minimizing instruments."},
    "karaoke": {"name": "Karaoke Maker", "description": "Remove the lead vocal; keep the instrumental backing."},
    "vocal_instrumental": {"name": "Vocal + Instrumental", "description": "Two complementary stems: vocals and full instrumental."},
    "acapella": {"name": "Acapella Extraction", "description": "Vocal-focused output with minimal instrumental bleed. May still contain reverb or backing vocals -- not guaranteed studio-clean."},
    "instruments": {"name": "Instrument Extractor", "description": "Individual instrument stems the model supports."},
    "custom": {"name": "Custom Separation", "description": "Pick exactly which stems to separate."},
    "convert": {"name": "Audio Converter", "description": "Convert format/quality without AI separation."},
}


def get_adapter(model_id: str, device: str = "auto") -> SeparatorAdapter:
    if model_id not in MODELS:
        raise ValueError(f"unknown model: {model_id}")
    return DemucsAdapter(model_id=model_id, device=device)


def model_stems(model_id: str) -> list[str]:
    return list(MODELS[model_id]["stems"])


def stems_for_mode(mode: str, model_id: str, custom_stems: list[str] | None = None) -> tuple[list[str], bool]:
    """Return (stems_to_separate, needs_instrumental_mix).

    Raises ValidationError on unsupported combinations (surfaced as HTTP 400).
    """
    if mode not in MODES:
        raise ValidationError("invalid_mode", f"Unknown mode '{mode}'.")
    available = set(model_stems(model_id))
    if mode == "vocal_isolation":
        return ["vocals"], False
    if mode == "karaoke":
        return ["drums", "bass", "other"], True
    if mode == "vocal_instrumental":
        return ["vocals", "drums", "bass", "other"], True
    if mode == "acapella":
        return ["vocals"], False
    if mode == "instruments":
        inst = [s for s in model_stems(model_id) if s != "vocals"]
        if not inst:
            raise ValidationError("invalid_mode", "This model has no instrument stems.")
        return inst, False
    if mode == "custom":
        if not custom_stems:
            raise ValidationError("invalid_stems", "Custom mode needs at least one stem selected.")
        unknown = [s for s in custom_stems if s not in available]
        if unknown:
            raise ValidationError(
                "invalid_stems",
                f"Model '{model_id}' does not output these stems: {', '.join(unknown)}. "
                f"Available: {', '.join(model_stems(model_id))}.",
            )
        return list(dict.fromkeys(custom_stems)), False
    if mode == "convert":
        return [], False
    raise ValidationError("invalid_mode", f"Unknown mode '{mode}'.")


def output_plan(mode: str, model_id: str, separated: dict[str, str]) -> list[dict]:
    """Map separated stem files to user-facing outputs.

    `separated`: {stem_name: key}. Returns [{stem, label, source_stems[]}].
    """
    if mode == "karaoke":
        return [{"stem": "instrumental", "label": "Instrumental (karaoke)",
                 "source_stems": ["drums", "bass", "other"]}]
    if mode == "vocal_instrumental":
        return [
            {"stem": "vocals", "label": "Vocals", "source_stems": ["vocals"]},
            {"stem": "instrumental", "label": "Instrumental", "source_stems": ["drums", "bass", "other"]},
        ]
    plans = []
    for stem in separated:
        label = {"vocals": "Vocals", "drums": "Drums", "bass": "Bass",
                 "other": "Other instruments", "guitar": "Guitar",
                 "piano": "Piano"}.get(stem, stem.title())
        plans.append({"stem": stem, "label": label, "source_stems": [stem]})
    return plans
