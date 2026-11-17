"""Scam Drift demo: paste a text message, compare the 2012 model with the fixed model.

Run:  python app.py   (then open the local URL Gradio prints)
Needs: models/model_2012.joblib and models/model_fixed.joblib (create them with: python src/scam_drift.py)
This project is a prototype and is not financial advice.
"""
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from scam_drift import explain, normalise  # noqa: E402

M2012 = joblib.load(ROOT / "models" / "model_2012.joblib")
MFIX = joblib.load(ROOT / "models" / "model_fixed.joblib")

EXAMPLES = [
    "Your package could not be delivered due to an incomplete address. Update it here: http://parcel-redelivery-help.com",
    "Your First Harbor Bank verification code is 482913. It expires in 10 minutes. We will never call or text to ask for this code.",
    "Dear customer, your account has been blocked. Please update your KYC details here to avoid suspension: http://kyc-update.in",
    "Hi, long time no see, how are you doing?",
    "Maple Pharmacy: Your prescription is ready for pickup at our Main Street store. Reply STOP to opt out.",
    "WINNER!! You have been selected to receive a £900 prize reward! To claim call 09061701461. Valid 12 hours only.",
]


def score(bundle, norm):
    p = float(bundle["pipeline"].predict_proba([norm])[0, 1])
    return p, p >= bundle["threshold"]


def plain_warning(flag_fixed: bool, flag_2012: bool, has_link: bool) -> str:
    if flag_fixed and flag_2012:
        msg = ("**Stop and check.** Both models think this looks like a scam. Do not tap any link and do not reply. "
               "If it says it is from your bank, a shop or the government, call them using the number on your card, "
               "bill or their official website - not a number in this message.")
    elif flag_fixed or flag_2012:
        msg = ("**Be careful.** One model thinks this looks like a scam. Do not tap a link until you have checked "
               "with the company directly or asked a family member.")
    else:
        msg = ("**No warning signs found by these models.** That does not prove it is safe. "
               "Never share a one-time code, PIN or password with anyone who contacts you.")
    if has_link:
        msg += "\n\nThis message contains a link. Real organisations rarely need you to tap a link to fix a problem."
    msg += ("\n\n_Known weakness: the fixed model also flags many genuine bank, delivery and pharmacy texts "
            "(it was never shown modern genuine messages). Treat a warning as 'check first', not 'this is fraud'._")
    return msg


def predict(text: str):
    """Return (markdown verdict table, plain-language warning, top words markdown)."""
    if not text or not text.strip():
        return "Paste a text message above.", "", ""
    norm = normalise(text)
    p12, f12 = score(M2012, norm)
    pfx, ffx = score(MFIX, norm)
    verdict = (
        "| Model | Scam probability | Threshold | Verdict |\n|---|---|---|---|\n"
        f"| 2012 model (UCI SMS 2012 only) | {p12:.2f} | {M2012['threshold']:.2f} | {'SCAM' if f12 else 'not flagged'} |\n"
        f"| Fixed model (+ 2015-2021 smishing) | {pfx:.2f} | {MFIX['threshold']:.2f} | {'SCAM' if ffx else 'not flagged'} |"
    )
    words = []
    for name, bundle in [("2012 model", M2012), ("Fixed model", MFIX)]:
        top = explain(bundle["pipeline"], norm, k=5)
        shown = ", ".join(f"`{w}` (+{c:.2f})" for w, c in top) if top else "none"
        words.append(f"**{name}** - words pushing toward scam: {shown}")
    words.append(f"\nNormalised text the models see: `{norm}`")
    return verdict, plain_warning(ffx, f12, "tok_url" in norm), "\n\n".join(words)


def build_demo():
    import gradio as gr
    with gr.Blocks(title="Scam Drift") as demo:
        gr.Markdown("# Scam Drift\nPaste a text message. Compare a 2012-era spam filter with a filter "
                    "updated with 2015-2021 smishing reports. This project is a prototype and is not financial advice.")
        inp = gr.Textbox(lines=4, label="Text message")
        btn = gr.Button("Check message", variant="primary")
        out_v = gr.Markdown(); out_w = gr.Markdown(); out_x = gr.Markdown()
        btn.click(predict, inp, [out_v, out_w, out_x])
        gr.Examples(EXAMPLES, inp)
    return demo


if __name__ == "__main__":
    build_demo().launch()
