"""Operational warning policy for the post-deadline FastAPI checker.

The saved lexical filter and the contextual model score the message. Rules add actionable
signals and input-quality warnings. The historical experiment uses the original policy.
"""
from __future__ import annotations

import html
import logging
import re
import unicodedata

from scam_drift import FRIENDLY_TOKENS, normalise, rule_reasons, money_offer_reasons
from triage import _bundle
from context_model import MODEL_ID, load_context_model

VERSION = "web-v5"
LOG = logging.getLogger(__name__)

_GAPS = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")
_QUOTES = str.maketrans("’‘‐‑–—", "''----")
_LINK = re.compile(r"https?://\S+|www\.\S+|<[A-Z_]+>", re.I)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_COMMON_OTHER = frozenset(
    "su una los las del sus esta este para por pulse pague paquete entrega verifique "
    "veuillez votre vous une les des avec pour compte carte colis veuillez remplir "
    "você voce seu sua sua para uma pelo conta clique entrega encomenda devido "
    "bitte ihre dein konto paket zahlen ihren über und danke anmelden".split()
)
_NEGATED = re.compile(r"\b(?:never|don't|do not|shouldn't|mustn't|won't|will not|no need to|not to)\s+(?:\w+\s+){0,5}$", re.I)

# Require context for ordinary terms such as «fee», «gift card» and «verification code».
_RULES = [
    ("credential", "Asks you to share a code, PIN, or password",
     r"\b(?:send|share|tell|give|forward|provide|text|reply(?: with)?|read(?: out)?|pass on)\b"
     r"(?:\s+[\w'-]+){0,5}?\s+(?:one[- ]time (?:code|password)|verification code|security code|"
     r"login code|passcode|password|otp|pin|code)\b"),
    ("gift_card", "Requests gift cards or a photo of the codes",
     r"\b(?:(?:buy|get|purchase|pick up|send|pay (?:with|using))\b[^.!?\n]{0,38}\bgift\s*cards?"
     r"|(?:share|send|text)\b[^.!?\n]{0,30}\b(?:photos?|pictures?)\b[^.!?\n]{0,40}\b(?:gift\s*cards?|codes?))\b"),
    ("job_fee", "Asks for money or equipment before a job starts",
     r"\b(?:pay|purchase|buy|send)\b[^.!?\n]{0,65}\b(?:training fee|equipment fee|starter kit|"
     r"equipment\b[^.!?\n]{0,24}\b(?:upfront|before|from our vendor)|(?:upfront|refundable) fee)\b"),
    ("rental_deposit", "Requests a deposit before a rental viewing",
     r"\b(?:deposit|application fee|wire(?: transfer)?)\b[^.!?\n]{0,65}"
     r"\b(?:before (?:you |the )?(?:view|see|tour|visit|show)|to (?:hold|reserve) (?:the |your )?(?:rental|unit|apartment))\b"),
    ("payment_method", "Requests payment by wire, cryptocurrency, or a similar hard-to-reverse method",
     r"\b(?:send|wire|transfer|pay|deposit)\b[^.!?\n]{0,50}"
     r"\b(?:bitcoin|crypto(?:currency)?|bitcoin atm|wire transfer|by wire)\b"),
    ("qr_payment", "Links a payment or account request to a QR code",
     r"\b(?:(?:scan|use)\b[^.!?\n]{0,32}\bqr(?: code)?\b[^.!?\n]{0,52}\b(?:pay|fees?|parking|sign in|verify)"
     r"|(?:pay|parking fee|verify)\b[^.!?\n]{0,42}\bqr code)\b"),
    ("account_link", "Directs you to a link to sign in or change account details",
     r"\b(?:click|tap|open|follow|visit|use|go to)\b[^.!?\n]{0,72}"
     r"\b(?:log ?in|sign ?in|verify (?:your |the )?(?:account|identity|payment)|"
     r"reset (?:your |the )?password|update (?:your |the )?payment (?:details|information))\b"),
    ("fee_pressure", "Pressures you to pay or update details",
     r"\b(?:(?:pay|send|transfer)(?:\s+(?:me|us|the|your|a|this|money|payment|fee|balance)){0,4}"
     r"\s+(?:now|immediately|right away)|(?:pay|update|confirm)\b[^.!?\n]{0,58}"
     r"\b(?:avoid (?:a |the )?(?:penalty|fine|late fees?|suspension)|or (?:your|the) (?:account|parcel|service) will))\b"),
    ("new_number", "Claims a new number or opens with a wrong-number story",
     r"\b(?:my new (?:phone )?number|(?:changed|lost|broke) my (?:phone|number)|"
     r"this is (?:the )?wrong number|(?:texted|got) the wrong number|sorry[^.!?\n]{0,22}wrong number)\b"),
    ("investment", "Promises investment returns or pushes you to deposit funds",
     r"\b(?:guaranteed returns?|risk[- ]free (?:profit|investment)|double your (?:money|investment)|"
     r"deposit\b[^.!?\n]{0,55}\b(?:unlock|withdraw) (?:your )?(?:profit|earnings|funds))\b"),
    ("foreign_link", "Contains a payment, account, or personal-information request",
     r"\b(?:pague (?:ahora|su|el|la)|verifique (?:su|sus) (?:cuenta|datos)|actualice (?:sus datos|su cuenta)|"
     r"confirme (?:su dirección|el pago)|pagar (?:la |el )?(?:tasa|multa|tarifa)|"
     r"veuillez (?:payer|remplir|confirmer|vérifier)|paiement (?:urgent|requis)|"
     r"pague (?:agora|a taxa)|confirme (?:seus dados|sua conta)|atualize (?:seus dados|sua conta))\b"),
]
_RULES = [(key, label, re.compile(pattern, re.I)) for key, label, pattern in _RULES]
_SECRET = re.compile(r"\b(?:don'?t|do not|never)\s+(?:tell|let)\b[^.!?\n]{0,40}\b(?:parents?|mom|mum|dad|anyone|anybody)\b"
                     r"|\b(?:our (?:little )?secret|keep (?:this|it) (?:secret|between us))\b", re.I)
