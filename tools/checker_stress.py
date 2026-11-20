"""Web checker regression suite and optional corpus comparison. Prints counts and timings only.

Run python tools/checker_stress.py [--corpus] [--url http://127.0.0.1:8000].
The transport tests use FastAPI in-process. --url tests concurrent requests over HTTP.
--corpus reruns historical test splits without training or writing result files.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import MAX_BODY_BYTES, MAX_CHARS, api, sd  # noqa: E402
from scam_drift import normalise, step_load_and_split, step_v2_data, triage_tier  # noqa: E402
from triage import _bundle  # noqa: E402
from web_triage import VERSION, assess  # noqa: E402

PRIVATE = "LOCAL_TEST_SECRET_VAL"
SCENARIOS = [
    ("gift-card", "Please buy three gift cards and send me a picture of the codes.", "YELLOW", "gift_card"),
    ("job-upfront", "You must buy the equipment from our vendor before your first day.", "YELLOW", "job_fee"),
    ("rental-deposit", "Wire the deposit before you see the apartment.", "YELLOW", "rental_deposit"),
    ("wire-payment", "Please send your payment by wire transfer.", "YELLOW", "payment_method"),
    ("qr-parking", "Scan the QR code to pay the parking fee.", "YELLOW", "qr_payment"),
    ("credential", "Please reply with your verification code.", "YELLOW", "credential"),
    ("credential-link", "Send me your password using https://domain.example", "RED", "credential"),
    ("account-update", "Tap this link to verify your account: https://domain.example", "RED", "account_link"),
    ("urgent-payment", "Pay me now or I will call again.", "YELLOW", "fee_pressure"),
    ("new-family-number", "Hi mum, this is my new phone number. Save it.", "YELLOW", "new_number"),
    ("invest-guarantee", "We offer guaranteed returns on this investment.", "YELLOW", "investment"),
    ("luring", "I'll give you $50 if you come to my car. Don't tell your parents.", "RED", "luring"),
    ("isolating-question", "Are you home alone tonight?", "YELLOW", "personal_safety"),
    ("private-image", "Send me private photos of yourself.", "YELLOW", "personal_safety"),
    ("es-payment-link", "Pague la multa ahora para evitar una sanción: https://domain.example", "RED", "foreign_link"),
    ("fr-form-link", "Veuillez remplir le formulaire pour renouveler votre carte: https://domain.example", "RED", "foreign_link"),
    ("pt-request-link", "Pague agora esta taxa para receber sua encomenda: https://domain.example", "RED", "foreign_link"),
    ("private-ride-birthday", "Happy birthday! I will give you a gift card and drive you home afterwards.", "GREEN", ""),
    ("family-lunch", "I will buy you lunch and pick you up after school.", "GREEN", ""),
    ("normal-delivery", "Your parcel was delivered to your front porch. No action is needed.", "GREEN", ""),
    ("no-code-share", "For your security, never share your verification code.", "GREEN", ""),
    ("doctor-appointment", "We moved your appointment to Thursday afternoon. See you then!", "GREEN", ""),
    ("quiet-payment", "I paid the rent this morning. The receipt is in my email.", "GREEN", ""),
    ("legit-code", sd.EXAMPLES[2][1], "GREEN", ""),
    ("only-link", "https://domain.example", "YELLOW", ""),
    ("just-emoji", "📦💰‼️", "YELLOW", ""),
    ("just-greeting", "Hi", "YELLOW", ""),
    ("arabic", "هذا نص عربي يرجى التحقق من الرسالة", "YELLOW", ""),
    ("hindi", "आपका पार्सल आज घर नहीं पहुंचा", "YELLOW", ""),
    ("chinese", "这条短信需要独立核实", "YELLOW", ""),
]
SHAPES = {
    "original": lambda s: s,
    "uppercase": str.upper,
    "wide-ascii": lambda s: s.translate({code: code + 0xFEE0 for code in range(33, 127)}),
    "zero-width": lambda s: s[:2] + "\u200b" + s[2:],
    "padded": lambda s: " \r\n " + s + " \t",
}


def valid(data):
    assert data["version"] == VERSION
    assert data["tier"] in {"RED", "YELLOW", "GREEN", None}
    assert isinstance(data["signals"], list)
    assert all(set(s) == {"id", "label", "phrase"} for s in data["signals"])
    assert isinstance(data["actions"], list)
    if data["tier"]:
        assert data["actions"] and data["headline"] and data["reason"]
    assert data["headline"].strip().lower() != "safe"


def long_text():
    words = ("".join(letters) for letters in itertools.product("abcdefgh", repeat=5))
    return " ".join(itertools.islice(words, 4000))[:MAX_CHARS]


def test_requests(client):
    failures = []
    for scenario, text, tier, signal in SCENARIOS:
        for shape, convert in SHAPES.items():
            response = client.post("/api/check", json={"text": convert(text)})
            result = response.json()
            if response.status_code != 200 or result.get("tier") != tier or (
                    signal and signal not in {s["id"] for s in result.get("signals", [])}):
                failures.append({"name": scenario, "shape": shape, "wanted": tier,
                                 "seen": result.get("tier"), "status": response.status_code,
                                 "signals": [s["id"] for s in result.get("signals", [])]})
            else:
                valid(result)

    invalid = [
        ("broken-json", b'{"text":"' + PRIVATE.encode() + b'"', "application/json", 400),
        ("duplicate-property", b'{"text":"first","text":"second"}', "application/json", 400),
        ("invalid-utf8", b'{"text":"\xff"}', "application/json", 400),
        ("unpaired-utf16", br'{"text":"\ud800"}', "application/json", 422),
        ("oversized-decoded", json.dumps({"text": PRIVATE * (MAX_CHARS // len(PRIVATE) + 1)}).encode(),
         "application/json", 422),
        ("oversized-body", b'x' * (MAX_BODY_BYTES + 1), "application/json", 413),
        ("wrong-type", json.dumps({"text": {"note": PRIVATE}}).encode(), "application/json", 422),
        ("extra-field", b'{"text":"x","extra":3}', "application/json", 422),
        ("array", b'[]', "application/json", 422),
        ("form-data", PRIVATE.encode(), "text/plain", 415),
        ("nesting", b'[' * 50 + b']' * 50, "application/json", 422),
    ]
    for name, raw, content_type, status in invalid:
        result = client.post("/api/check", content=raw, headers={"Content-Type": content_type})
        assert result.status_code == status, (name, result.status_code)
        assert PRIVATE not in result.text and len(result.content) < 150, name
        assert result.headers["cache-control"] == "no-store", name

    streamed = client.post("/api/check", content=(b"x" * 65537 for _ in range(4)),
                           headers={"Content-Type": "application/json"})
    assert streamed.status_code == 413
    valid_count = 0
    for text in ("", "\t\r\n", "🧾" * MAX_CHARS, "<URL>", "\x00", "constructor", long_text()):
        response = client.post("/api/check", json={"text": text})
        assert response.status_code == 200, response.status_code
        valid(response.json())
        valid_count += 1
    assert client.get("/api/story").status_code == 200
    assert client.get("/api/examples").status_code == 200
    elapsed = time.perf_counter()
    response = client.post("/api/check", json={"text": long_text()})
    long_ms = (time.perf_counter() - elapsed) * 1000
    assert response.status_code == 200
    report = {"targeted": len(SCENARIOS) * len(SHAPES), "transport_and_edges": len(invalid) + 1 + valid_count,
              "max_length_in_process_ms": round(long_ms, 1), "targeted_failures": failures}
    return report


def http_load(url):
    url = url.rstrip("/") + "/api/check"
    payload = [json.dumps({"text": case[1]}).encode() for case in SCENARIOS]
    expected = [case[2] for case in SCENARIOS]
    payload.append(json.dumps({"text": long_text()}).encode())
    expected.append("YELLOW")
    count = 512
    def send(index):
        slot = index % len(payload)
        request = Request(url, data=payload[slot], headers={"Content-Type": "application/json"})
        start = time.perf_counter()
        with urlopen(request, timeout=8) as response:
            data = json.load(response)
            assert response.status == 200
        valid(data)
        if slot < len(SCENARIOS):
            assert data["tier"] == expected[slot], (index, slot, data["tier"])
        return (time.perf_counter() - start) * 1000
    with ThreadPoolExecutor(max_workers=8) as pool:
        times = sorted(pool.map(send, range(count)))
    return {"requests": count, "success": len(times), "workers": 8, "p50_ms": round(statistics.median(times), 1),
            "p95_ms": round(times[int(.95 * len(times)) - 1], 1), "max_ms": round(max(times), 1)}


def corpus():
    d = step_load_and_split()
    split, _ = step_v2_data(d)
    datasets = {
        "dated_english_reports": d["late"],
        "dated_english_cluster_safe": split["late_safe"],
        "other_language_reports": d["nonen"],
        "held_out_india_business_legitimate": split["ind_te"],
        "mozambique_legitimate": split["moz"],
        "uci_2012_legitimate": d["uci_te"][d["uci_te"]["label"] == 0],
        "uci_2012_spam": d["uci_te"][d["uci_te"]["label"] == 1],
        "synthetic_legitimate": split["syn_te"],
        "synthetic_scam": split["syn_scam"],
    }
    bundle = _bundle()
    output = {}
    for name, frame in datasets.items():
        texts = frame["text"].tolist()
        norms = [normalise(raw) for raw in texts]
        probs = bundle["pipeline"].predict_proba(norms)[:, 1]
        legacy = collections.Counter(triage_tier(p, bundle["threshold"], n, raw)
                                     for p, n, raw in zip(probs, norms, texts))
        upgraded = collections.Counter()
        unknown = 0
        for raw in texts:
            score = assess(raw, explain=False)
            upgraded[score["tier"]] += 1
            unknown += bool(score["uncertain"])
        output[name] = {"n": len(texts), "v3_warned": legacy["RED"] + legacy["YELLOW"],
                        f"{VERSION}_warned": upgraded["RED"] + upgraded["YELLOW"], f"{VERSION}_red": upgraded["RED"],
                        f"{VERSION}_uncertain_subset": unknown}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", action="store_true")
    parser.add_argument("--url")
    args = parser.parse_args()
    with TestClient(api, raise_server_exceptions=False) as client:
        report = test_requests(client)
    print(json.dumps(report, indent=2), flush=True)
    if report["targeted_failures"]:
        return 1
    if args.url:
        print(json.dumps({"http_load": http_load(args.url)}, indent=2), flush=True)
    if args.corpus:
        print(json.dumps({"corpus": corpus()}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
