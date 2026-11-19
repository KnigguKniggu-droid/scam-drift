"""Shipped three-tier triage (post-deadline v2 (Nov 18)). Warn-only: it never blocks a message.

    from triage import triage          # with src/ on sys.path
    triage("Your parcel is held, pay the fee here: http://...")
    -> {"tier": "RED", "label": "...", "scam_probability": 0.97, "threshold": 0.94,
        "reasons": [...], "top_words": [...], "model": "..."}

The model, threshold and tier rules come from models/model_shipped.joblib and models/shipped_config.json,
written by `python src/scam_drift.py` (model chosen on validation data only; see docs/RESULTS_DETAIL.md).
Non-English text: the model mainly knows English. A real deployment needs on-device translation first
(UNVERIFIED quality); our non-English numbers use the dataset's English translation as an oracle reference.
This project is a prototype and is not financial advice.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scam_drift import (TIER_LABELS, money_offer_reasons, normalise, occlusion_words, rule_reasons, safety_reasons,
                        triage_tier)  # noqa: E402

DISCLAIMER = "This project is a prototype and is not financial advice."


@lru_cache(maxsize=1)
def _bundle():
    import joblib
    return joblib.load(ROOT / "models" / "model_shipped.joblib")


def triage(text: str) -> dict:
    """Pure function of the text (given the saved model): tier, scam probability, plain-language reasons, top words."""
    b = _bundle()
    text = text if isinstance(text, str) else ""
    norm = normalise(text)
    if not norm:
        return {"tier": "GREEN", "label": TIER_LABELS["GREEN"], "scam_probability": None, "threshold": b["threshold"],
                "reasons": ["The message is empty."], "top_words": [], "model": b["name"], "disclaimer": DISCLAIMER}
    p = float(b["pipeline"].predict_proba([norm])[0, 1])
    th = float(b["threshold"])
    tier = triage_tier(p, th, norm, text)
    reasons = []
    if p >= th:
        reasons.append(f"The model scores this text {p:.2f}, at or above its warning level {th:.2f}.")
    if "tok_url" in norm:
        reasons.append("It contains a web link. Do not tap links in unexpected texts.")
    if "tok_phone" in norm:
        reasons.append("It contains a phone number. Call the official number on your card or bill instead.")
    for r in rule_reasons(text, norm) + money_offer_reasons(text):
        reasons.append("It " + r + ".")
    safety = safety_reasons(text)
    for r in safety:
        reasons.insert(0, "SAFETY: it " + r + ".")
    if tier == "GREEN":
        reasons.append("No warning signs found. This does not prove the message is safe. "
                       "Never share a one-time code, PIN or password.")
    top = [w for w, _ in occlusion_words(b["pipeline"], norm, k=5)]  # words whose removal lowers the score most
    return {"tier": tier, "safety": bool(safety), "label": TIER_LABELS[tier], "scam_probability": round(p, 4), "threshold": th,
            "reasons": reasons, "top_words": top, "model": b["name"], "disclaimer": DISCLAIMER}


if __name__ == "__main__":
    import json
    for t in ["Your package could not be delivered. Update your address here: http://parcel-redelivery-help.com",
              "Hi mum, this is my new number, my phone broke. Can you text me back?",
              "Your First Harbor Bank verification code is 482913. Never share this code with anyone.",
              "Hi, long time no see, how are you doing?"]:
        print(json.dumps(triage(t), indent=1))
