import json
import logging
import re

import aqt
from anki.notes import Note
from ..config import get
from ..card_types import CardFields, card_fields_from_dict
from ..editor.current_editor import (
    add_cards_add_to_history,
    get_add_cards_info,
    map_to_add_cards,
)
from tornado.web import RequestHandler

from .migaku_http_handler import MigakuHTTPHandler
from . import word_align

logger = logging.getLogger("migaku.connection.card_receiver")


class CardReceiver(MigakuHTTPHandler):
    def post(self: RequestHandler):
        try:
            raw_body = self.request.body
            logger.info(f"[DEBUG-PAYLOAD] Raw request body from {self.request.remote_ip}: {raw_body!r}")
            body = json.loads(raw_body)
            logger.info(f"[DEBUG-PAYLOAD] Parsed top-level keys: {sorted(body.keys())}")
            for k, v in body.items():
                preview = repr(v)
                if len(preview) > 500:
                    preview = preview[:500] + f"... (truncated, total len={len(preview)})"
                logger.info(f"[DEBUG-PAYLOAD]   {k} = {preview}")
            card = card_fields_from_dict(body)
            logger.debug(f"Received card creation request from {self.request.remote_ip}")
            self.create_card(card, body)
        except Exception as e:
            logger.error(f"Failed to process card receiver request: {e}", exc_info=True)
            self.finish({"success": False, "error": f"Invalid request: {str(e)}."})
        return

    def create_card(self, card: CardFields, body=None):
        if get("migakuIntercept", False) and map_to_add_cards(card):
            logger.info("Card mapped to Add Cards window (intercept mode)")
            print("Tryied to map to add cards.")
            aqt.mw.taskman.run_on_main(
                lambda: aqt.utils.tooltip("Mapped Migaku fields to Add cards window.")
            )
            self.finish(
                json.dumps(
                    {
                        "success": True,
                        "created": False,
                    }
                )
            )
            return

        info = get_add_cards_info()

        note = Note(aqt.mw.col, info["notetype"])
        fields = info["fields"]

        if not any([type != "none" for (fieldname, type) in fields.items()]):
            logger.warning("Card creation failed: No fields configured to map to")
            print("No fields to map to.")
            aqt.mw.taskman.run_on_main(
                lambda: aqt.utils.tooltip(
                    "Could not create Migaku Card: No fields to map to."
                )
            )
            self.finish(
                {
                    "success": False,
                    "error": "No fields to map to.",
                }
            )
            return

        addcards_note = info["note"] if "note" in info else None

        for fieldname, type in fields.items():
            note[fieldname] = (
                str(getattr(card, type))
                if type != "none"
                else addcards_note[fieldname]
                if addcards_note
                else ""
            )

        note.tags = info["tags"]
        note.model()["did"] = int(info["deck_id"])

        aqt.mw.col.addNote(note)
        aqt.mw.col.save()
        aqt.mw.taskman.run_on_main(aqt.mw.reset)
        aqt.mw.taskman.run_on_main(lambda: aqt.utils.tooltip("Migaku Card created"))
        aqt.mw.taskman.run_on_main(lambda: add_cards_add_to_history(note))
        logger.info(f"Card created successfully. Note ID: {note.id}")
        print(f"Card created. ID: {note.id}.")

        self._maybe_schedule_alignment(card, note.id, fields, body or {})

        self.finish(
            json.dumps(
                {
                    "success": True,
                    "created": True,
                    "id": note.id,
                }
            )
        )

    def _maybe_schedule_alignment(
        self,
        card: CardFields,
        note_id: int,
        fields: dict,
        body: dict,
    ):
        """Kick off wav2vec2 word alignment in the background and patch
        the wordTimings field once it returns. Never blocks card creation.

        Worker runs on a daemon Thread (subprocess.run blocks fine there);
        the note.flush() that writes the result is dispatched to the Qt
        main thread via aqt.mw.taskman.run_on_main. Any failure is logged
        and silently swallowed — never affects the original card create.
        """
        if not word_align.is_enabled():
            return

        target_fieldname = next(
            (fn for fn, t in fields.items() if t == "wordTimings"), None
        )
        if not target_fieldname:
            logger.debug("align: no field mapped to wordTimings; skipping")
            return

        sentence_text = (card.sentenceNoSyntax or card.sentence or "").strip()
        if not sentence_text:
            logger.debug("align: empty sentence; skipping")
            return

        audio_path = word_align.first_audio_path(card.sentenceAudio)
        if not audio_path:
            logger.info("align: no audio file found in sentenceAudio; skipping")
            return

        language = word_align.detect_language(body)
        if not language:
            logger.info("align: no language detected and no fallback set; skipping")
            return

        def do_align():
            return word_align.align(audio_path, sentence_text, language)

        def on_done(words):
            if not words:
                return
            try:
                note = aqt.mw.col.get_note(note_id)
            except Exception:
                logger.exception("align: failed to load note %s", note_id)
                return
            note[target_fieldname] = json.dumps(words, ensure_ascii=False)
            note.flush()
            aqt.mw.col.save()
            logger.info(
                "align: patched %s words into note %s field %r",
                len(words),
                note_id,
                target_fieldname,
            )

        def runner():
            try:
                words = do_align()
            except Exception:
                logger.exception("align: background alignment crashed")
                words = []
            aqt.mw.taskman.run_on_main(lambda: on_done(words))

        import threading

        threading.Thread(target=runner, daemon=True).start()
