"""Scam Drift demo: paste a text message and get a three-tier warning for an older adult.

Run:  python app.py   (then open the local URL Gradio prints)
Needs: models/model_2012.joblib and models/model_fixed.joblib (create them with: python src/scam_drift.py)
This project is a prototype and is not financial advice.

Verdict (post-hoc design, warn-only; results/metrics.json -> "triage" measured the link-only rule, the phone rule is not measured):
  RED    = Model 2012 flags the text AND it contains a link or a phone number (tok_url / tok_phone)
  YELLOW = Model 2012 flags the text, no link and no phone number
  GREEN  = Model 2012 does not flag it ("No warning signs found", never "safe")
The fixed model (2012 data + 2015-2021 scams) is shown only as a second opinion, because it flags almost
every genuine-style test text (59 of 60 benign twins).
"""
import csv
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from scam_drift import friendly_explain, normalise, triage  # noqa: E402

M2012 = joblib.load(ROOT / "models" / "model_2012.joblib")
MFIX = joblib.load(ROOT / "models" / "model_fixed.joblib")

EXAMPLES = [
    "Your package could not be delivered due to an incomplete address. Update it here: http://parcel-redelivery-help.com",
    "Your First Harbor Bank verification code is 482913. It expires in 10 minutes. We will never call or text to ask for this code.",
    "Hi, long time no see, how are you doing?",
    "Maple Pharmacy: Your prescription is ready for pickup at our Main Street store. Reply STOP to opt out.",
]
# Real 2022+ test scams picked by a fixed rule in src/scam_drift.py (results/demo_examples.csv), not hand-picked.
_DEMO = ROOT / "results" / "demo_examples.csv"
if _DEMO.exists():
    with _DEMO.open(encoding="utf-8") as f:
        EXAMPLES = [r["text"] for r in csv.DictReader(f) if r["true_label"] == "scam"] + EXAMPLES

TIER_TEXT = {
    "RED": ("**RED - Likely scam - do not tap links or reply.**\n\n"
            "If it says it is from your bank, a shop or the government, call them on the number on your card, "
            "bill or their official website - not a number in this message."),
    "YELLOW": ("**YELLOW - Ask a family member before replying.**\n\n"
               "This message has words that scams often use. Never share a one-time code, PIN or password."),
    "GREEN": ("**GREEN - No warning signs found.** This does not prove the message is safe. "
              "Never share a one-time code, PIN or password with anyone who contacts you."),
}


def score(bundle, norm):
    p = float(bundle["pipeline"].predict_proba([norm])[0, 1])
    return p, p >= bundle["threshold"]


def words(bundle, norm, k=5):
    top = friendly_explain(bundle["pipeline"], norm, k=k)
    return ", ".join(w for w, _ in top) if top else "none"


def predict(text: str):
    """Return (tier verdict markdown, details markdown, top words markdown)."""
    if not text or not text.strip():
        return "Paste a text message above.", "", ""
    norm = normalise(text)
    p12, f12 = score(M2012, norm)
    pfx, ffx = score(MFIX, norm)
    tier = triage(p12, M2012["threshold"], ("tok_url" in norm) or ("tok_phone" in norm))
    verdict = TIER_TEXT[tier]
    second = ("The updated model (with 2015-2021 scams) also flags this message. "
              "Note: it flags almost all genuine bank, delivery and pharmacy texts too, so treat it as a weak signal."
              if ffx else "The updated model (with 2015-2021 scams) does not flag this message.")
    details = (
        "| Model | Scam probability | Threshold | Flag |\n|---|---|---|---|\n"
        f"| 2012 model (decides the colour) | {p12:.2f} | {M2012['threshold']:.2f} | {'yes' if f12 else 'no'} |\n"
        f"| Updated model (second opinion) | {pfx:.2f} | {MFIX['threshold']:.2f} | {'yes' if ffx else 'no'} |\n\n"
        + second + "\n\n_Prototype - not financial advice._")
    expl = (f"**Words that pushed the 2012 model toward 'scam':** {words(M2012, norm)}\n\n"
            f"**Words that pushed the updated model toward 'scam':** {words(MFIX, norm)}")
    return verdict, details, expl


def build_demo():
    import gradio as gr
    with gr.Blocks(title="Scam Drift") as demo:
        gr.Markdown("# Scam Drift\nPaste a text message you are unsure about. You get a RED / YELLOW / GREEN "
                    "warning and the words behind it.\n\n_This project is a prototype and is not financial advice. "
                    "The first two examples are real reported scams (anonymised by the dataset authors); "
                    "the others were written for this project._")
        inp = gr.Textbox(lines=4, label="Text message")
        btn = gr.Button("Check this text", variant="primary")
        out_v = gr.Markdown(); out_d = gr.Markdown(); out_x = gr.Markdown()
        btn.click(predict, inp, [out_v, out_d, out_x])
        gr.Examples(EXAMPLES, inp)
    return demo


if __name__ == "__main__":
    build_demo().launch()
