"""Scam Drift v3 web server (post-deadline, Nov 18): a JSON API around the existing checker + the static web/ front end.

Run:  python server.py   (then open http://127.0.0.1:8000)
Needs the same saved models as app.py (create them with: python src/scam_drift.py).
app.py (Gradio) stays the fallback demo and is not changed.
This project is a prototype and is not financial advice.

API (contract shared by the checker and the story page):
  POST /api/check    {"text": str} -> tier, label, headline, actions, reason, signals, top_words,
                       input_quality, safety, uncertain, version, and optional context for examples.
  GET  /api/examples -> [{"id", "label", "kind": "REAL|SYNTHETIC", "text", "source"}]
  GET  /api/story    -> key numbers for the story page, each with its results/*.json file and key path

The web checker uses the saved classifier plus its own warning and input-quality policy.
The Gradio and historical experiment paths use the original policy. Submitted text is checked in memory.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import app as sd  # noqa: E402
from scam_drift import friendly_explain, normalise  # noqa: E402
from triage import DISCLAIMER, triage  # noqa: E402
from web_triage import VERSION, assess  # noqa: E402
from context_model import load_context_model  # noqa: E402

MAX_CHARS = 20_000
MAX_BODY_BYTES = 256 * 1024
LOG = logging.getLogger(__name__)
WEB = ROOT / "web"
STUDY = ROOT / "web-william"


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------
def _shown_words(top_words: list[str]) -> list[str]:
    """Same clean-up as app.predict: strip edge punctuation, drop empties, keep order, no repeats."""
    shown = [w.strip(".,:;!?()\"'") for w in top_words]
    return [w for w in dict.fromkeys(shown) if w]


def _compare_2012(text: str) -> str:
    """The one-line 2012-filter comparison from app.predict, as plain text."""
    norm = normalise(text)
    p12, f12 = sd.score(sd.M2012, norm)
    said = "above its warning threshold" if f12 else "below its warning threshold"
    w12 = friendly_explain(sd.M2012["pipeline"], norm, k=3)
    w12s = f"; its top words: {', '.join(w for w, _ in w12)}" if (f12 and w12) else ""
    return f"2012 filter scored this text {said} (score {p12:.2f}, its warning level {sd.M2012['threshold']:.2f}){w12s}."


_ACTIONS = {
    "verify": "Open the official app yourself or call a number you already trust.",
    "codes": "Keep one-time codes, PINs, and passwords private, even if the sender says they are support.",
    "money": "Do not send money, gift cards, or cryptocurrency while you check the request.",
}


def _next_steps(tier: str, ids: set[str], safety: bool) -> list[str]:
    if safety:
        return ["Do not meet this person or go anywhere with them.",
                "Show the message to a trusted adult. Keep it as evidence.",
                "If anyone is in immediate danger, call your local emergency number."]
    if ids & {"credential", "account_link"}:
        return [_ACTIONS["codes"], "Do not open the link or call a number from the text.", _ACTIONS["verify"],
                "If you already shared a code or password, contact your account provider through a trusted channel."]
    if ids & {"gift_card", "job_fee", "rental_deposit", "payment_method", "qr_payment", "fee_pressure", "investment"}:
        return [_ACTIONS["money"], "Contact the person or organisation through a channel you already use.",
                "If you already paid, contact your payment provider promptly and ask what can be reversed."]
    if "new_number" in ids:
        return ["Call the person on the number you saved before this message.", _ACTIONS["money"], _ACTIONS["codes"]]
    if "personal_safety" in ids:
        return ["Do not send a private photo or share where you are.", "Show the message to someone you trust."]
    if tier == "RED":
        return ["Do not open links or reply to the text.", _ACTIONS["money"], _ACTIONS["verify"]]
    if tier == "YELLOW":
        return ["Ask someone you trust to look at the text with you.", _ACTIONS["verify"], _ACTIONS["codes"]]
    return [_ACTIONS["verify"], _ACTIONS["codes"]]


def check(text: str) -> dict:
    """Return a warning with concrete evidence and next steps."""
    if not text.strip():
        return {"tier": None, "label": "", "headline": "Paste a text message to check.",
                "actions": [], "reason": "", "top_words": [], "signals": [], "compare_2012": "",
                "note": "", "translation_note": "", "translation_detail": "",
                "input_quality": "empty", "version": VERSION, "safety": False, "uncertain": False,
                "context_model": "lexical"}

    result = assess(text)
    tier, safety = result["tier"], result["safety"]
    ids = {signal["id"] for signal in result["signals"]}
    quality = result["input_quality"]
    warn, detail = "", ""
    if quality == "possible_non_english":
        warn = "The checker mainly reads English. Ask someone you trust to read the message with you."
    elif quality == "limited_text":
        warn = "This text gives very little context. Verify the request before you act."
    translation = sd._TRANSLATIONS.get(text.strip())
    if translation and warn:
        translation_tier = triage(translation)["tier"]
        detail = f"The dataset's English translation received this result: {sd.LABEL[translation_tier]}."

    if safety:
        label, headline = "Personal safety warning", "Do not meet. Tell a trusted adult."
    elif result["uncertain"]:
        label, headline = "Needs another check", "Verify this message before you act."
    else:
        label = sd.LABEL[tier]
        headline = {"RED": "Stop and verify the request.", "YELLOW": "Pause before you reply or pay.",
                    "GREEN": "No warning signs found."}[tier]

    if ids - {"model", "neural_model", "contact"}:
        reason = "The checker found these specific requests or patterns."
    elif "neural_model" in ids:
        reason = "The fine-tuned model found a pattern across the message. Review the request with someone you trust."
    elif "model" in ids:
        reason = "The wording resembles messages the saved filter flagged."
    elif result["uncertain"]:
        reason = "The text may be too short or outside the language this checker reads best."
    else:
        reason = "The checker cannot verify who sent this message or whether its request is genuine."

    return {**result, "version": VERSION, "label": label, "headline": headline,
            "actions": _next_steps(tier, ids, safety), "reason": reason,
            "top_words": _shown_words(result["top_words"]), "compare_2012": _compare_2012(text),
            "note": sd._NOTES.get(text.strip(), ""), "translation_note": warn, "translation_detail": detail}


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------
def examples() -> list[dict]:
    out = []
    for i, (label, text, note) in enumerate(sd.EXAMPLES, start=1):
        kind = "REAL" if label.upper().startswith("REAL") else "SYNTHETIC"
        short = re.sub(r"^(REAL|SYNTHETIC)\s+", "", label)
        short = re.sub(r"'([^']+)' ", lambda m: m.group(1).replace(" ", "-") + " ", short)  # 'wrong number' scam
        out.append({"id": f"ex{i}", "label": short[:1].upper() + short[1:], "kind": kind, "text": text,
                    "source": note.split(". ")[0].rstrip(".") + "."})
    return out


# ---------------------------------------------------------------------------
# Story numbers (read on every request, so the page always shows the files on disk)
# ---------------------------------------------------------------------------
PROBE = "results/real_ham_fix_probe.json"
METRICS = "results/metrics.json"

# (id, file, key path, plain-language label)
STORY_KEYS = [
    ("y2012_uci_recall", PROBE, "word_2012.uci_test.recall",
     "2012 filter: share of spam caught on its own era's test set (UCI 2012)"),
    ("y2012_late_recall", PROBE, "word_2012.late_2022_24_recall",
     "2012 filter: share of real 2022-24 scams caught"),
    ("y2012_late_recall_v1", METRICS, "modern_late_test.word_2012.recall_at_threshold",
     "2012 filter: share of real 2022-24 scams caught (v1 metrics file)"),
    ("y2012_fa_real_legit", PROBE, "word_2012.fa_india_heldout_brands",
     "2012 filter: false alarms on real modern legitimate business texts (held-out brands)"),
    ("naive_fix_late_recall", PROBE, "word_naive_fix.late_2022_24_recall",
     "Naive fix (retrain on modern scams): share of real 2022-24 scams caught"),
    ("naive_fix_late_recall_v1", METRICS, "modern_late_test.word_fixed.recall_at_threshold",
     "Naive fix: share of real 2022-24 scams caught (v1 metrics file)"),
    ("naive_fix_fa_real_legit", PROBE, "word_naive_fix.fa_india_heldout_brands",
     "Naive fix: false alarms on real modern legitimate business texts (held-out brands)"),
    ("real_ham_fix_late_recall", PROBE, "word_fix_real_ham.late_2022_24_recall",
     "Fix + real legitimate texts in training: share of real 2022-24 scams caught"),
    ("real_ham_fix_fa_real_legit", PROBE, "word_fix_real_ham.fa_india_heldout_brands",
     "Fix + real legitimate texts in training: false alarms on real modern legitimate business texts"),
    ("ships_model", METRICS, "v2.triage.shipped_model", "Shipped model"),
    ("ships_threshold", METRICS, "v2.triage.threshold", "Shipped model warning level (threshold)"),
    ("ships_warned_scams_2022_24", METRICS, "v2.triage.sets.scams_2022_24_english.share_red_or_yellow",
     "Shipped checker: real 2022-24 English scams that get RED or AMBER"),
    ("ships_red_scams_2022_24", METRICS, "v2.triage.sets.scams_2022_24_english.share_red",
     "Shipped checker: real 2022-24 English scams that get RED"),
    ("ships_warned_cluster_safe", METRICS, "v2.triage.sets.scams_2022_24_cluster_safe.share_red_or_yellow",
     "Shipped checker: real 2022-24 scams with near-copies of training scams removed, RED or AMBER"),
    ("ships_fa_real_legit", METRICS, "v2.triage.sets.real_legit_india_heldout.share_red_or_yellow",
     "Shipped checker: real modern legitimate business texts (held-out) that get RED or AMBER"),
    ("ships_fa_moz", METRICS, "v2.triage.sets.real_legit_moz_portuguese.share_red_or_yellow",
     "Shipped checker: real legitimate Portuguese texts that get RED or AMBER"),
    ("ships_fa_uci_ham", METRICS, "v2.triage.sets.uci_test_ham.share_red_or_yellow",
     "Shipped checker: 2012 legitimate texts (UCI test) that get RED or AMBER"),
    ("ships_nonenglish_raw", METRICS, "v2.triage.sets.scams_nonenglish_raw_text.share_red_or_yellow",
     "Shipped checker: real non-English scams, raw text, RED or AMBER"),
    ("ships_nonenglish_oracle", METRICS, "v2.triage.sets.scams_nonenglish_translation_oracle.share_red_or_yellow",
     "Shipped checker: the same scams read through the dataset's English translation (oracle), RED or AMBER"),
    ("ships_synthetic_legit_fa", METRICS, "v2.triage.sets.synthetic_legit_heldout.share_red_or_yellow",
     "Shipped checker: SYNTHETIC legitimate texts (held-out categories) that get RED or AMBER"),
]


def _load(rel: str):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _dig(node, path: str):
    for k in path.split("."):
        if not isinstance(node, dict) or k not in node:
            return None
        node = node[k]
    return node


def story() -> dict:
    files = {PROBE: _load(PROBE), METRICS: _load(METRICS)}
    numbers = {}
    for key, rel, path, label in STORY_KEYS:
        raw = _dig(files[rel], path)
        item = {"label": label, "source": rel, "key": path, "value": None, "k": None, "n": None, "ci95": None}
        if isinstance(raw, dict):  # {"rate"/"recall", "k", "n", "ci95"/"wilson95"}
            item["value"] = raw.get("rate")
            item["k"], item["n"] = raw.get("k"), raw.get("n")
            item["ci95"] = raw.get("ci95") or raw.get("wilson95")
            item["key"] = path + ".rate"
        else:
            item["value"] = raw
        numbers[key] = item
    missing = [k for k, v in numbers.items() if v["value"] is None]
    return {"numbers": numbers, "missing": missing, "files": [PROBE, METRICS],
            "rule": "Every number is read from the named results file at request time; nothing is typed in by hand.",
            "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def _lifespan(_app):
    context = await run_in_threadpool(load_context_model)
    if os.environ.get("SCAM_DRIFT_REQUIRE_CONTEXT") == "1" and context is None:
        raise RuntimeError("The fine-tuned model is required but could not load.")
    yield


api = FastAPI(title="Scam Drift", docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)


@api.middleware("http")
async def _headers(request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return obj


@api.post("/api/check")
async def api_check(request: Request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "Send the text as JSON.")
    length = request.headers.get("content-length")
    if length is not None:
        try:
            size = int(length)
        except ValueError:
            raise HTTPException(400, "Invalid request length.") from None
        if size < 0:
            raise HTTPException(400, "Invalid request length.")
        if size > MAX_BODY_BYTES:
            raise HTTPException(413, "The request is too large.")

    body = bytearray()
    try:
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                raise HTTPException(413, "The request is too large.")
            body.extend(chunk)
    except ClientDisconnect:
        raise HTTPException(400, "The request ended early.") from None

    try:
        data = json.loads(body.decode("utf-8"), object_pairs_hook=_json_object)
    except (UnicodeError, ValueError, RecursionError):
        raise HTTPException(400, "Invalid JSON request.") from None
    if not isinstance(data, dict) or set(data) - {"text"} or not isinstance(data.get("text", ""), str):
        raise HTTPException(422, "Provide one text field.")
    text = data.get("text", "")
    if len(text) > MAX_CHARS:
        raise HTTPException(422, "The text is too long.")
    try:
        text.encode("utf-8", errors="strict")
    except UnicodeError:
        raise HTTPException(422, "The text contains an invalid character.") from None

    try:
        return JSONResponse(await run_in_threadpool(check, text))
    except Exception as error:
        LOG.error("Check could not complete (%s)", type(error).__name__)
        raise HTTPException(503, "The checker is temporarily unavailable.") from None


@api.get("/api/examples")
def api_examples():
    return JSONResponse(examples())


@api.get("/api/story")
def api_story():
    return JSONResponse(story())


api.mount("/lab", StaticFiles(directory=WEB, html=True), name="lab")
api.mount("/", StaticFiles(directory=STUDY, html=True), name="study")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="127.0.0.1", port=8000, log_level="warning", access_log=False)
