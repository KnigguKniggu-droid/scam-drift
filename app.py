"""Scam Drift demo (post-deadline v2 (Nov 18)): paste a text message and get a three-tier warning for an older adult.

Run:  python app.py   (then open http://127.0.0.1:7860)
Needs: models/model_shipped.joblib, models/shipped_config.json and models/model_2012.joblib
       (create them with: python src/scam_drift.py)
This project is a prototype and is not financial advice.

The verdict comes from src/triage.py (the shipped model `char_fix_plus_real_ham` at its strict threshold, warn-only):
  RED    = the model flags the text AND it has a link or a phone number -> "Likely scam - don't tap links or reply"
  YELLOW = the model flags with no link/phone, OR a rule fires (asks for a code/PIN/password; "hi mum / new number /
           wrong number" opener)                                       -> "Ask a family member before replying"
  GREEN  = otherwise                                                  -> "No warning signs found" (never "safe")
The middle tier is called YELLOW in the code and in results/metrics.json; on screen it is drawn in amber-orange.
The 2012 filter (models/model_2012.joblib) is shown only as a one-line comparison.

Examples (fixed, not a sample; they show behaviour, they do not measure it - see docs/RESULTS_DETAIL.md):
  1. Real reported scam with a link: IMC25, English, report date 2022-08-05, scam_type "delivery".
  2. Real reported scam with no link or phone number: IMC25, English, report date Feb 8, 2023, scam_type "wrong number".
  3. Synthetic legitimate bank code text from data/benign_twins.csv (written with AI assistance for this project;
     category bank_otp). The shipped model was not trained on any synthetic text.
  4. Real reported scam in French: IMC25, report date 2022-02-25, scam_type "government". The English translation
     is the dataset's own translation (oracle reference); this app does not translate.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from scam_drift import friendly_explain, normalise, rule_reasons  # noqa: E402
from triage import DISCLAIMER, triage  # noqa: E402

M2012 = joblib.load(ROOT / "models" / "model_2012.joblib")

RED, ORANGE, GREEN_TEXT, INK = "#D64545", "#E07A1F", "#2E8B57", "#111111"
FOOTER = "Prototype - not financial advice. Synthetic examples are labelled."

VERDICT = {
    "RED": "Likely scam - don't tap links or reply",
    "YELLOW": "Ask a family member before replying",
    "GREEN": "No warning signs found",
}


def _metric(*path):
    """Read one number from results/metrics.json (None if the file or key is missing)."""
    try:
        node = json.loads((ROOT / "results" / "metrics.json").read_text(encoding="utf-8"))
        for k in path:
            node = node[k]
        return float(node)
    except (OSError, KeyError, TypeError, ValueError):
        return None


_RAW = _metric("v2", "triage", "sets", "scams_nonenglish_raw_text", "share_red_or_yellow", "rate")
_ORACLE = _metric("v2", "triage", "sets", "scams_nonenglish_translation_oracle", "share_red_or_yellow", "rate")
_LANG_NOTE = (f" On real non-English scams, the checker warns on {_RAW:.0%} of raw texts and on {_ORACLE:.0%} "
              "when it reads the dataset's English translation (results/metrics.json)."
              if _RAW is not None and _ORACLE is not None else "")

FRENCH_TRANSLATION = ("Your new health insurance card is available, please fill out the form to continue "
                      "being covered: <URL>")

# (button label, text, note shown under the result)
EXAMPLES = [
    ("Real scam with a link",
     "Please confirm your shipment details, otherwise your item will be sent back to the sender: <URL>",
     "Real reported scam (IMC25 dataset, report date 2022-08-05, delivery type). The dataset authors replaced "
     "links and names with tags such as <URL>."),
    ("Real 'wrong number' scam",
     "Hi, <NAMED_ENTITY>, we talked about the contract last time, we can talk about it later.\n"
     "I just wanted to let you know this is the wrong number.\n"
     "Aren't you <NAMED_ENTITY>? I'm sure I think I added the wrong person.\n"
     "I usually have a lot of business partners, maybe my secretary sent you <NAMED_ENTITY> number, "
     "sorry I hope you don't mind.\n"
     "Acceptance is a lot, I am from <LOCATION>, where are you from?",
     "Real reported scam (IMC25 dataset, report date Feb 8, 2023, 'wrong number' type). It has no link and no "
     "phone number. Names and places were replaced with tags by the dataset authors."),
    ("Synthetic bank code text",
     "Your First Harbor Bank verification code is 482913. It expires in 10 minutes. "
     "We will never call or text to ask for this code.",
     "Synthetic example: a legitimate-style bank code text written with AI assistance for this project. "
     "It is not a scam, and the bank name is made up."),
    ("Real French scam",
     "Ton nouvelle carte vitale est disponible, veuillez remplir le formulaire pour continuer a etre couvert: <URL>",
     "Real reported scam in French (IMC25 dataset, report date 2022-02-25, government type). "
     "The checker mainly knows English." + _LANG_NOTE),
]
_NOTES = {text: note for _, text, note in EXAMPLES}
_TRANSLATIONS = {EXAMPLES[3][1]: FRENCH_TRANSLATION}


def score(bundle, norm):
    """Scam probability and flag for one saved word model on normalised text."""
    p = float(bundle["pipeline"].predict_proba([norm])[0, 1])
    return p, p >= bundle["threshold"]


def reason_sentence(text: str, res: dict) -> str:
    """One plain-language sentence that explains the tier."""
    norm = normalise(text)
    tier = res["tier"]
    p, th = res["scam_probability"], res["threshold"]
    flagged = p is not None and p >= th
    has = [w for w, tok in (("a web link", "tok_url"), ("a phone number", "tok_phone")) if tok in norm]
    rules = rule_reasons(text, norm)
    if tier == "RED":
        return f"The wording looks like reported scams, and the message has {' and '.join(has)}."
    if tier == "YELLOW":
        if rules:
            return "The message " + " and ".join(rules) + "."
        return "The wording looks like reported scams, but there is no link or phone number."
    if p is None:
        return "The message is empty."
    return ("The checker found no warning signs. This does not prove the message is safe: "
            "never share a code, PIN or password.")


def verdict_html(tier: str) -> str:
    if tier == "RED":
        box = f"background:{RED};color:#FFFFFF;border:4px solid {RED};"
        tag = '<div style="font-size:20px;font-weight:700;letter-spacing:.06em;">RED</div>'
    elif tier == "YELLOW":
        box = f"background:{ORANGE};color:{INK};border:4px solid {ORANGE};"
        tag = '<div style="font-size:20px;font-weight:700;letter-spacing:.06em;">YELLOW (amber)</div>'
    else:
        box = f"background:#FFFFFF;color:{INK};border:4px solid #444444;"
        tag = (f'<div style="font-size:20px;font-weight:700;letter-spacing:.06em;color:{GREEN_TEXT};">'
               "GREEN</div>")
    return (f'<div class="sd-verdict" data-tier="{tier}" style="{box}border-radius:14px;padding:22px 24px;">'
            f'{tag}<div style="font-size:36px;line-height:1.2;font-weight:800;margin-top:6px;">'
            f"{html.escape(VERDICT[tier])}</div></div>")


def _p(text: str) -> str:
    return f'<p class="sd-line">{html.escape(text)}</p>'


def predict(text: str):
    """Return (verdict HTML, reason HTML, top words HTML, 2012 comparison HTML, example note HTML)."""
    if not text or not text.strip():
        return (_p("Paste a text message above, then press \"Check this text\"."), "", "", "", "")
    res = triage(text)
    tier = res["tier"]
    reason = _p(reason_sentence(text, res))
    shown = [w.strip(".,:;!?()\"'") for w in res["top_words"]]
    shown = [w for w in dict.fromkeys(shown) if w]
    words = ", ".join(shown) if shown else "none"
    lead = ("Words that raised the warning score most" if tier != "GREEN"
            else "Words that raised the score most (still below the warning level)")
    top = _p(f"{lead}: {words}")
    norm = normalise(text)
    p12, f12 = score(M2012, norm)
    said = "scam" if f12 else "not a scam"
    w12 = friendly_explain(M2012["pipeline"], norm, k=3)
    w12s = f"; its top words: {', '.join(w for w, _ in w12)}" if (f12 and w12) else ""
    cmp12 = (f'<p class="sd-small">2012 filter said: {said} (score {p12:.2f}, its warning level '
             f'{M2012["threshold"]:.2f}){html.escape(w12s)}.</p>')
    note = ""
    if text.strip() in _NOTES:
        note = _NOTES[text.strip()]
        tr = _TRANSLATIONS.get(text.strip())
        if tr:
            tr_tier = triage(tr)["tier"]
            note += (f" The dataset's English translation (oracle reference, not made by this app): \"{tr}\". "
                     f"On that translation the checker says: {tr_tier} - {VERDICT[tr_tier]}.")
        note = f'<p class="sd-small sd-note">{html.escape(note)}</p>'
    return verdict_html(tier), reason, top, cmp12, note


CSS = f"""
:root, .dark {{ color-scheme: light; }}
body, gradio-app, .gradio-container, .dark .gradio-container {{ background:#FFFFFF !important; color:{INK} !important; }}
.gradio-container {{ max-width: 860px !important; margin: 0 auto !important; font-size: 20px; }}
.gradio-container h1 {{ font-size: 40px; color:{INK}; }}
.sd-intro, .sd-intro p {{ font-size: 21px; line-height: 1.45; color:{INK}; }}
.sd-line {{ font-size: 24px; line-height: 1.45; color:{INK}; margin: 6px 0; }}
.sd-small {{ font-size: 18px; line-height: 1.45; color:#333333; margin: 6px 0; }}
.sd-note {{ border-left: 4px solid #666666; padding-left: 12px; }}
.sd-footer, .sd-footer p {{ font-size: 18px; color:#333333; border-top: 2px solid #DDDDDD; padding-top: 10px; }}
#sd-input textarea {{ font-size: 22px !important; line-height: 1.4; background:#FFFFFF !important; color:{INK} !important;
                      border: 2px solid #444444 !important; }}
#sd-input label span {{ font-size: 20px !important; color:{INK} !important; }}
#sd-check {{ font-size: 26px !important; min-height: 64px; background:{INK} !important; color:#FFFFFF !important;
             border: none !important; }}
.sd-ex button, button.sd-ex {{ font-size: 19px !important; min-height: 54px; background:#FFFFFF !important;
             color:{INK} !important; border: 2px solid #444444 !important; }}
"""

# Force the light look even when the viewer's system prefers dark mode (design rule: white background).
JS = "() => { document.body.classList.remove('dark'); }"


def build_demo():
    import gradio as gr
    with gr.Blocks(title="Scam Drift") as demo:
        gr.Markdown("# Scam Drift\nPaste a text message you are unsure about, then press **Check this text**. "
                    f"The checker only warns; it never blocks a message. {DISCLAIMER}",
                    elem_classes="sd-intro")
        inp = gr.Textbox(lines=5, label="Text message", placeholder="Paste the text message here",
                         elem_id="sd-input")
        btn = gr.Button("Check this text", variant="primary", elem_id="sd-check")
        gr.Markdown("**Or try an example:**", elem_classes="sd-intro")
        with gr.Row():
            ex_btns = [gr.Button(label, elem_classes="sd-ex") for label, _, _ in EXAMPLES]
        out_v = gr.HTML()
        out_r = gr.HTML()
        out_w = gr.HTML()
        out_c = gr.HTML()
        out_n = gr.HTML()
        outs = [out_v, out_r, out_w, out_c, out_n]
        btn.click(predict, inp, outs)
        inp.submit(predict, inp, outs)
        for b, (_, text, _) in zip(ex_btns, EXAMPLES):
            b.click(lambda t=text: t, None, inp).then(predict, inp, outs)
        gr.Markdown(FOOTER, elem_classes="sd-footer")
    return demo


def launch_kwargs() -> dict:
    """Styling arguments (Gradio 6 takes css/js/theme in launch(), not in Blocks())."""
    import gradio as gr
    return {"css": CSS, "js": JS, "theme": gr.themes.Default()}


if __name__ == "__main__":
    build_demo().launch(server_name="127.0.0.1", server_port=7860, **launch_kwargs())