_MEET = re.compile(r"\b(?:come|hop|get|step)\s+(?:in(?:to)?|to|inside)\s+(?:my|the|our)\s+(?:car|van|truck|house|room)\b"
                   r"|\b(?:come alone|sneak out|meet me alone|meet me|pick you up)\b", re.I)
_REWARD = re.compile(r"\b(?:give|pay|send|offer)\s+you\b[^.!?\n]{0,32}\b(?:cash|money|robux|gift cards?|dollars|bucks)\b"
                     r"|\b(?:give|pay|send)\s+you\s+\$\s*\d+\b", re.I)
_PRIVATE_IMAGE = re.compile(r"\b(?:send|take|show)\b[^.!?\n]{0,28}\b(?:nudes?|naked (?:pics?|photos?)|private (?:pics?|photos?)|pics? of yourself)\b", re.I)
_ALONE = re.compile(r"\b(?:are you (?:home )?alone|is (?:your )?(?:mom|mum|dad) home)\b", re.I)
_SOCIAL_GIFT = re.compile(r"\b(?:happy birthday|birthday (?:gift|present)|holiday (?:gift|present))\b", re.I)
_LURE_LINK = re.compile(r"\b(?:if you|in exchange|to get|for coming|if u)\b", re.I)


def _canonical(text: str) -> str:
    clean = unicodedata.normalize("NFKC", html.unescape(text)).translate(_GAPS).translate(_QUOTES)
    return re.sub(r"[^\S\n]+", " ", clean.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _match(pattern: re.Pattern, text: str):
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 70):match.start()]
        if not _NEGATED.search(prefix):
            return match
    return None


def _quality(text: str, norm: str) -> str:
    body = _LINK.sub(" ", text)
    letters = [c for c in body if c.isalpha()]
    words = _WORD.findall(body.lower())
    if (letters and sum(ord(c) > 0x24F for c in letters) * 3 > len(letters)
            or len(set(words) & _COMMON_OTHER) >= 3):
        return "possible_non_english"
    words = [w for w in norm.split() if not w.startswith("tok_") and len(_WORD.findall(w)) and len(w.strip(".,:;!?")) >= 2]
    return "limited_text" if len(words) < 3 else "readable"


