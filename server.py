"""Scam Drift v3 web server (post-deadline, Nov 18): a JSON API around the existing checker + the static web/ front end.

Run:  python server.py   (then open http://127.0.0.1:8000)
Needs the same saved models as app.py (create them with: python src/scam_drift.py).
app.py (Gradio) stays the fallback demo and is not changed.
This project is a prototype and is not financial advice.

API (contract shared by the checker and the story page):
  POST /api/check    {"text": str} -> {"tier": "RED|YELLOW|GREEN"|null, "label", "headline", "actions", "reason",
                                       "top_words", "compare_2012", "note", "translation_note", "translation_detail"}
                     translation_note: one short warning line (text may not be English, or too few words to read);
                     translation_detail: an optional smaller line (the dataset translation's result). Neither changes
                     the tier.
  GET  /api/examples -> [{"id", "label", "kind": "REAL|SYNTHETIC", "text", "source"}]
  GET  /api/story    -> key numbers for the story page, each with its results/*.json file and key path

The verdict logic is app.predict's logic (same triage() call, same helpers), returned as data instead of HTML.
Nothing is stored: the text is checked in memory and is not logged or written to disk.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import app as sd  # noqa: E402  (app.py: VERDICT, LABEL, ACTIONS, EXAMPLES, reason_sentence, score, M2012)
from scam_drift import friendly_explain, normalise  # noqa: E402
from triage import DISCLAIMER, triage  # noqa: E402

MAX_CHARS = 20000
WEB = ROOT / "web"


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------
class CheckIn(BaseModel):
    text: str = Field(default="", max_length=MAX_CHARS)


def _shown_words(top_words: list[str]) -> list[str]:
    """Same clean-up as app.predict: strip edge punctuation, drop empties, keep order, no repeats."""
    shown = [w.strip(".,:;!?()\"'") for w in top_words]
    return [w for w in dict.fromkeys(shown) if w]


def _compare_2012(text: str) -> str:
    """The one-line 2012-filter comparison from app.predict, as plain text."""
    norm = normalise(text)
    p12, f12 = sd.score(sd.M2012, norm)
    said = "scam" if f12 else "not a scam"
    w12 = friendly_explain(sd.M2012["pipeline"], norm, k=3)
    w12s = f"; its top words: {', '.join(w for w, _ in w12)}" if (f12 and w12) else ""
    return f"2012 filter said: {said} (score {p12:.2f}, its warning level {sd.M2012['threshold']:.2f}){w12s}."


_LETTER_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _probably_not_english(text: str) -> bool:
    """Rough cue only (no language model): many non-Latin letters, or long text with almost no English stop words."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    letters = [c for c in text if c.isalpha()]
    if letters and sum(ord(c) > 0x24F for c in letters) / len(letters) > 0.3:
        return True
    words = [w.lower() for w in _LETTER_RE.findall(re.sub(r"<[A-Z_]+>", " ", text))]
    if len(words) < 6:
        return False
    return sum(w in ENGLISH_STOP_WORDS for w in words) / len(words) < 0.12


_URL_RE = re.compile(r"https?://\S+|www\.\S+|<[A-Z_]+>", re.I)


def _few_words(text: str) -> bool:
    """Input-quality cue (no model change): fewer than 3 words of 2+ letters once links and dataset tags are removed
    (emoji only, a single letter, a bare link)."""
    words = [w for w in _LETTER_RE.findall(_URL_RE.sub(" ", text)) if len(w) >= 2]
    return len(words) < 3


def _translation_note(text: str, tier: str) -> tuple[str, str]:
    """(short warning line, smaller detail line). Plain words for the user; the tier is never changed here."""
    stripped = text.strip()
    if _probably_not_english(text):
        warn = ("This text may not be in English. The checker mainly reads English, so do not trust a "
                "“No warning signs” answer. Ask a family member before you reply.")
    elif tier == "GREEN" and _few_words(text):
        warn = ("This message has too few words for the checker to read. Ask a family member before you reply.")
    else:
        return "", ""
    detail = ""
    tr = sd._TRANSLATIONS.get(stripped)
    if tr:
        tr_tier = triage(tr)["tier"]
        detail = (f"In the dataset’s English translation of this text, the checker says: {sd.LABEL[tr_tier]}. "
                  "The translation comes from the dataset, not from this app.")
    return warn, detail


def check(text: str) -> dict:
    """app.predict as data. Tier comes from the same triage() call app.predict makes."""
    if not text or not text.strip():
        return {"tier": None, "label": "", "headline": "Paste a text message above, then press “Check this text”.",
                "actions": [], "reason": "", "top_words": [], "compare_2012": "", "note": "",
                "translation_note": "", "translation_detail": ""}
    res = triage(text)
    tier = res["tier"]
    note = sd._NOTES.get(text.strip(), "")
    warn, detail = _translation_note(text, tier)
    safety = bool(res.get("safety"))
    return {"tier": tier, "safety": safety,
            "label": "Safety warning" if safety else sd.LABEL[tier],
            "headline": "Possible danger - do not meet, tell a trusted adult" if safety else sd.VERDICT[tier],
            "actions": list(sd.SAFETY_ACTIONS if safety else sd.ACTIONS[tier]),
            "reason": sd.reason_sentence(text, res), "top_words": _shown_words(res["top_words"]),
            "compare_2012": _compare_2012(text), "note": note, "translation_note": warn,
            "translation_detail": detail}


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
api = FastAPI(title="Scam Drift", docs_url=None, redoc_url=None, openapi_url=None)


@api.middleware("http")
async def _headers(request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@api.post("/api/check")
def api_check(body: CheckIn):
    return JSONResponse(check(body.text))


@api.get("/api/examples")
def api_examples():
    return JSONResponse(examples())


@api.get("/api/story")
def api_story():
    return JSONResponse(story())


api.mount("/", StaticFiles(directory=WEB, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="127.0.0.1", port=8000, log_level="warning", access_log=False)
