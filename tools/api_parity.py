"""Regression gate for the original demo and the revised FastAPI API.

The two interfaces intentionally have different warning policies. This verifies
the original demo against its original triage and checks the live API contract.
It prints only aggregate counts and fixture IDs.
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

import server  # noqa: E402
from scam_drift import IMC_PATH, _read_text  # noqa: E402
from triage import triage  # noqa: E402
from web_triage import VERSION  # noqa: E402


def original_cases():
    out = [(label, text) for label, text, _ in server.sd.EXAMPLES] + [("empty", "")]
    reported = pd.read_csv(io.StringIO(_read_text(IMC_PATH))).dropna(subset=["text"])
    reported = reported[reported["text"].str.strip().str.len() > 0]
    out += [(f"report:{i}", str(row.text)) for i, row in reported.sample(25, random_state=42).iterrows()]
    twins = pd.read_csv(ROOT / "data" / "benign_twins.csv")
    out += [(f"twin:{i}", str(row.text)) for i, row in twins.sample(25, random_state=42).iterrows()]
    return out


def main():
    original = original_cases()
    for name, text in original:
        match = re.search(r'data-tier="(\w+)"', server.sd.predict(text)[0] or "")
        seen = match.group(1) if match else None
        expected = triage(text)["tier"] if text.strip() else None
        assert seen == expected, (name, seen, expected)

    with TestClient(server.api) as client:
        response = client.get("/api/examples")
        assert response.status_code == 200
        examples = response.json()
        assert [ex["text"] for ex in examples] == [t for _, t, _ in server.sd.EXAMPLES]
        assert [ex["kind"] for ex in examples] == ["REAL", "REAL", "SYNTHETIC", "REAL"]
        for example, tier in zip(examples, ["RED", "YELLOW", "GREEN", "RED"], strict=True):
            response = client.post("/api/check", json={"text": example["text"]})
            assert response.status_code == 200, (example["id"], response.status_code)
            data = response.json()
            assert data["tier"] == tier and data["version"] == VERSION, (example["id"], data["tier"])
            assert data["actions"] and "no-store" in response.headers["Cache-Control"]
        body = client.get("/api/story").json()
        assert body["numbers"] and not body["missing"]
        assert client.post("/api/check", json={"text": ""}).json()["tier"] is None
    print(json.dumps({"original_demo_matches": len(original), "web_example_fixtures": len(examples),
                      "story_endpoint": "passed", "web_policy": VERSION}, indent=2))


if __name__ == "__main__":
    main()
