"""Replay the reported portfolio message and synthetic finance controls against the FastAPI checker."""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from context_model import load_context_model  # noqa: E402
from scam_drift import normalise  # noqa: E402
from triage import _bundle  # noqa: E402
from web_triage import _canonical  # noqa: E402

REPORTED = (
    "Year-End Portfolio Rebalancing & K-1 Distribution SummaryHi [First Name],Ahead of the upcoming fiscal close, "
    "our tax advisory desk has prepared your preliminary capital gains summary and tax-loss harvesting allocations "
    "for review\\.Because certain equity positions triggered wash-sale thresholds this quarter, we require your digital "
    "sign-off on the adjusted cost-basis election before we finalize your custodial reporting. You can review the itemized "
    "breakdown and submit your election through our encrypted document center: [example.com]Please let us know if you "
    "would like to schedule a brief call with your portfolio strategist before the filing deadline.Warm regards, &#x20;"
)
RENDERED = (REPORTED.replace("SummaryHi", "Summary\n\nHi").replace(",Ahead", ",\n\nAhead")
            .replace("\\.Because", ".\n\nBecause").replace("]Please", "]\n\nPlease")
            .replace("deadline.Warm", "deadline.\n\nWarm").removesuffix("&#x20;"))

# Reserved example domains and non-clickable placeholders keep every fixture inert.
# The synthetic positive label means a request warrants verification in this fixture.
# It is not a claim about the sender or about all real messages with similar wording.
CASES = (
    ("reported-literal", "warn", REPORTED),
    ("reported-rendered", "warn", RENDERED),
    ("reported-without-demo-url", "warn", RENDERED.replace("[example.com]", "[link]")),
    ("reported-no-visible-url", "warn", RENDERED.replace(": [example.com]", ".")),
    ("reported-https", "warn", RENDERED.replace("[example.com]", "https://documents.example.test")),
    ("tax-election-external", "warn", "A change to your tax election needs a signature. Review it at https://documents.example.test."),
    ("tax-election-short", "warn", "Your cost-basis election is ready for digital sign-off in the document center: documents.example.test."),
    ("tax-form-sensitive-reply", "warn", "Your K-1 needs an amendment. Please reply with your taxpayer ID and routing details."),
    ("tax-refund-portal", "warn", "A tax refund remains unclaimed. Enter your bank details at https://documents.example.test to release it."),
    ("custody-signature", "warn", "Your custodian requires a signature before the transfer can proceed. Approve it at documents.example.test."),
    ("wire-change", "warn", "Our bank changed this morning. Send your payment by wire transfer and confirm by replying."),
    ("broker-code", "warn", "To confirm the brokerage transfer, please reply with your verification code."),
    ("invoice-change", "warn", "Please confirm our updated bank details before remitting tomorrow's invoice. Call the new number in the attachment."),
    ("no-action-tax-form", "green", "Your K-1 is posted in the brokerage app you already use. This is for your records. No action is required."),
    ("tax-election-in-app", "green", "You asked me to check your cost-basis election. It's in the Documents tab of the app. We can discuss it on our scheduled call."),
    ("tax-meeting", "green", "Hi, are we still meeting Tuesday to review last year's capital gains and loss harvesting?"),
    ("custodian-confirmation", "green", "Your annual custodian report has been generated. Keep it for your records. No signature is needed."),
    ("existing-tax-portal", "green", "Your accountant uploaded the draft to the client portal you already know. Open it from your saved bookmark."),
    ("tax-form-negation", "green", "We will never ask for your taxpayer ID or password by text. Open your usual tax app for your documents."),
    ("payroll-posted", "green", "Your payroll statement is available in the employee app. This notice does not require a reply."),
    ("invoice-paid", "green", "I paid the invoice yesterday. Accounting confirmed that the payment arrived this morning."),
    ("bank-change-warning", "green", "Never pay an invoice using new bank details from a text. Call us on your saved number if you need help."),
    ("investment-report", "green", "We discussed a capital loss on our call. The statement is now available in your usual account."),
    ("linkless-reminder", "green", "Just a reminder that we have a meeting next week about the year-end portfolio review."),
    ("trusted-broker-navigation", "green", "Open the brokerage app you already installed. Go to Statements, then download your K-1 if you need it."),
)


def check(url: str, text: str) -> dict:
    payload = json.dumps({"text": text}).encode("utf-8")
    request = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8174")
    args = parser.parse_args()
    url = args.url.rstrip("/") + "/api/check"
    results = []
    for name, expected, text in CASES:
        result = check(url, text)
        tier = result["tier"]
        found = "green" if tier == "GREEN" else "warn" if tier in {"RED", "YELLOW"} else "invalid"
        results.append({"id": name, "expected": expected, "tier": tier, "pass": found == expected,
                        "signals": [signal["id"] for signal in result["signals"]], "engine": result["context_model"]})

    # Scores below are from the local artifacts. They explain the lexical gate without exposing messages.
    bundle = _bundle()
    model = load_context_model()
    norms = [normalise(_canonical(text)) for _, _, text in CASES[:5]]
    probabilities = bundle["pipeline"].predict_proba(norms)[:, 1]
    logits = model.scores(norms) if model else [None] * len(norms)
    diagnostics = [
        {"id": case[0], "recognized_link": "tok_url" in norm, "lexical_score": round(float(score), 4),
         "neural_logit": round(float(logit), 4) if logit is not None else None}
        for case, norm, score, logit in zip(CASES, norms, probabilities, logits)
    ]
    counts = collections.Counter((item["expected"], item["pass"]) for item in results)
    print(json.dumps({"report": {"warning_cases": counts["warn", True] + counts["warn", False],
                                  "missed_warnings": counts["warn", False],
                                  "legitimate_controls": counts["green", True] + counts["green", False],
                                  "false_alarms": counts["green", False]},
                      "cases": results, "local_reported_diagnostics": diagnostics,
                      "local_lexical_threshold": bundle["threshold"],
                      "local_neural_logit_threshold": model.threshold if model else None}, indent=2))
    return 0 if all(item["pass"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
