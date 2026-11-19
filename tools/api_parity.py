"""API parity test (UI_PLAN.md phase B gate): POST /api/check must give the same tier as app.predict.

Usage: python tools/api_parity.py
Texts: the 4 fixed demo examples + an empty input + 50 seeded texts (seed 42): 25 IMC25 reported scams (public
dataset, any language) and 25 rows of data/benign_twins.csv (SYNTHETIC, written with AI assistance; legit and scam
twins). India/MOZ texts are never used or printed. Runs in-process with FastAPI's TestClient (no server needed).
Also checks that label / headline / actions / reason come from the same app.py tables and helpers.
Also checks translation_note (note only, tier unchanged) on emoji-only, one-letter and example texts.
Writes qa/api_parity.json (per-text tiers, no message text) and exits 1 on any mismatch.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import app  # noqa: E402
import server  # noqa: E402
from scam_drift import IMC_PATH, _read_text  # noqa: E402
from triage import triage  # noqa: E402

SEED = 42


def predict_tier(text: str):
    m = re.search(r'data-tier="(\w+)"', app.predict(text)[0] or "")
    return m.group(1) if m else None


def texts():
    out = [("example:" + label, t) for label, t, _ in app.EXAMPLES] + [("empty", "")]
    imc = pd.read_csv(io.StringIO(_read_text(IMC_PATH)))
    imc = imc[imc["text"].notna() & (imc["text"].str.strip().str.len() > 0)]
    for i, r in imc.sample(25, random_state=SEED).iterrows():
        out.append((f"imc25:{i}:{r.get('language', '?')}", str(r["text"])))
    bt = pd.read_csv(ROOT / "data" / "benign_twins.csv")
    for i, r in bt.sample(25, random_state=SEED).iterrows():
        out.append((f"synthetic_twin:{i}:label{r['label']}:{r['category']}", str(r["text"])))
    return out


def main():
    client = TestClient(server.api)
    rows, bad = [], []
    for name, text in texts():
        resp = client.post("/api/check", json={"text": text})
        assert resp.status_code == 200, (name, resp.status_code)
        d = resp.json()
        want = predict_tier(text)
        ok = d["tier"] == want
        if want is not None:
            res = triage(text)
            ok = ok and d["label"] == app.LABEL[want] and d["headline"] == app.VERDICT[want] \
                and d["actions"] == app.ACTIONS[want] and d["reason"] == app.reason_sentence(text, res)
        rows.append({"id": name, "api_tier": d["tier"], "predict_tier": want, "ok": ok})
        if not ok:
            bad.append(rows[-1])
    # Note-only checks: translation_note warns on unreadable or non-English input and never changes the tier.
    note_cases = [("emoji_only", "😀🎁📦💰👉", True),
                  ("single_letter", "a", True),
                  ("example_french", app.EXAMPLES[3][1], True),
                  ("example_link_english", app.EXAMPLES[0][1], False),
                  ("example_bank_code_english", app.EXAMPLES[2][1], False)]
    notes = []
    for name, text, want_note in note_cases:
        d = client.post("/api/check", json={"text": text}).json()
        ok = d["tier"] == predict_tier(text) and bool(d["translation_note"]) == want_note
        if name == "example_french":
            ok = ok and "High risk" in d.get("translation_detail", "")
        notes.append({"id": name, "tier": d["tier"], "has_note": bool(d["translation_note"]), "ok": ok})
    notes_ok = all(n["ok"] for n in notes)
    ex = client.get("/api/examples").json()
    ex_ok = [e["text"] for e in ex] == [t for _, t, _ in app.EXAMPLES] and \
        [e["kind"] for e in ex] == ["REAL", "REAL", "SYNTHETIC", "REAL"]
    st = client.get("/api/story").json()
    story_ok = not st["missing"] and len(st["numbers"]) > 0
    tiers = {}
    for r in rows:
        tiers[str(r["api_tier"])] = tiers.get(str(r["api_tier"]), 0) + 1
    summary = {"n_texts": len(rows), "n_match": len(rows) - len(bad), "mismatches": bad, "tier_counts": tiers,
               "note_checks": notes, "note_checks_ok": notes_ok,
               "examples_endpoint_ok": ex_ok, "story_endpoint_ok": story_ok,
               "example_tiers": {r["id"]: r["api_tier"] for r in rows if r["id"].startswith("example:")}}
    (ROOT / "qa").mkdir(exist_ok=True)
    (ROOT / "qa" / "api_parity.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1),
                                                 encoding="utf-8")
    print(json.dumps(summary, indent=1))
    sys.exit(0 if (not bad and ex_ok and story_ok and notes_ok) else 1)


if __name__ == "__main__":
    main()
