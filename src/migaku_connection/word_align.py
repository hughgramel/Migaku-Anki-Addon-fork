"""
Subprocess wrapper around tools/align.py — wav2vec2 forced alignment of a
known sentence to a short audio clip.

Anki's bundled Python doesn't (and shouldn't) ship torch/whisperx. Users
install whisperx into a separate Python (`pipx install whisperx`) and
point the addon at it via the `align_python_path` config key. We shell
out, parse JSON, and return word timings.

This module never raises into the card-creation path. On any failure —
sidecar missing, model download timed out, language unsupported — it
logs and returns an empty list.
"""
import json
import logging
import os
import re
import subprocess
from typing import Optional

from .. import config
from .. import util

logger = logging.getLogger("migaku.word_align")

SOUND_TAG_RE = re.compile(r"\[sound:([^\]]+)\]")
LANGUAGE_KEYS = (
    "language",
    "lang",
    "targetLanguage",
    "sourceLanguage",
    "languageCode",
    "langCode",
    "deck_language",
    "deckLanguage",
)

ADDON_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
ALIGN_SCRIPT = os.path.join(ADDON_ROOT, "tools", "align.py")


def is_enabled() -> bool:
    return bool(config.get("align_enabled", False))


def python_path() -> Optional[str]:
    p = config.get("align_python_path", "")
    return p.strip() or None


def align(audio_path: str, text: str, language: str, timeout_sec: int = 120) -> list[dict]:
    """Return [{"surface","start","end"}] for the words in `text` placed
    against `audio_path`. Empty list on any failure."""
    if not is_enabled():
        return []
    if not text or not text.strip():
        return []
    if not language:
        logger.info("align: no language; skipping")
        return []
    if not os.path.isfile(audio_path):
        logger.info("align: audio not found at %s; skipping", audio_path)
        return []
    py = python_path()
    if not py:
        logger.info("align: align_python_path not configured; skipping")
        return []
    if not os.path.isfile(ALIGN_SCRIPT):
        logger.warning("align: sidecar script missing at %s", ALIGN_SCRIPT)
        return []

    payload = json.dumps(
        {
            "audio": audio_path,
            "text": text,
            "language": language,
            "device": config.get("align_device", "cpu"),
        }
    )

    try:
        proc = subprocess.run(
            [py, ALIGN_SCRIPT],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        logger.warning("align: timed out after %ss", timeout_sec)
        return []
    except FileNotFoundError:
        logger.warning("align: python not found at %s", py)
        return []
    except Exception:
        logger.exception("align: subprocess failed")
        return []

    if proc.returncode != 0:
        logger.warning(
            "align: sidecar exit %s — stderr: %s",
            proc.returncode,
            proc.stderr.strip()[:500],
        )
        return []

    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        logger.warning("align: bad JSON from sidecar: %s", proc.stdout[:500])
        return []

    words = out.get("words", [])
    logger.info("align: %d words for %s clip", len(words), language)
    return words


def first_audio_path(sentence_audio_field: str) -> Optional[str]:
    """Pull the first [sound:foo.mp3] filename out of the rendered audio
    field and resolve to an absolute path in Anki's media folder."""
    if not sentence_audio_field:
        return None
    m = SOUND_TAG_RE.search(sentence_audio_field)
    if not m:
        return None
    filename = m.group(1).strip()
    abs_path = util.col_media_path(filename)
    return abs_path if os.path.isfile(abs_path) else None


def detect_language(body: dict) -> str:
    """Extract a language code from the Migaku payload, walking common
    keys at the top level and one level into nested dicts. Falls back to
    the configured `align_language` (empty if unset)."""
    if isinstance(body, dict):
        for k in LANGUAGE_KEYS:
            v = body.get(k)
            if isinstance(v, str) and v.strip():
                logger.info("align: language from payload key %r = %r", k, v)
                return v.strip()[:5].split("-")[0]
        for k, v in body.items():
            if isinstance(v, dict):
                for kk in LANGUAGE_KEYS:
                    vv = v.get(kk)
                    if isinstance(vv, str) and vv.strip():
                        logger.info(
                            "align: language from payload %s.%s = %r", k, kk, vv
                        )
                        return vv.strip()[:5].split("-")[0]
    fallback = (config.get("align_language", "") or "").strip()
    if fallback:
        logger.info("align: language from config fallback = %r", fallback)
    return fallback


def probe(language: str = "en") -> tuple[bool, str]:
    """Quick health check used by the settings 'Test alignment' button.
    Returns (ok, message). Doesn't actually run alignment — only checks
    that the configured Python can import whisperx."""
    py = python_path()
    if not py:
        return False, "Set the path to a Python where `whisperx` is installed."
    if not os.path.isfile(py):
        return False, f"Python not found at {py}."
    try:
        proc = subprocess.run(
            [py, "-c", "import whisperx; print(whisperx.__version__)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return False, "Python import probe timed out."
    except Exception as e:
        return False, f"Could not run Python: {e}"
    if proc.returncode != 0:
        return False, f"whisperx not importable: {proc.stderr.strip()[:300]}"
    return True, f"whisperx {proc.stdout.strip()} OK at {py}"
