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

RED, ORANGE, GREEN_TEXT, INK = "#B93333", "#E07A1F", "#2E8B57", "#111111"
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
    ("REAL scam with a link",
     "Please confirm your shipment details, otherwise your item will be sent back to the sender: <URL>",
     "Real reported scam (IMC25 dataset, report date 2022-08-05, delivery type). The dataset authors replaced "
     "links and names with tags such as <URL>."),
    ("REAL 'wrong number' scam",
     "Hi, <NAMED_ENTITY>, we talked about the contract last time, we can talk about it later.\n"
     "I just wanted to let you know this is the wrong number.\n"
     "Aren't you <NAMED_ENTITY>? I'm sure I think I added the wrong person.\n"
     "I usually have a lot of business partners, maybe my secretary sent you <NAMED_ENTITY> number, "
     "sorry I hope you don't mind.\n"
     "Acceptance is a lot, I am from <LOCATION>, where are you from?",
     "Real reported scam (IMC25 dataset, report date Feb 8, 2023, 'wrong number' type). It has no link and no "
     "phone number. Names and places were replaced with tags by the dataset authors."),
    ("SYNTHETIC bank code text",
     "Your First Harbor Bank verification code is 482913. It expires in 10 minutes. "
     "We will never call or text to ask for this code.",
     "Synthetic example: a legitimate-style bank code text written with AI assistance for this project. "
     "It is not a scam, and the bank name is made up."),
    ("REAL scam in French",
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


LABEL = {"RED": "High risk", "YELLOW": "Be careful", "GREEN": "No warning signs"}
ICON = {"RED": "!", "YELLOW": "?", "GREEN": "i"}
ACTIONS = {
    "RED": ["Do not tap the link and do not reply.",
            "Do not pay, and never share a code, PIN or password.",
            "Call the company on a number you already trust (the back of your card or its official website).",
            "Delete the text. In the US you can forward scam texts to 7726 (SPAM)."],
    "YELLOW": ["Do not send money, gift cards or codes yet.",
               "Ask a family member or a friend before you reply.",
               "Contact the person or company another way, on a number you already know."],
    "GREEN": ["The checker found no warning signs, but this does not prove the text is safe.",
              "Never share a code, PIN or password, even with someone who says they are your bank.",
              "If the text asks for money, check with family first."],
}


def verdict_html(tier: str) -> str:
    """Verdict card: tier, plain-language headline and money-safety steps (announced to screen readers)."""
    steps = "".join(f"<li>{html.escape(a)}</li>" for a in ACTIONS[tier])
    return (f'<div class="sd-verdict sd-{tier.lower()}" data-tier="{tier}" role="status" aria-live="polite">'
            f'<div class="sd-vhead"><span class="sd-icon" aria-hidden="true">{ICON[tier]}</span>'
            f'<div><div class="sd-tier">{tier} &middot; {LABEL[tier]}</div>'
            f'<div class="sd-headline">{html.escape(VERDICT[tier])}</div></div></div>'
            f'<div class="sd-actions"><div class="sd-actions-title">What to do now</div><ol>{steps}</ol></div>'
            "</div>")


def _p(text: str) -> str:
    return f'<p class="sd-line">{html.escape(text)}</p>'


def predict(text: str):
    """Return (verdict HTML, reason HTML, top words HTML, 2012 comparison HTML, example note HTML)."""
    if not text or not text.strip():
        return (_p("Paste a text message above, then press \"Check this text\"."), "", "", "", "")
    res = triage(text)
    tier = res["tier"]
    reason = f'<div class="sd-reason"><span class="sd-why-title">Why:</span> {html.escape(reason_sentence(text, res))}</div>'
    shown = [w.strip(".,:;!?()\"'") for w in res["top_words"]]
    shown = [w for w in dict.fromkeys(shown) if w]
    lead = ("Words that raised the warning score most" if tier != "GREEN"
            else "Words that raised the score most (still below the warning level)")
    chips = "".join(f'<span class="sd-chip">{html.escape(w)}</span>' for w in shown) or "none"
    top = f'<div class="sd-why"><div class="sd-why-title">{html.escape(lead)}</div><div>{chips}</div></div>'
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
body, gradio-app, .gradio-container, .dark .gradio-container {{ background:#F6F7F9 !important; color:{INK} !important; }}
.gradio-container {{ max-width: 880px !important; margin: 0 auto !important; font-size: 20px; padding: 0 16px !important; }}
.sd-card {{ background:#FFFFFF; border:1px solid #D9DCE1; border-radius:16px; padding:20px 22px !important; }}
/* header */
.sd-hero h1 {{ font-size: 40px; line-height:1.15; margin: 18px 0 6px; color:{INK}; }}
.sd-hero .sd-sub {{ font-size: 23px; line-height:1.4; margin: 0 0 12px; color:#2B2F36; }}
.sd-badges {{ display:flex; flex-wrap:wrap; gap:8px; margin: 4px 0 6px; }}
.sd-badge {{ font-size:16px; font-weight:600; padding:6px 12px; border-radius:999px; background:#E9EEF6; color:#1F2A3C; }}
.sd-step {{ font-size: 21px; font-weight: 700; color:{INK}; margin: 6px 0 2px; }}
.sd-intro, .sd-intro p {{ font-size: 20px; line-height: 1.45; color:{INK}; }}
/* input + button */
#sd-input textarea {{ font-size: 22px !important; line-height: 1.45; background:#FFFFFF !important; color:{INK} !important;
                      border: 2px solid #3B4048 !important; border-radius: 12px !important; }}
#sd-input label span {{ font-size: 20px !important; color:{INK} !important; }}
#sd-check {{ font-size: 26px !important; min-height: 64px; background:#1F4FD1 !important; color:#FFFFFF !important;
             border: none !important; border-radius: 12px !important; }}
#sd-check:hover {{ background:#163C9E !important; }}
/* examples */
.sd-ex-row {{ display:grid !important; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }}
.sd-ex button, button.sd-ex {{ font-size: 19px !important; min-height: 58px; background:#FFFFFF !important;
             color:{INK} !important; border: 2px solid #3B4048 !important; border-radius: 12px !important;
             white-space: normal !important; }}
.sd-ex:hover, .sd-ex button:hover {{ background:#EEF2F8 !important; }}
button:focus-visible, textarea:focus-visible {{ outline: 4px solid #1F4FD1 !important; outline-offset: 2px; }}
/* verdict */
.sd-verdict {{ border-radius:16px; padding:22px 24px; margin-top: 8px; }}
.sd-verdict, .sd-verdict * {{ color: inherit !important; }}
.sd-red {{ background:{RED}; color:#FFFFFF !important; }}
.sd-yellow {{ background:{ORANGE}; color:{INK} !important; }}
.sd-green {{ background:#FFFFFF; color:{INK} !important; border:3px solid #3B4048; }}
.sd-vhead {{ display:flex; gap:16px; align-items:center; }}
.sd-icon {{ flex:0 0 auto; width:56px; height:56px; border-radius:50%; display:flex; align-items:center; justify-content:center;
           font-size:34px; font-weight:800; border:3px solid currentColor; }}
.sd-green .sd-icon {{ color:{GREEN_TEXT} !important; }}
.sd-tier {{ font-size:19px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }}
.sd-green .sd-tier {{ color:{GREEN_TEXT} !important; }}
.sd-headline {{ font-size:34px; line-height:1.2; font-weight:800; margin-top:2px; }}
.sd-actions {{ margin-top:16px; padding-top:14px; border-top:2px solid currentColor; }}
.sd-actions-title {{ font-size:20px; font-weight:800; margin-bottom:4px; }}
.sd-actions ol {{ margin:0; padding-left: 1.4em; }}
.sd-actions li {{ font-size:21px; line-height:1.45; margin:4px 0; }}
/* why */
.sd-reason {{ font-size: 23px; line-height: 1.45; color:{INK}; margin: 8px 0; }}
.sd-why-title {{ font-weight: 700; }}
.sd-why {{ font-size: 20px; color:{INK}; margin: 6px 0; }}
.sd-chip {{ display:inline-block; font-size:19px; padding:4px 12px; margin:6px 8px 0 0; border-radius:999px;
            background:#FFFFFF; border:2px solid #3B4048; color:{INK}; }}
.sd-line {{ font-size: 23px; line-height: 1.45; color:{INK}; margin: 6px 0; }}
.sd-small {{ font-size: 18px; line-height: 1.45; color:#2B2F36; margin: 6px 0; }}
.sd-note {{ border-left: 4px solid #5A6270; padding-left: 12px; }}
.sd-footer, .sd-footer p {{ font-size: 18px; color:#2B2F36; border-top: 2px solid #D9DCE1; padding-top: 10px; }}
@media (max-width: 520px) {{
  .sd-hero h1 {{ font-size: 32px; }} .sd-headline {{ font-size: 27px; }} .sd-ex-row {{ grid-template-columns: 1fr; }}
  .sd-icon {{ width:46px; height:46px; font-size:28px; }}
}}
"""

# Force the light look even when the viewer's system prefers dark mode (design rule: white background).
JS = "() => { document.body.classList.remove('dark'); }"


HERO = ("<div class='sd-hero'><h1>Scam Drift</h1>"
        "<p class='sd-sub'>Got a text about your bank, a delivery or a payment? Check it here before you pay, tap a link "
        "or reply.</p><div class='sd-badges'><span class='sd-badge'>Warns only, never blocks</span>"
        "<span class='sd-badge'>Never says &ldquo;safe&rdquo;</span>"
        "<span class='sd-badge'>Prototype, not financial advice</span></div></div>")


def build_demo():
    import gradio as gr
    with gr.Blocks(title="Scam Drift") as demo:
        gr.HTML(HERO)
        gr.Markdown(f"The checker only warns; it never blocks a message. {DISCLAIMER}", elem_classes="sd-intro")
        with gr.Column(elem_classes="sd-card"):
            gr.HTML("<div class='sd-step'>1. Paste the text message</div>")
            inp = gr.Textbox(lines=5, label="Text message", placeholder="Paste the text message here",
                             elem_id="sd-input")
            btn = gr.Button("2. Check this text", variant="primary", elem_id="sd-check")
        gr.HTML("<div class='sd-step'>Or try an example</div>")
        with gr.Row(elem_classes="sd-ex-row"):
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
