#!/usr/bin/env python3
"""
wav2vec2 forced alignment of a known sentence to a short audio clip.

Sidecar to the Migaku Anki addon. Runs in a *user-supplied* Python env
(`pipx install whisperx` is the recommended setup) — NOT in Anki's
bundled Python. Anki's addon shells out via subprocess.

Input: JSON on stdin, single object:
  {"audio": "/abs/path.mp3", "text": "...", "language": "es", "device": "cpu"}

Output: JSON on stdout, single object:
  {"language": "es", "duration": 6.42, "words": [
     {"surface": "hola", "start": 0.12, "end": 0.41}, ...
  ]}

Errors go to stderr with non-zero exit. The addon treats any non-zero
exit as "skip alignment for this card" — never blocks card creation.
"""
import json
import sys

import whisperx


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print("error: empty stdin", file=sys.stderr)
        return 2
    req = json.loads(raw)

    audio_path = req["audio"]
    text = req["text"].strip()
    language = req["language"]
    device = req.get("device", "cpu")

    if not text:
        print("error: empty text", file=sys.stderr)
        return 2

    audio = whisperx.load_audio(audio_path)
    duration = float(len(audio)) / 16000.0

    segments = [{"text": text, "start": 0.0, "end": duration}]

    align_model, metadata = whisperx.load_align_model(
        language_code=language,
        device=device,
    )
    result = whisperx.align(
        segments,
        align_model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    words = []
    for w in result.get("word_segments", []):
        start = w.get("start")
        end = w.get("end")
        if start is None or end is None:
            continue
        words.append(
            {
                "surface": (w.get("word") or "").strip(),
                "start": float(start),
                "end": float(end),
            }
        )

    json.dump(
        {"language": language, "duration": duration, "words": words},
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