def _signal(key: str, label: str, phrase: str = "") -> dict:
    # Markers point into the submitted message. Avoid repeating numeric sequences in the evidence labels.
    phrase = phrase.strip()[:110]
    return {"id": key, "label": label, "phrase": phrase if not re.search(r"\d[\d -]{3,}\d", phrase) else ""}


def _rule_signals(text: str, norm: str) -> tuple[list[dict], bool]:
    signals = []
    for key, label, pattern in _RULES:
        match = _match(pattern, text)
        if match:
            signals.append(_signal(key, label, match.group()))
    secret, meet, reward, images, alone = (_match(p, text) for p in (_SECRET, _MEET, _REWARD, _PRIVATE_IMAGE, _ALONE))
    luring = bool((secret and (meet or images or alone)) or
                  (meet and reward and (_LURE_LINK.search(text) or re.search(r"\b(?:my|our) (?:car|van)\b", meet.group(), re.I))))
    if luring:
        signals.insert(0, _signal("luring", "Combines a private meeting, reward, or secrecy request", (meet or secret).group()))
    elif images or alone:
        signals.append(_signal("personal_safety", "Asks for a private image or checks if you are alone", (images or alone).group()))
    if not any(s["id"] == "credential" for s in signals) and any(
        "code, PIN" in reason for reason in rule_reasons(text, norm)
    ):
        signals.append(_signal("credential", "Asks you to share a code, PIN, or password"))
    if money_offer_reasons(text) and not _SOCIAL_GIFT.search(text) and not (reward and meet and not luring):
        signals.append(_signal("reward", "Offers money, a prize, or a reward"))
    return signals, luring


def _highlight_words(model, norm: str, probability: float) -> list[str]:
    """Test at most 32 unique terms. The base score always uses the full text."""
    tokens = norm.split()
    unique = list(dict.fromkeys(tokens))
    half = 6 if len(norm) > 4000 else 16
    candidates = unique if len(unique) <= half * 2 else unique[:half] + unique[-half:]
    if not candidates:
        return []
    variants = [" ".join(word for word in tokens if word != candidate) for candidate in candidates]
    scores = model.predict_proba(variants)[:, 1]
    ranked = sorted(zip(candidates, scores), key=lambda item: item[1])
    return [FRIENDLY_TOKENS.get(word, word) for word, score in ranked if probability - score > 1e-8][:5]


def assess(raw: str, *, explain: bool = True, use_context: bool = True) -> dict:
    text = _canonical(raw)
    norm = normalise(text)
    quality = _quality(text, norm)
    signals, safety = _rule_signals(text, norm)
    bundle = _bundle()
    model, threshold = bundle["pipeline"], bundle["threshold"]
    p = float(model.predict_proba([norm])[0, 1]) if norm else 0
    flagged = p >= threshold
    has_contact = "tok_url" in norm or "tok_phone" in norm
    ids = {s["id"] for s in signals}
    strong_request = bool(ids & {"credential", "account_link", "foreign_link"}) and "tok_url" in norm
    contextual_model_flag = flagged and quality != "limited_text"
    neural = load_context_model() if use_context and norm and quality == "readable" else None
    neural_flag = False
    engine = "lexical"
    if neural is not None:
        try:
            neural_flag = bool(neural.scores([norm])[0] >= neural.threshold)
            engine = MODEL_ID
        except Exception as error:
            LOG.warning("Contextual check could not complete (%s)", type(error).__name__)

    tier = "GREEN"
    if safety or strong_request or (contextual_model_flag and has_contact):
        tier = "RED"
    elif signals or flagged or neural_flag or quality != "readable":
        tier = "YELLOW"

    if contextual_model_flag:
        signals.append(_signal("model", "Wording resembles messages the saved filter flagged"))
    elif neural_flag:
        signals.append(_signal("neural_model", "The fine-tuned model found wording patterns associated with scam or spam texts"))
    elif not signals and quality == "readable" and has_contact:
        signals.append(_signal("contact", "Contains a link or number that needs independent verification"))

    uncertain = quality != "readable" and not (ids or contextual_model_flag)
    return {"tier": tier, "signals": signals, "input_quality": quality, "uncertain": uncertain,
            "safety": safety, "context_model": engine,
            "top_words": _highlight_words(model, norm, p) if explain and (flagged or not neural_flag) else []}
