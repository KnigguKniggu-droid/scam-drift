"""Scam Drift: does a 2012-era SMS spam filter still protect a grandparent from 2020s smishing?

Run end to end (seeded) from the project root:
    python src/scam_drift.py

Outputs: results/metrics.json, results/*.csv, figures/*.png, models/*.joblib, models/shipped_config.json.
v2 (post-deadline v2 (Nov 18)): docs/V2_SPEC.md items 1-10 under metrics["v2"]; needs data/raw/extra/ or internet
(the loader falls back to pinned Hugging Face revisions).
Importing this module does NOT run the pipeline (app.py imports normalise/explain from here).
"""
from __future__ import annotations

import html
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
DATA_RAW = ROOT / "data" / "raw"
UCI_PATH = DATA_RAW / "SMSSpamCollection"
IMC_PATH = DATA_RAW / "imc25_smishing.csv"
TWINS_PATH = ROOT / "data" / "benign_twins.csv"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
MODELS = ROOT / "models"

# Cost model for the grandparent: a missed scam costs 5x a false alarm.
COST_FN = 5.0
COST_FP = 1.0
# Time split: modern scams dated up to and including this year may be used for training the fix.
TRAIN_LAST_YEAR = 2021

# ---------------------------------------------------------------------------
# 1. Normalisation (applied identically to every source)
# ---------------------------------------------------------------------------
# Placeholder tokens found in either dataset -> one shared vocabulary.
# UCI uses HTML-escaped placeholders such as &lt;#&gt; and &lt;DECIMAL&gt;.
PLACEHOLDER_MAP = {
    "URL": " tok_url ", "IP_ADDRESS": " tok_url ",
    "PHONE_NUMBER": " tok_phone ",
    "EMAIL_ADDRESS": " tok_email ", "EMAIL": " tok_email ",
    "DATE_TIME": " tok_date ", "TIME": " tok_date ",
    # Named entities (people, brands, places) were removed by the IMC25 authors.
    # UCI has no equivalent tag, so we delete the tag instead of creating a dataset-only token.
    "NAMED_ENTITY": " ", "LOCATION": " ", "NRP": " ", "NAME": " ",
    # Presidio-style ID tags mostly fire on long numbers and codes -> generic number.
    "US_DRIVER_LICENSE": " tok_num ", "US_BANK_NUMBER": " tok_num ", "UK_NHS": " tok_num ",
    "US_PASSPORT": " tok_num ", "US_SSN": " tok_num ", "US_ITIN": " tok_num ",
    "CREDIT_CARD": " tok_num ", "IBAN_CODE": " tok_num ", "MEDICAL_LICENSE": " tok_num ",
    "CRYPTO": " tok_num ", "NUMERO_COLIS": " tok_num ", "#": " tok_num ", "DECIMAL": " tok_num ",
}
_PH_RE = re.compile(r"<([A-Z_#]+)>")
_OBFUSCATED_DOT = re.compile(r"\s?[\(\[]\.[\)\]]\s?")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TLDS = ("com|net|org|co|uk|ly|info|biz|io|me|us|in|gov|xyz|top|site|online|link|app|cc|ru|cn|de|"
         "ca|au|tk|ml|ga|cf|gq|shop|club|live|vip|icu|buzz|win|ws|eu|es|fr|nl|it|id|my|ph|sg|to|gl")
_URL_RE = re.compile(
    r"(?:https?://\S+|www\.\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:" + _TLDS + r")\b(?:/\S*)?)", re.I)
_MONEY_RE = re.compile(
    r"(?:[£$€₹¥]|\b(?:rs|inr|usd|gbp|eur|rm|aud|cad)\.?)\s?\d[\d,]*(?:\.\d+)?"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:pounds|dollars|euros|usd|gbp|eur|pence|ppm|p)\b"
    r"|\b\d[\d,]*(?:\.\d+)?\s?[£$€₹¥]", re.I)  # suffix symbols, e.g. "60$"
_MONTHS = "january|february|march|april|june|july|august|september|october|november|december"
_MON_ABBR = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_RE = re.compile(
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\s?(?:[ap]\.?m\.?)?\b"
    r"|\b\d{1,2}\s?(?:[ap]\.?m\.?)\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:" + _MON_ABBR + r")[a-z]*\b"
    r"|\b(?:" + _MON_ABBR + r")[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\b"
    r"|\b(?:" + _MONTHS + r")\b"
    r"|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
    r"|\b(?:today|tomorrow|tonight|yesterday)\b", re.I)
_PHONE_RE = re.compile(r"\+?\(?\d[\d\s\-()]{5,}\d")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
_WS_RE = re.compile(r"\s+")


def _ph_sub(m: re.Match) -> str:
    tag = m.group(1)
    return PLACEHOLDER_MAP.get(tag, " " + tag.lower() + " ")


def normalise(text: str) -> str:
    """Map URLs, phones, emails, money, dates and numbers to shared tokens, then lowercase."""
    if not isinstance(text, str):
        return ""
    t = html.unescape(text)
    t = _PH_RE.sub(_ph_sub, t)
    t = _OBFUSCATED_DOT.sub(".", t)
    t = _EMAIL_RE.sub(" tok_email ", t)
    t = _URL_RE.sub(" tok_url ", t)
    t = _MONEY_RE.sub(" tok_money ", t)
    t = _DATE_RE.sub(" tok_date ", t)

    def _phone(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return " tok_phone " if len(digits) >= 7 else m.group(0)

    t = _PHONE_RE.sub(_phone, t)
    t = _NUM_RE.sub(" tok_num ", t)
    t = t.lower()
    return _WS_RE.sub(" ", t).strip()


# ---------------------------------------------------------------------------
# 2. Data loading
# ---------------------------------------------------------------------------
def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_uci() -> pd.DataFrame:
    rows = []
    for line in _read_text(UCI_PATH).splitlines():
        if "\t" not in line:
            continue
        lab, txt = line.split("\t", 1)
        rows.append((1 if lab.strip() == "spam" else 0, txt))
    df = pd.DataFrame(rows, columns=["label", "text"])
    df["norm"] = df["text"].map(normalise)
    n_raw = len(df)
    # Drop exact duplicates after normalisation; drop texts that carry both labels.
    conflict = df.groupby("norm")["label"].nunique()
    df = df[~df["norm"].isin(conflict[conflict > 1].index)]
    df = df.drop_duplicates("norm").reset_index(drop=True)
    df.attrs["n_raw"] = n_raw
    return df


_YEAR4 = re.compile(r"(?<!\d)(20(?:1[5-9]|2[0-5]))(?!\d)")
_YEAR2 = re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-](1[5-9]|2[0-5])\b")


def extract_year(s) -> float:
    """The IMC25 'time' column is the raw screenshot timestamp (e.g. 'Today 8:15 AM').
    Only rows whose timestamp shows an explicit year can be dated."""
    if not isinstance(s, str):
        return np.nan
    m = _YEAR4.search(s)
    if m:
        return float(m.group(1))
    m = _YEAR2.search(s)
    if m:
        return float(2000 + int(m.group(1)))
    return np.nan


def load_imc() -> pd.DataFrame:
    import io
    df = pd.read_csv(io.StringIO(_read_text(IMC_PATH)))
    df["year"] = df["time"].map(extract_year)
    df["scam_type"] = df["scam_type"].fillna("unlabelled")
    return df


def length_bucket(n: int) -> str:
    if n < 80:
        return "a <80 chars"
    if n < 160:
        return "b 80-159"
    if n < 320:
        return "c 160-319"
    return "d 320+"


# ---------------------------------------------------------------------------
# 3. Models
# ---------------------------------------------------------------------------
URGENCY_WORDS = ["urgent", "verify", "suspended", "click", "winner", "claim", "locked", "blocked",
                 "confirm", "won", "prize", "immediately"]
_URG_RE = re.compile(r"\b(?:" + "|".join(URGENCY_WORDS) + r")\b")


def rule_flag(norm_texts) -> np.ndarray:
    """Simple rule baseline: flag if the normalised message has a link or an urgency word."""
    return np.array([("tok_url" in t) or bool(_URG_RE.search(t)) for t in norm_texts], dtype=int)


def link_flag(norm_texts) -> np.ndarray:
    """Simplest rule: flag if the normalised message contains a link (tok_url)."""
    return np.array(["tok_url" in t for t in norm_texts], dtype=int)


# Three-tier warning used by the demo (post-hoc design, chosen after the v1 results; see RESULTS_DETAIL.md):
# RED    = Model 2012 flags the text AND it contains a link   -> "Likely scam: do not tap, do not reply"
# YELLOW = Model 2012 flags the text, no link                 -> "Ask a family member before replying"
# GREEN  = Model 2012 does not flag it                         -> "No warning signs found" (never "safe")
# The fixed model is not part of the tiers because it flags almost every genuine-style text (benign twins).
def triage(p_2012: float, threshold_2012: float, has_link: bool) -> str:
    if p_2012 >= threshold_2012:
        return "RED" if has_link else "YELLOW"
    return "GREEN"


FRIENDLY_TOKENS = {"tok_url": "[a web link]", "tok_phone": "[a phone number]", "tok_money": "[a money amount]",
                   "tok_email": "[an email address]", "tok_date": "[a date or time]", "tok_num": "[a number]"}


def friendly_explain(model, norm_text: str, k: int = 5):
    """Like explain(), but drops n-grams made only of stop words and writes tokens in plain words."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    out = []
    for w, c in explain(model, norm_text, k=10000):
        toks = w.split()
        if all(t in ENGLISH_STOP_WORDS for t in toks):
            continue
        out.append((" ".join(FRIENDLY_TOKENS.get(t, t) for t in toks), c))
        if len(out) >= k:
            break
    return out


def make_word_model():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                  token_pattern=r"(?u)\b\w+\b")),
        ("lr", LogisticRegression(C=10.0, class_weight="balanced", max_iter=3000, random_state=SEED)),
    ])


def make_char_model():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True,
                                  max_features=200000)),
        ("lr", LogisticRegression(C=10.0, class_weight="balanced", max_iter=3000, random_state=SEED)),
    ])


def pick_threshold(y, p) -> dict:
    """Choose the threshold that minimises COST_FN*FN + COST_FP*FP on out-of-fold predictions."""
    best = None
    for th in np.round(np.arange(0.02, 0.99, 0.01), 2):
        pred = (p >= th).astype(int)
        fn = int(((pred == 0) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        cost = COST_FN * fn + COST_FP * fp
        if best is None or cost < best["cost"]:
            best = {"threshold": float(th), "cost": cost, "fn": fn, "fp": fp}
    return best


def oof_proba(make_model, X, y, n_splits=5) -> np.ndarray:
    from sklearn.model_selection import StratifiedKFold
    p = np.zeros(len(y))
    for tr, va in StratifiedKFold(n_splits, shuffle=True, random_state=SEED).split(X, y):
        m = make_model().fit(X[tr], y[tr])
        p[va] = m.predict_proba(X[va])[:, 1]
    return p


def explain(model, norm_text: str, k: int = 5):
    """Top-k n-grams pushing toward 'scam' = LR coefficient * tf-idf value (positive only)."""
    vec, lr = model.named_steps["tfidf"], model.named_steps["lr"]
    x = vec.transform([norm_text]).tocoo()
    names = vec.get_feature_names_out()
    contrib = [(names[j], float(v * lr.coef_[0, j])) for j, v in zip(x.col, x.data)]
    contrib = [c for c in contrib if c[1] > 0]
    contrib.sort(key=lambda c: -c[1])
    return contrib[:k]


# ---------------------------------------------------------------------------
# 4. Metric helpers
# ---------------------------------------------------------------------------
def prf(y, pred) -> dict:
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else 0.0
    far = fp / (fp + tn) if (fp + tn) else None
    return {"precision": _r(prec), "recall": _r(rec), "f1": _r(f1), "false_alarm_rate": _r(far),
            "recall_ci95": wilson(tp, tp + fn), "false_alarm_rate_ci95": wilson(fp, fp + tn),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": int(len(y))}


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


def wilson(k, n, z: float = 1.96):
    """Wilson score 95% interval for k successes out of n, as [low, high]."""
    k, n = int(k), int(n)
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [_r(max(0.0, c - h)), _r(min(1.0, c + h))]


def rate_ci(flags) -> dict:
    flags = np.asarray(flags).astype(int)
    return {"rate": _r(flags.mean()) if len(flags) else None, "k": int(flags.sum()), "n": int(len(flags)),
            "ci95": wilson(flags.sum(), len(flags))}


def recall_table(df: pd.DataFrame, by: str, pred_cols: list[str], ci_cols=("word_2012", "word_fixed")) -> pd.DataFrame:
    g = df.groupby(by)
    out = g.size().rename("n").to_frame()
    for c in pred_cols:
        out["recall_" + c] = g["pred_" + c].mean().round(4)
    for c in pred_cols:
        if c in ci_cols:
            ci = g["pred_" + c].agg(lambda s: wilson(s.sum(), len(s)))
            out["ci95_lo_" + c] = ci.map(lambda v: v[0]); out["ci95_hi_" + c] = ci.map(lambda v: v[1])
    return out.reset_index()


# ---------------------------------------------------------------------------
# 5. Pipeline steps (each callable on its own from the notebook)
# ---------------------------------------------------------------------------
def step_load_and_split():
    from sklearn.model_selection import train_test_split
    uci = load_uci()
    tr_idx, te_idx = train_test_split(np.arange(len(uci)), test_size=0.2, stratify=uci["label"],
                                      random_state=SEED)
    uci_tr, uci_te = uci.iloc[tr_idx].reset_index(drop=True), uci.iloc[te_idx].reset_index(drop=True)

    imc = load_imc()
    info = {"imc_rows_total": int(len(imc)),
            "imc_rows_with_explicit_year": int(imc["year"].notna().sum())}
    imc = imc[imc["text"].notna()].copy()
    imc["norm"] = imc["text"].map(normalise)
    imc = imc[imc["norm"].str.len() > 0]

    en = imc[imc["language"] == "English"].copy()
    info["imc_english_rows"] = int(len(en))
    # Dedupe: keep the earliest dated copy so a campaign never sits on both sides of the split.
    en = en.sort_values("year", na_position="last", kind="stable")
    en = en.drop_duplicates("norm", keep="first")
    info["imc_english_unique_after_norm"] = int(len(en))
    uci_set = set(uci["norm"])
    overlap = en["norm"].isin(uci_set)
    info["imc_english_dropped_overlap_with_uci"] = int(overlap.sum())
    en = en[~overlap].copy()
    en["len_bucket"] = en["text"].str.len().map(length_bucket)

    early = en[en["year"] <= TRAIN_LAST_YEAR].reset_index(drop=True)
    late = en[en["year"] > TRAIN_LAST_YEAR].reset_index(drop=True)
    undated = en[en["year"].isna()].reset_index(drop=True)
    info.update({"time_split_rule": f"train pool = English scams with explicit year <= {TRAIN_LAST_YEAR}; "
                                    f"test = explicit year >= {TRAIN_LAST_YEAR + 1}; undated rows never trained on",
                 "modern_early_train_n": int(len(early)), "modern_late_test_n": int(len(late)),
                 "modern_undated_n": int(len(undated)),
                 "modern_early_years": sorted(int(y) for y in early["year"].unique()),
                 "modern_late_years": sorted(int(y) for y in late["year"].unique()),
                 "uci_rows_raw": int(uci.attrs.get("n_raw", 0)), "uci_rows_dedup": int(len(uci)),
                 "uci_train_n": int(len(uci_tr)), "uci_test_n": int(len(uci_te)),
                 "uci_train_spam": int(uci_tr["label"].sum()), "uci_test_spam": int(uci_te["label"].sum())})

    nonen = imc[(imc["language"] != "English") & imc["translation"].notna()].copy()
    nonen["norm_tr"] = nonen["translation"].map(normalise)
    nonen = nonen.drop_duplicates("norm")
    train_norms = set(uci_tr["norm"]) | set(early["norm"])
    nonen = nonen[~nonen["norm"].isin(train_norms) & ~nonen["norm_tr"].isin(train_norms)].reset_index(drop=True)
    info["nonenglish_eval_n"] = int(len(nonen))

    twins = pd.read_csv(TWINS_PATH)
    twins["norm"] = twins["text"].map(normalise)
    return {"uci": uci, "uci_tr": uci_tr, "uci_te": uci_te, "early": early, "late": late,
            "undated": undated, "nonen": nonen, "twins": twins, "info": info}


def step_shortcut_check(d):
    """Can a classifier tell UCI spam from IMC25 English scams after normalisation?
    High separability = remaining dataset artifacts and/or genuine language drift."""
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.metrics import roc_auc_score, balanced_accuracy_score
    a = d["uci"].loc[d["uci"]["label"] == 1, "norm"].tolist()
    en_all = pd.concat([d["early"], d["late"], d["undated"]])
    b = en_all["norm"].sample(n=min(len(en_all), 3000), random_state=SEED).tolist()
    X = np.array(a + b, dtype=object); y = np.array([0] * len(a) + [1] * len(b))
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    p = cross_val_predict(make_word_model(), X, y, cv=cv, method="predict_proba")[:, 1]
    m = make_word_model().fit(X, y)
    names = m.named_steps["tfidf"].get_feature_names_out(); coef = m.named_steps["lr"].coef_[0]
    order = np.argsort(coef)
    res = {"n_uci_spam": len(a), "n_imc_english_sample": len(b),
           "cv_roc_auc": _r(roc_auc_score(y, p)), "cv_balanced_accuracy": _r(balanced_accuracy_score(y, p >= 0.5)),
           "top_tokens_say_imc25": [names[i] for i in order[::-1][:20]],
           "top_tokens_say_uci2012": [names[i] for i in order[:20]]}
    tokrate = {}
    for tok in ["tok_url", "tok_phone", "tok_email", "tok_money", "tok_date", "tok_num"]:
        tokrate[tok] = {"uci_spam": _r(np.mean([tok in t for t in a])),
                        "uci_ham": _r(np.mean([tok in t for t in d["uci"].loc[d["uci"]["label"] == 0, "norm"]])),
                        "imc_english": _r(np.mean([tok in t for t in b]))}
    res["token_presence_rate"] = tokrate
    return res


def step_train(d):
    """Train the 2012 models (UCI only) and the fixed models (UCI + early modern scams).
    Thresholds come from 5-fold out-of-fold predictions on each model's own training data."""
    uci_tr = d["uci_tr"]
    X12 = uci_tr["norm"].to_numpy(dtype=object); y12 = uci_tr["label"].to_numpy()
    Xfx = np.concatenate([X12, d["early"]["norm"].to_numpy(dtype=object)])
    yfx = np.concatenate([y12, np.ones(len(d["early"]), dtype=int)])
    models, thresholds = {}, {}
    for name, maker, X, y in [("word_2012", make_word_model, X12, y12), ("char_2012", make_char_model, X12, y12),
                              ("word_fixed", make_word_model, Xfx, yfx), ("char_fixed", make_char_model, Xfx, yfx)]:
        p = oof_proba(maker, X, y)
        thresholds[name] = pick_threshold(y, p)
        thresholds[name]["validation"] = "5-fold out-of-fold predictions on this model's training data"
        thresholds[name]["validation_n"] = int(len(y)); thresholds[name]["validation_scam_n"] = int(y.sum())
        models[name] = maker().fit(X, y)
    return models, thresholds


def step_evaluate(d, models, thresholds):
    uci_te, late, undated, nonen, twins = d["uci_te"], d["late"], d["undated"], d["nonen"], d["twins"]
    yte = uci_te["label"].to_numpy()
    M = {"baselines": {}, "uci_test": {}, "modern_late_test": {}, "modern_undated": {},
         "benign_twins": {}, "nonenglish": {}}
    # (a) always not-scam, (b) rule
    M["baselines"]["always_not_scam"] = {
        "uci_test": prf(yte, np.zeros_like(yte)), "uci_test_accuracy": _r((yte == 0).mean()),
        "modern_late_recall": 0.0, "benign_twins_false_alarm_rate": 0.0, "benign_twins_scam_recall": 0.0}
    rule = {"uci_test": prf(yte, rule_flag(uci_te["norm"])),
            "modern_late_recall": _r(rule_flag(late["norm"]).mean()),
            "modern_undated_recall": _r(rule_flag(undated["norm"]).mean())}
    tw = prf(twins["label"].to_numpy(), rule_flag(twins["norm"]))
    rule["benign_twins_false_alarm_rate"] = tw["false_alarm_rate"]; rule["benign_twins_scam_recall"] = tw["recall"]
    rule["benign_twins"] = tw
    rule["modern_late_recall_ci95"] = wilson(rule_flag(late["norm"]).sum(), len(late))
    M["baselines"]["rule_url_or_urgency"] = rule
    # (b2) link-only rule: the simplest possible "warn before tapping a link" filter.
    lk = {"uci_test": prf(yte, link_flag(uci_te["norm"])),
          "modern_late_recall": _r(link_flag(late["norm"]).mean()),
          "modern_late_recall_ci95": wilson(link_flag(late["norm"]).sum(), len(late)),
          "modern_undated_recall": _r(link_flag(undated["norm"]).mean())}
    lk["benign_twins"] = prf(twins["label"].to_numpy(), link_flag(twins["norm"]))
    lk["benign_twins_false_alarm_rate"] = lk["benign_twins"]["false_alarm_rate"]
    lk["benign_twins_scam_recall"] = lk["benign_twins"]["recall"]
    M["baselines"]["rule_link_only"] = lk
    late = late.copy(); undated = undated.copy(); twins = twins.copy(); uci_te = uci_te.copy(); nonen = nonen.copy()
    late["pred_rule"] = rule_flag(late["norm"]); undated["pred_rule"] = rule_flag(undated["norm"])
    for name, m in models.items():
        th = thresholds[name]["threshold"]
        p_te = m.predict_proba(uci_te["norm"])[:, 1]; uci_te["p_" + name] = p_te
        M["uci_test"][name] = {"at_threshold": prf(yte, (p_te >= th).astype(int)),
                               "at_0.5": prf(yte, (p_te >= 0.5).astype(int)), "threshold": th}
        p_l = m.predict_proba(late["norm"])[:, 1]; late["p_" + name] = p_l
        late["pred_" + name] = (p_l >= th).astype(int)
        M["modern_late_test"][name] = {"recall_at_threshold": _r((p_l >= th).mean()),
                                       "recall_at_threshold_ci95": wilson((p_l >= th).sum(), len(late)),
                                       "recall_at_0.5": _r((p_l >= 0.5).mean()), "n": int(len(late))}
        p_u = m.predict_proba(undated["norm"])[:, 1]; undated["pred_" + name] = (p_u >= th).astype(int)
        M["modern_undated"][name] = {"recall_at_threshold": _r((p_u >= th).mean()),
                                     "recall_at_0.5": _r((p_u >= 0.5).mean()), "n": int(len(undated))}
        p_t = m.predict_proba(twins["norm"])[:, 1]; twins["p_" + name] = p_t
        M["benign_twins"][name] = {"at_threshold": prf(twins["label"].to_numpy(), (p_t >= th).astype(int)),
                                   "at_0.5": prf(twins["label"].to_numpy(), (p_t >= 0.5).astype(int))}
        p_raw = m.predict_proba(nonen["norm"])[:, 1]; p_tr = m.predict_proba(nonen["norm_tr"])[:, 1]
        nonen["pred_raw_" + name] = (p_raw >= th).astype(int); nonen["pred_tr_" + name] = (p_tr >= th).astype(int)
        M["nonenglish"][name] = {"recall_raw_text": _r((p_raw >= th).mean()),
                                 "recall_english_translation": _r((p_tr >= th).mean()), "n": int(len(nonen))}
    M["modern_late_test"]["note"] = ("All rows are scams, so precision and false-alarm rate are undefined here; "
                                     "false alarms are measured on UCI test ham and the benign twins.")
    # Link-gated mode: warn only when the model says scam AND the message contains a link.
    # POST-HOC: this mode was added after the first results were seen; it is exploratory, not pre-registered.
    M["link_gated"] = {"rule": "warn = model flag at its threshold AND message contains tok_url",
                       "status": "post-hoc exploratory analysis (added after the v1 results were seen)"}
    for name in ["word_2012", "word_fixed"]:
        th = thresholds[name]["threshold"]
        g = lambda df, col: ((df[col] >= th) & df["norm"].str.contains("tok_url")).astype(int).to_numpy()
        late_g = g(late, "p_" + name); twins_g = g(twins, "p_" + name)
        M["link_gated"][name] = {
            "uci_test": prf(yte, g(uci_te, "p_" + name)),
            "modern_late_recall": _r(late_g.mean()),
            "modern_late_recall_ci95": wilson(late_g.sum(), len(late_g)),
            "modern_late_recall_on_rows_with_link": _r(late_g[late["norm"].str.contains("tok_url").to_numpy()].mean()),
            "benign_twins": prf(twins["label"].to_numpy(), twins_g),
            # Share of messages where the gated model gives the same answer as the link-only rule.
            "agreement_with_link_only_rule": {
                "modern_late": _r((late_g == link_flag(late["norm"])).mean()),
                "benign_twins": _r((twins_g == link_flag(twins["norm"])).mean()),
                "uci_test": _r((g(uci_te, "p_" + name) == link_flag(uci_te["norm"])).mean())}}
    M["link_gated"]["modern_late_share_with_link"] = _r(late["norm"].str.contains("tok_url").mean())

    # Three-tier warning (post-hoc design used by the demo; see triage()).
    th12 = thresholds["word_2012"]["threshold"]
    tier = lambda df: np.array([triage(p, th12, "tok_url" in n) for p, n in zip(df["p_word_2012"], df["norm"])])
    undated["p_word_2012"] = models["word_2012"].predict_proba(undated["norm"])[:, 1]
    T = {"status": "post-hoc design (chosen after the v1 results were seen); tiers come from Model 2012 + link",
         "definition": {"RED": "Model 2012 flags AND link", "YELLOW": "Model 2012 flags, no link",
                        "GREEN": "Model 2012 does not flag"}}
    for key, df in [("modern_late_scams", late), ("modern_undated_scams", undated),
                    ("benign_twins_genuine", twins[twins["label"] == 0]), ("benign_twins_scam", twins[twins["label"] == 1]),
                    ("uci_test_ham", uci_te[uci_te["label"] == 0]), ("uci_test_spam", uci_te[uci_te["label"] == 1])]:
        t = tier(df)
        T[key] = {"share_red": rate_ci(t == "RED"), "share_yellow": rate_ci(t == "YELLOW"),
                  "share_red_or_yellow": rate_ci(t != "GREEN")}
    M["triage"] = T
    return M, {"uci_te": uci_te, "late": late, "undated": undated, "twins": twins, "nonen": nonen}


def _max_cos(fit_texts, a, b, same=False):
    """Max TF-IDF (word 1-2 gram) cosine of each text in a to any text in b (excluding itself if same)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    v = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b").fit(fit_texts)
    S = (v.transform(a) @ v.transform(b).T).toarray()
    if same:
        np.fill_diagonal(S, 0.0)
    return S


def step_near_duplicate_check(d, P=None, models=None, thresholds=None):
    """Near-duplicate checks: (1) late test vs early training scams, (2) UCI test vs UCI train,
    (3) near-duplicates inside the late test (greedy clusters at cosine >= 0.9)."""
    res = {}
    s = _max_cos(pd.concat([d["early"]["norm"], d["late"]["norm"]]), d["late"]["norm"], d["early"]["norm"]).max(axis=1)
    res["late_test_frac_with_cosine_ge_0.9_to_train"] = _r((s >= 0.9).mean())
    res["late_test_frac_with_cosine_ge_0.7_to_train"] = _r((s >= 0.7).mean())

    # UCI: test vs train (the UCI split is a plain stratified split, so spam templates repeat across it).
    uci_tr, uci_te = d["uci_tr"], d["uci_te"]
    S = _max_cos(d["uci"]["norm"], uci_te["norm"], uci_tr["norm"])
    s_all = S.max(axis=1)
    spam_te = uci_te["label"].to_numpy() == 1
    s_spam = S[spam_te][:, uci_tr["label"].to_numpy() == 1].max(axis=1)
    u = {"uci_test_frac_with_cosine_ge_0.9_to_train": _r((s_all >= 0.9).mean()),
         "uci_test_spam_frac_with_cosine_ge_0.9_to_train_spam": _r((s_spam >= 0.9).mean()),
         "uci_test_spam_frac_with_cosine_ge_0.7_to_train_spam": _r((s_spam >= 0.7).mean())}
    if P is not None and thresholds is not None:
        p = P["uci_te"]["p_word_2012"].to_numpy()[spam_te] >= thresholds["word_2012"]["threshold"]
        for cut in (0.9, 0.7):
            keep = s_spam < cut
            u[f"word_2012_recall_uci_test_spam_without_near_dup_{cut}"] = rate_ci(p[keep])
            u[f"word_2012_recall_uci_test_spam_with_near_dup_{cut}"] = rate_ci(p[~keep])
    res["uci"] = u

    # Inside the late test: near-duplicate variants (e.g. differing by one emoji) inflate the effective n.
    late = d["late"] if P is None else P["late"]
    Sl = _max_cos(late["norm"], late["norm"], late["norm"], same=True)
    res["late_test_frac_with_cosine_ge_0.9_to_other_late_row"] = _r((Sl.max(axis=1) >= 0.9).mean())
    cl = -np.ones(len(late), dtype=int); k = 0
    for i in range(len(late)):
        if cl[i] < 0:
            members = np.where((Sl[i] >= 0.9) & (cl < 0))[0]
            cl[i] = k; cl[members] = k; k += 1
    res["late_test_clusters_at_0.9"] = int(k)
    if P is not None:
        lc = late.assign(cluster=cl)
        res["late_test_cluster_level_recall"] = {
            c: _r(lc.groupby("cluster")["pred_" + c].mean().mean()) for c in ["rule", "word_2012", "word_fixed"]}
    return res


def step_tok_date_ablation(d):
    """Retrain the word models with every tok_date token removed from all sources (IMC25's anonymiser tags dates and
    durations far more often than our regex, so tok_date is a dataset artifact). Same thresholds rule (OOF)."""
    strip = lambda s: s.str.replace(r"\btok_date\b", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    dd = {k: (v.assign(norm=strip(v["norm"])) if isinstance(v, pd.DataFrame) and "norm" in v else v) for k, v in d.items()}
    X12 = dd["uci_tr"]["norm"].to_numpy(dtype=object); y12 = dd["uci_tr"]["label"].to_numpy()
    Xfx = np.concatenate([X12, dd["early"]["norm"].to_numpy(dtype=object)])
    yfx = np.concatenate([y12, np.ones(len(dd["early"]), dtype=int)])
    out = {"what": "tok_date removed from every text (train and test) before TF-IDF; models retrained; thresholds re-chosen"}
    yte = dd["uci_te"]["label"].to_numpy()
    for name, X, y in [("word_2012", X12, y12), ("word_fixed", Xfx, yfx)]:
        th = pick_threshold(y, oof_proba(make_word_model, X, y))["threshold"]
        m = make_word_model().fit(X, y)
        tw = dd["twins"]
        out[name] = {"threshold": th,
                     "uci_test": prf(yte, (m.predict_proba(dd["uci_te"]["norm"])[:, 1] >= th).astype(int)),
                     "modern_late_recall": _r((m.predict_proba(dd["late"]["norm"])[:, 1] >= th).mean()),
                     "benign_twins": prf(tw["label"].to_numpy(), (m.predict_proba(tw["norm"])[:, 1] >= th).astype(int))}
    return out


def step_demo_examples(models, thresholds, P):
    """Fixed-rule demo examples (not hand-picked for a good result), written to results/demo_examples.csv:
    1. first 2022+ test scam (by row order) with a link that Model 2012 misses and the fixed model catches;
    2. first 2022+ test scam (by row order) that both word models miss;
    3. first genuine benign twin (file order) that both word models flag."""
    late, twins = P["late"], P["twins"]
    t12, tfx = thresholds["word_2012"]["threshold"], thresholds["word_fixed"]["threshold"]
    f12, ffx = late["p_word_2012"] >= t12, late["p_word_fixed"] >= tfx
    has_link = late["norm"].str.contains("tok_url")
    picks = [("2022+ test scam: 2012 misses, fixed catches", late[~f12 & ffx & has_link].iloc[0]),
             ("2022+ test scam: both miss", late[~f12 & ~ffx].iloc[0]),
             ("synthetic genuine text: false alarm",
              twins[(twins["label"] == 0) & (twins["p_word_2012"] >= t12) & (twins["p_word_fixed"] >= tfx)].iloc[0])]
    rows = []
    for why, r in picks:
        rows.append({"example": why, "text": r["text"], "true_label": "scam" if why.startswith("2022") else "genuine",
                     "scam_type": r.get("scam_type", r.get("category", "")),
                     "p_2012": _r(r["p_word_2012"]), "flag_2012": bool(r["p_word_2012"] >= t12),
                     "p_fixed": _r(r["p_word_fixed"]), "flag_fixed": bool(r["p_word_fixed"] >= tfx),
                     "tier": triage(r["p_word_2012"], t12, "tok_url" in r["norm"]),
                     "top_words_2012": "; ".join(w for w, _ in friendly_explain(models["word_2012"], r["norm"], 3)),
                     "top_words_fixed": "; ".join(w for w, _ in friendly_explain(models["word_fixed"], r["norm"], 3))})
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "demo_examples.csv", index=False)
    return df.to_dict(orient="records")


def hypothesis_for_miss(norm: str, scam_type: str) -> str:
    if "tok_url" not in norm and not _URG_RE.search(norm):
        if scam_type in ("wrong number", "hey mum/dad"):
            return "conversational opener with no link or urgency word; the scam starts later in the chat"
        return "no link and no urgency word; reads like an ordinary notice"
    if len(norm.split()) <= 8:
        return "very short; few n-grams carry signal"
    if scam_type in ("banking", "government", "telecom"):
        return "official-sounding wording that also appears in genuine notifications"
    return "vocabulary not seen in training scams"


def hypothesis_for_false_alarm(norm: str) -> str:
    if "tok_url" in norm:
        return "contains a link; the normaliser hides the domain, so an official link looks like a scam link"
    if "tok_num" in norm and ("code" in norm or "verification" in norm):
        return "one-time code wording overlaps with modern banking scams"
    if "tok_money" in norm:
        return "money amount plus account wording overlaps with payment scams"
    if re.search(r"\b(free|win|prize|claim|offer|call)\b", norm):
        return "promotional or call-to-action words typical of 2012 spam"
    return "formal notification style (unlike 2012 chatty ham) is learned as 'modern scam'"


def step_tables_and_figures(d, models, thresholds, M, P):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve
    RESULTS.mkdir(exist_ok=True); FIGURES.mkdir(exist_ok=True)
    C12, CFX, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
    late, undated, twins, uci_te, nonen = P["late"], P["undated"], P["twins"], P["uci_te"], P["nonen"]
    pcols = ["rule", "word_2012", "char_2012", "word_fixed", "char_fixed"]

    # Per scam type and per length bucket on the late test.
    st = recall_table(late, "scam_type", pcols).sort_values("n", ascending=False)
    st.to_csv(RESULTS / "recall_by_scam_type_late_test.csv", index=False)
    lb = recall_table(late, "len_bucket", pcols)
    uci_ham = uci_te[uci_te["label"] == 0].copy()
    uci_ham["len_bucket"] = uci_ham["text"].str.len().map(length_bucket)
    for n in ["word_2012", "word_fixed"]:
        uci_ham["fa_" + n] = (uci_ham["p_" + n] >= thresholds[n]["threshold"]).astype(int)
    fa = uci_ham.groupby("len_bucket").agg(uci_ham_n=("label", "size"), fa_word_2012=("fa_word_2012", "mean"),
                                           fa_word_fixed=("fa_word_fixed", "mean")).round(4).reset_index()
    lb = lb.merge(fa, on="len_bucket", how="outer")
    lb.to_csv(RESULTS / "by_length_bucket.csv", index=False)

    # Per year: 2012 model on every dated English scam (none were trained on); fixed on test years only.
    dated = pd.concat([d["early"].assign(split="train_pool"), late.assign(split="late_test")])
    for n in ["word_2012", "char_2012"]:
        dated["pred_" + n] = (models[n].predict_proba(dated["norm"])[:, 1] >= thresholds[n]["threshold"]).astype(int)
    yr = recall_table(dated, "year", ["word_2012", "char_2012"])
    yfx = recall_table(late, "year", ["word_fixed", "char_fixed"])
    yr = yr.merge(yfx.drop(columns="n"), on="year", how="left")
    yr["year"] = yr["year"].astype(int)
    yr.to_csv(RESULTS / "recall_by_year.csv", index=False)

    # Undated English (big sample) by scam type: 2012 model.
    ut = recall_table(undated, "scam_type", ["rule", "word_2012", "word_fixed"])
    ut.sort_values("n", ascending=False).to_csv(RESULTS / "recall_by_scam_type_undated.csv", index=False)

    # Non-English per language (top 10 by n).
    top_lang = nonen["language"].value_counts().head(10).index
    nl = nonen[nonen["language"].isin(top_lang)].groupby("language").agg(
        n=("norm", "size"), recall_raw_word_2012=("pred_raw_word_2012", "mean"),
        recall_translation_word_2012=("pred_tr_word_2012", "mean"),
        recall_raw_word_fixed=("pred_raw_word_fixed", "mean"),
        recall_translation_word_fixed=("pred_tr_word_fixed", "mean")).round(4).sort_values("n", ascending=False)
    nl.reset_index().to_csv(RESULTS / "nonenglish_by_language.csv", index=False)

    # Benign twins per category.
    for n in ["word_2012", "word_fixed", "char_2012", "char_fixed"]:
        twins["flag_" + n] = (twins["p_" + n] >= thresholds[n]["threshold"]).astype(int)
    twins["flag_rule"] = rule_flag(twins["norm"])
    tw = twins.groupby(["label", "category"]).agg(n=("text", "size"), flag_rule=("flag_rule", "mean"),
                                                  flag_word_2012=("flag_word_2012", "mean"),
                                                  flag_word_fixed=("flag_word_fixed", "mean"),
                                                  flag_char_fixed=("flag_char_fixed", "mean")).round(4).reset_index()
    tw.to_csv(RESULTS / "benign_twins_by_category.csv", index=False)
    twins[["text", "label", "category", "p_word_2012", "p_word_fixed", "flag_word_2012", "flag_word_fixed"]].round(4)\
        .to_csv(RESULTS / "benign_twins_predictions.csv", index=False)

    # Failure analysis: misses of the fixed word model on the late test + false alarms.
    th_fx = thresholds["word_fixed"]["threshold"]
    miss = late[late["pred_word_fixed"] == 0].sort_values("p_word_fixed").copy()
    miss["auto_reason"] = [hypothesis_for_miss(n, s) for n, s in zip(miss["norm"], miss["scam_type"])]
    miss[["year", "scam_type", "p_word_fixed", "text", "auto_reason"]].round(4)\
        .to_csv(RESULTS / "fixed_model_missed_scams.csv", index=False)
    fa_rows = pd.concat([
        uci_te[(uci_te["label"] == 0) & (uci_te["p_word_fixed"] >= th_fx)].assign(source="uci_test_ham"),
        twins[(twins["label"] == 0) & (twins["p_word_fixed"] >= th_fx)].assign(source="benign_twins")])
    fa_rows = fa_rows.sort_values("p_word_fixed", ascending=False)
    fa_rows["top_scam_words"] = [", ".join(w for w, _ in explain(models["word_fixed"], n)) for n in fa_rows["norm"]]
    fa_rows["auto_reason"] = [hypothesis_for_false_alarm(n) for n in fa_rows["norm"]]
    fa_rows[["source", "p_word_fixed", "text", "top_scam_words", "auto_reason"]].round(4)\
        .to_csv(RESULTS / "fixed_model_false_alarms.csv", index=False)
    model_cmp = pd.DataFrame([
        {"model": n, "trained_on": ("UCI train only" if n.endswith("2012") else "UCI train + modern scams <= " + str(TRAIN_LAST_YEAR)),
         "threshold": thresholds[n]["threshold"], **{"uci_" + k: v for k, v in M["uci_test"][n]["at_threshold"].items()
                                                    if k in ("precision", "recall", "f1", "false_alarm_rate")},
         "modern_late_recall": M["modern_late_test"][n]["recall_at_threshold"],
         "modern_undated_recall": M["modern_undated"][n]["recall_at_threshold"],
         "twins_false_alarm_rate": M["benign_twins"][n]["at_threshold"]["false_alarm_rate"],
         "twins_scam_recall": M["benign_twins"][n]["at_threshold"]["recall"]} for n in models])
    model_cmp.to_csv(RESULTS / "model_comparison.csv", index=False)

    # Figure 1: recall by scam type on the late test (word models).
    st_plot = st[st["n"] >= 5]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(st_plot)); w = 0.38
    ax.bar(x - w / 2 - 0.01, st_plot["recall_word_2012"], w, color=C12, label="2012 model (UCI only)")
    ax.bar(x + w / 2 + 0.01, st_plot["recall_word_fixed"], w, color=CFX, label=f"Fixed model (+ scams <= {TRAIN_LAST_YEAR})")
    ax.set_xticks(x, [f"{t}\n(n={n})" for t, n in zip(st_plot["scam_type"], st_plot["n"])], fontsize=8)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Recall (share of scams caught)")
    ax.set_title(f"Scams caught, by type: English scams dated {TRAIN_LAST_YEAR + 1}+ (held-out)", loc="left")
    ax.yaxis.grid(True, color="#e6e5e0", lw=0.8); ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, -0.18), ncol=2)
    fig.tight_layout(); fig.savefig(FIGURES / "recall_by_scam_type.png", dpi=150); plt.close(fig)

    # Figure 2: recall by year (drift).
    yp = yr[yr["n"] >= 30]  # years with fewer than 30 dated rows are not plotted
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(yp["year"], yp["recall_word_2012"], "-o", color=C12, lw=2, ms=6, label="2012 model (UCI only)")
    yf = yp.dropna(subset=["recall_word_fixed"])
    ax.plot(yf["year"], yf["recall_word_fixed"], "-o", color=CFX, lw=2, ms=6, label="Fixed model (test years only)")
    ax.axvline(TRAIN_LAST_YEAR + 0.5, color=MUTED, lw=1, ls="--")
    ax.text(TRAIN_LAST_YEAR + 0.55, 0.04, "time split: train | test", color=MUTED, fontsize=8)
    for _, r in yp.iterrows():
        ax.text(r["year"], -0.09, f"n={int(r['n'])}", ha="center", fontsize=7, color=MUTED)
    ax.set_ylim(-0.12, 1.05); ax.set_ylabel("Recall"); ax.set_xticks(yp["year"])
    ax.set_title("Scam recall by year of the report (English, dated rows)", loc="left")
    ax.yaxis.grid(True, color="#e6e5e0", lw=0.8); ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1, 0.1))
    fig.tight_layout(); fig.savefig(FIGURES / "recall_by_year.png", dpi=150); plt.close(fig)

    # Figure 3: confusion matrices (UCI test and benign twins, word models at chosen threshold).
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.2))
    panels = [("UCI test: 2012", uci_te["label"], uci_te["p_word_2012"] >= thresholds["word_2012"]["threshold"]),
              ("UCI test: fixed", uci_te["label"], uci_te["p_word_fixed"] >= th_fx),
              ("Benign twins: 2012", twins["label"], twins["flag_word_2012"] == 1),
              ("Benign twins: fixed", twins["label"], twins["flag_word_fixed"] == 1)]
    for ax, (title, yt, yp_) in zip(axes, panels):
        yt = np.asarray(yt); yp_ = np.asarray(yp_).astype(int)
        cm = np.array([[((yt == a) & (yp_ == b)).sum() for b in (0, 1)] for a in (0, 1)])
        ax.imshow(cm, cmap="Blues", vmin=0, vmax=max(cm.max(), 1) * 1.3)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", color=INK, fontsize=11)
        ax.set_xticks([0, 1], ["pred safe", "pred scam"]); ax.set_yticks([0, 1], ["true safe", "true scam"])
        ax.set_title(title, fontsize=10)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.tight_layout(); fig.savefig(FIGURES / "confusion_matrices.png", dpi=150); plt.close(fig)

    # Figure 4: precision-recall curve on UCI test.
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for n, c, ls in [("word_2012", C12, "-"), ("word_fixed", CFX, "-"), ("char_2012", C12, ":"), ("char_fixed", CFX, ":")]:
        pr, rc, _ = precision_recall_curve(uci_te["label"], uci_te["p_" + n])
        ax.plot(rc, pr, color=c, ls=ls, lw=2, label=n)
    r = M["baselines"]["rule_url_or_urgency"]["uci_test"]
    ax.plot([r["recall"]], [r["precision"]], "s", color=MUTED, ms=8, label="rule baseline")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision"); ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02)
    ax.set_title("Precision-recall on UCI test (2012-era messages)", loc="left")
    ax.yaxis.grid(True, color="#e6e5e0", lw=0.8); ax.legend(frameon=False, loc="lower left")
    fig.tight_layout(); fig.savefig(FIGURES / "pr_curve_uci.png", dpi=150); plt.close(fig)
    # Figure 5 (trade-off) is drawn by step_v2_figures with the v2 variants (post-deadline v2).
    return {"recall_by_scam_type_late": st.to_dict(orient="records"),
            "recall_by_year": yr.to_dict(orient="records"),
            "by_length_bucket": lb.to_dict(orient="records"),
            "nonenglish_by_language": nl.reset_index().to_dict(orient="records"),
            "benign_twins_by_category": tw.to_dict(orient="records"),
            "fixed_model_missed_late_n": int(len(miss)),
            "fixed_model_false_alarms_n": {"uci_test_ham": int((fa_rows["source"] == "uci_test_ham").sum()),
                                           "benign_twins": int((fa_rows["source"] == "benign_twins").sum())}}


# ---------------------------------------------------------------------------
# 6. v2 additions: post-deadline v2 (Nov 18). docs/V2_SPEC.md items 1-10.
#    Every v1 key in metrics.json is unchanged; all v2 results live under metrics["v2"].
# ---------------------------------------------------------------------------
V2_LABEL = "post-deadline v2 (Nov 18)"
ASSUMED_PREVALENCE = 0.05          # ASSUMPTION for prevalence-adjusted precision and the selection cost
FA_BUDGET = 0.10                   # false-alarm budget for the alternative threshold rule (training data only)
CLUSTER_COSINE = 0.8               # char_wb 3-5 TF-IDF cosine for template clusters
EXTRA = DATA_RAW / "extra"
EXTRA_URLS = {
    "india": "https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-sample-10k/resolve/"
             "2b6de4910ab9337a92f1b672d2de8ed11c6a3805/sample_10k.csv",
    "moz": "https://huggingface.co/datasets/MOZNLP/MOZ-Smishing/resolve/"
           "1092f9d9a545b29ae6be030ee9713b615fc2d987/test.csv",
}
DLT_SENDER = r"^[A-Z]{2}-?[A-Za-z0-9]{5,6}(?:-[A-Z])?$"   # Indian TRAI business header, e.g. VM-SCBANK

# Tier rules (V2_SPEC item 10). The rules work on the raw text and on the normalised text.
_CODE_REQ_RE = re.compile(
    r"\b(?:send|share|tell|give|forward|provide|text|reply with|read out|pass on)\b(?:\s+\S+){0,3}?\s+"
    r"(?:the\s+|that\s+|your\s+|this\s+)?(?:code|pin|password|passcode|otp|one[- ]time code|verification code)\b", re.I)
_NEGATION_RE = re.compile(r"\b(?:never|not|don'?t|do not|no one|nobody|without)\b[^.!?]{0,40}$", re.I)
_FAMILY_OPENER_RE = re.compile(
    r"^\W*(?:hi|hello|hey|hiya)?\W*(?:mum|mom|mam|mummy|mommy|dad|daddy)\b"
    r"|\b(?:my new number|this is my new number|new phone number|lost my phone|broke my phone|"
    r"(?:my )?phone (?:is )?broken|dropped my phone|changed my number|wrong number)\b", re.I)
TIER_LABELS = {"RED": "Likely scam - do not tap, do not reply",
               "YELLOW": "Ask family before replying",
               "GREEN": "No warning signs found"}

# Safety rules (post-deadline v3, Nov 18). Not learned: fixed patterns for messages the SMS-scam model never saw,
# e.g. luring with money ("I will give you money ... come to my car"). Measured in tools/safety_rules_eval.py.
_MONEY_OFFER_RE = re.compile(
    r"\b(?:i(?:'ll| will| can)?|we(?:'ll| will)?)\s+(?:give|send|pay|offer)\s+(?:you|u)\b[^.!?]{0,40}"
    r"(?:money|cash|\$\s?\d|\d+\s*(?:dollars?|usd|bucks)|gift ?cards?|reward|prize)"
    r"|\byou(?:'ve| have)?\s+(?:just\s+)?won\b|\bfree\s+(?:money|cash|gift ?cards?)\b"
    r"|\b(?:easy|quick|fast)\s+(?:money|cash)\b", re.I)
_MEET_RE = re.compile(
    r"\b(?:come|get|hop|step)\s+(?:in(?:to)?|to|over to|inside)\s+(?:my|the|our|this)\s+(?:car|van|truck|house|place|room|hotel)\b"
    r"|\bmeet\s+(?:me|up)\b|\bcome\s+(?:with|outside|alone)\b|\b(?:i'?ll|i will)\s+pick\s+(?:you|u)\s+up\b", re.I)
_MINOR_RE = re.compile(r"\b(?:young|little)\s+(?:child|children|kid|kids|girl|girls|boy|boys)\b|\b(?:child|kid)\b", re.I)
_SECRECY_RE = re.compile(r"\b(?:don'?t|do not|never)\s+tell\s+(?:your|anyone|anybody|mom|mum|dad|parents)\b|\bour (?:little )?secret\b", re.I)


# Grooming-warning categories (general child-safety guidance: secrecy, isolation, personal-info and image requests,
# moving to private apps, gifts for contact, offline meeting). Each category is a loose pattern; RED needs 2 categories
# (or money+meeting) so a single ordinary phrase ("come to the car", "meet me at the mall") stays GREEN.
_GROOM = {
    "secrecy": r"\b(?:don'?t|dont|do not|never|no need to|dont need to|don'?t have to)\s+(?:tell|let)\b|\b(?:our|a) (?:little )?secret\b"
               r"|\bbetween (?:u|you) (?:n|and) me\b|\bkeep (?:this|it|our \w+) (?:private|secret|between)\b|\bdelete (?:these|this|the) (?:msgs?|messages?|texts?|chats?)\b"
               r"|\b(?:no ?one|nobody|noone) (?:else )?(?:knows|has to know|needs to know)\b|\bi won'?t tell\b|\b(?:parents|mom|mum|dad|folks)\b[^.!?]{0,20}\b(?:need to know|dont need|don'?t have to)\b",
    "isolation": r"\b(?:are|r) (?:u|you) (?:home )?(?:alone|by (?:ur|your)self)\b|\bis (?:ur|your) (?:mom|mum|dad|parents?|folks)\b[^.!?]{0,15}\bhome\b|\bjust (?:us|u and me|you and me)\b|\b(?:sneak|slip) out\b|\b(?:alone|by urself|by yourself)\b",
    "personal_info": r"\b(?:wh?at|which) (?:street|school|address|grade)\b|\b(?:ur|your) (?:address|house|school)\b[^.!?]{0,25}\b(?:find|come|drop|mail|wait|pick)\b|\bwhats? (?:ur|your) address\b|\bhow old (?:r|are) (?:u|you)\b|\bwhere do (?:u|you) live\b",
    "images": r"\b(?:send|snap|take)\b[^.!?]{0,20}\b(?:pic|pics|picture|photo|selfie|video)\b|\bvideo ?chat\b",
    "platform_move": r"\b(?:add me on|move to|switch to|talk on)\b[^.!?]{0,15}\b(?:snap|snapchat|insta|instagram|discord|telegram|whatsapp|kik|a diff(?:erent)? app|another app)\b|\bthis (?:app|one) reads\b",
    "gift": r"\b(?:i'?ll|ill|i will|i can|i could|i'd)\s+(?:buy|get|give|send|pay|venmo|cashapp)\b[^.!?]{0,30}\b(?:u|you|ur|your)\b|\b(?:free|extra)\s+(?:robux|v-?bucks|gift ?cards?|codes|skins)\b|\bnew (?:phone|console|controller)\b",
    "meeting": r"\bmeet (?:me|up)\b|\b(?:pick|drive) (?:u|you) (?:up|home)\b|\bhop in\b|\bneed a ride\b|\b(?:come|wanna) (?:over|hang|grab)\b|\bcome (?:to|into|in) my (?:car|van|place|house)\b|\bwait (?:at|for u|for you)\b|\bi might b(?:e)? in the area\b|\bdrop off\b",
    "flattery_wedge": r"\b(?:cooler|more mature|smarter) than (?:other )?(?:kids|people)\b|\b(?:parents|mom|dad|folks)\b[^.!?]{0,15}\b(?:too strict|wouldn'?t (?:get|understand))\b|\bi would treat (?:u|you)\b",
}
_GROOM_RE = {k: re.compile(v, re.I) for k, v in _GROOM.items()}
_MINOR_RE2 = re.compile(r"\b(?:young|little)\s+(?:child|children|kid|kids|girl|girls|boy|boys)\b|\bafter school\b|\bschool uniform\b", re.I)


def grooming_categories(text: str) -> list[str]:
    return [k for k, r in _GROOM_RE.items() if r.search(text or "")]


def safety_reasons(text: str) -> list[str]:
    """RED-level safety concerns: >= 2 grooming-warning categories, money/gift + meeting, or a child mention plus any
    category. Hand-written rules (not learned); evaluated in tools/safety_rules_eval.py."""
    t = text or ""
    cats = grooming_categories(t)
    money = bool(_MONEY_OFFER_RE.search(t)) or "gift" in cats
    out = []
    if len(cats) >= 2 or (money and "meeting" in cats) or (bool(_MEET_RE.search(t)) and bool(_MONEY_OFFER_RE.search(t))):
        out.append("shows warning signs of grooming or luring (" + ", ".join(c.replace("_", " ") for c in cats) + ")")
    elif cats and (_MINOR_RE.search(t) or _MINOR_RE2.search(t)):
        out.append("mentions a child together with a warning sign (" + ", ".join(c.replace("_", " ") for c in cats) + ")")
    return out


def money_offer_reasons(text: str) -> list[str]:
    """YELLOW: an unsolicited offer of money or a prize."""
    return ["offers you money or a prize out of the blue"] if _MONEY_OFFER_RE.search(text or "") else []


def rule_reasons(text: str, norm: str | None = None) -> list[str]:
    """Fixed YELLOW rules: a request for a code/PIN/password (not a 'never share' warning),
    or a 'hi mum / new number / wrong number' opener."""
    out = []
    for t in (text or "", norm or ""):
        for m in _CODE_REQ_RE.finditer(t):
            if not _NEGATION_RE.search(t[max(0, m.start() - 60):m.start()]):
                out.append("asks you to share a code, PIN or password"); break
        if _FAMILY_OPENER_RE.search(t.strip()):
            out.append("starts like a 'new number / wrong number / hi mum' message")
    return sorted(set(out))


def occlusion_words(model, norm_text: str, k: int = 5):
    """Words whose removal lowers the scam probability most (works for word and char models).
    Returns [(plain-language word, probability drop)], positive drops only."""
    toks = norm_text.split()
    uniq = list(dict.fromkeys(toks))
    if not uniq:
        return []
    variants = [" ".join(t for t in toks if t != u) for u in uniq]
    p = model.predict_proba([norm_text] + variants)[:, 1]
    out = [(FRIENDLY_TOKENS.get(u, u), float(p[0] - pv)) for u, pv in zip(uniq, p[1:])]
    out = [o for o in out if o[1] > 0]
    out.sort(key=lambda o: -o[1])
    return out[:k]


def triage_tier(p: float, threshold: float, norm: str, text: str = "") -> str:
    """Three-tier, warn-only verdict (V2_SPEC item 10).
    RED    = model flags AND (link or phone token)
    YELLOW = model flags with no link/phone, OR a fixed rule fires (code request, family/new-number opener)
    GREEN  = otherwise ("No warning signs found", never "safe")."""
    flag = p >= threshold
    contact = ("tok_url" in norm) or ("tok_phone" in norm)
    if (flag and contact) or safety_reasons(text):
        return "RED"
    if flag or rule_reasons(text, norm) or money_offer_reasons(text) or grooming_categories(text):
        return "YELLOW"
    return "GREEN"


def _key(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def load_extra_benign() -> pd.DataFrame:
    """Real modern legitimate SMS (docs/EXTRA_DATA.md): India inbox (English business SMS) + MOZ (Portuguese).
    Local file first, pinned Hugging Face revision as fallback. Raw texts are never printed or saved."""
    import io

    def _read(local, url):
        p = EXTRA / local
        return pd.read_csv(p if p.exists() else url)
    uci_txt = [ln.split("\t", 1)[1] for ln in _read_text(UCI_PATH).splitlines() if "\t" in ln]
    imc = pd.read_csv(io.StringIO(_read_text(IMC_PATH)))
    ban = {_key(t) for t in uci_txt} | {_key(t) for t in pd.concat([imc["text"].dropna(), imc["translation"].dropna()])}
    a = _read("gandharvbakshi_sms_sample_10k.csv", EXTRA_URLS["india"])
    a = a[(a["classification_status"] != "synthetic") & a["sender"].fillna("").str.match(DLT_SENDER)]
    a = a.assign(text=a["sms_text"].astype(str), source="india_inbox", sender=a["sender"])
    b = _read("moz_smishing.csv", EXTRA_URLS["moz"])
    b = b[(b["label"] == "Legitimate") & (b["source"] == "sms")]
    b = b.assign(text=b["text"].astype(str), source="moz_pt", sender=None)
    out = pd.concat([a[["text", "source", "sender"]], b[["text", "source", "sender"]]], ignore_index=True)
    out["k"] = out["text"].map(_key)
    out = out[~out["k"].isin(ban)].drop_duplicates("k").drop(columns="k").reset_index(drop=True)
    out["norm"] = out["text"].map(normalise)
    out["brand"] = (out["sender"].fillna("").str.replace(r"^[A-Z]{2}-?", "", regex=True)
                    .str.replace(r"-[A-Z]$", "", regex=True).str.upper())
    out["label"] = 0
    return out


def char_clusters(texts, cut: float = CLUSTER_COSINE) -> np.ndarray:
    """Connected components of the graph 'char_wb 3-5 TF-IDF cosine > cut'."""
    from scipy.sparse.csgraph import connected_components
    from sklearn.feature_extraction.text import TfidfVectorizer
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(list(texts))
    S = (X @ X.T).tocsr()
    S.data = (S.data > cut).astype(np.int8)
    S.eliminate_zeros()
    return connected_components(S, directed=False)[1]


def merge_groups(*labels) -> np.ndarray:
    """Rows that share ANY label (e.g. same brand OR same template cluster) end up in one group."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(labels[0]); rows, cols, off = [], [], n
    for lab in labels:
        codes, uniq = pd.factorize(pd.Series(list(lab)).astype(str))
        rows.extend(range(n)); cols.extend(off + codes); off += len(uniq)
    A = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(off, off))
    return connected_components(A, directed=False)[1][:n]


def strip_placeholders(s: pd.Series | np.ndarray):
    f = lambda t: _WS_RE.sub(" ", re.sub(r"\btok_\w+\b", " ", t)).strip()  # noqa: E731
    return np.array([f(t) for t in s], dtype=object)


def oof_proba_v2(make_model, X, y, groups=None, n_splits=5) -> np.ndarray:
    """Out-of-fold probabilities. With groups (India brand+template groups), folds never split a group."""
    if groups is None:
        return oof_proba(make_model, X, y, n_splits)
    from sklearn.model_selection import StratifiedGroupKFold
    p = np.zeros(len(y))
    for tr, va in StratifiedGroupKFold(n_splits, shuffle=True, random_state=SEED).split(X, y, groups):
        p[va] = make_model().fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
    return p


def fa_budget_threshold(p_neg, budget: float = FA_BUDGET) -> float:
    """Lowest threshold (0.01 grid) whose out-of-fold false-alarm rate on the given negatives is <= budget."""
    for th in np.round(np.arange(0.02, 0.99, 0.01), 2):
        if (np.asarray(p_neg) >= th).mean() <= budget:
            return float(th)
    return 0.99


def ppv_at(recall, far, prev: float = ASSUMED_PREVALENCE):
    if recall is None or far is None:
        return None
    den = recall * prev + far * (1 - prev)
    return _r(recall * prev / den) if den > 0 else None


def step_v2_data(d):
    """Real modern ham split, synthetic-benign split, cluster-safe split (V2 items 1, 4, 9)."""
    from sklearn.model_selection import GroupShuffleSplit
    V = {}
    xb = load_extra_benign()
    india = xb[xb["source"] == "india_inbox"].reset_index(drop=True)
    moz = xb[xb["source"] == "moz_pt"].reset_index(drop=True)
    india["cluster"] = char_clusters(india["norm"])
    india["group"] = merge_groups(india["brand"], india["cluster"])
    tr_i, te_i = next(GroupShuffleSplit(1, test_size=0.5, random_state=SEED).split(india, groups=india["group"]))
    ind_tr, ind_te = india.iloc[tr_i].reset_index(drop=True), india.iloc[te_i].reset_index(drop=True)
    # Selection split inside the India training groups (for choosing the shipped model on validation data only).
    a1, a2 = next(GroupShuffleSplit(1, test_size=0.5, random_state=SEED + 1).split(ind_tr, groups=ind_tr["group"]))
    gs = india.groupby("group").size()
    V["real_ham_split"] = {
        "india_rows": int(len(india)), "moz_rows": int(len(moz)),
        "india_distinct_senders": int(india["sender"].nunique()), "india_distinct_brands": int(india["brand"].nunique()),
        "india_template_clusters_at_cosine_0.8": int(india["cluster"].nunique()),
        "india_groups_brand_or_cluster": int(india["group"].nunique()), "india_largest_group_rows": int(gs.max()),
        "india_train_rows": int(len(ind_tr)), "india_test_rows": int(len(ind_te)),
        "india_train_senders": int(ind_tr["sender"].nunique()), "india_test_senders": int(ind_te["sender"].nunique()),
        "india_train_brands": int(ind_tr["brand"].nunique()), "india_test_brands": int(ind_te["brand"].nunique()),
        "brands_on_both_sides": int(len(set(ind_tr["brand"]) & set(ind_te["brand"]))),
        "identical_normalised_texts_across_split": int(len(set(ind_tr["norm"]) & set(ind_te["norm"]))),
        "selection_split_inside_train_rows": [int(len(a1)), int(len(a2))],
        "rule": "India rows grouped by brand (sender header without operator prefix) OR char-n-gram template cluster "
                "(cosine > 0.8); GroupShuffleSplit 50/50 seed 42. MOZ is never trained on.",
        "disclosure": "Both sets were looked at during exploration (Nov 17) before these numbers were final."}

    # Synthetic legit twins: split by category (phrasing-disjoint), seeded. Scam twins are never trained on.
    tw = d["twins"]
    cats = sorted(tw["category"].unique())
    train_cats = sorted(np.random.RandomState(SEED).choice(cats, len(cats) // 2, replace=False).tolist())
    syn_tr = tw[(tw["label"] == 0) & tw["category"].isin(train_cats)].reset_index(drop=True)
    syn_te = tw[(tw["label"] == 0) & ~tw["category"].isin(train_cats)].reset_index(drop=True)
    syn_scam = tw[tw["label"] == 1].reset_index(drop=True)
    V["synthetic_split"] = {"label": "synthetic stress test, written with AI assistance",
                            "train_categories": train_cats, "test_categories": [c for c in cats if c not in train_cats],
                            "train_legit_n": int(len(syn_tr)), "test_legit_n": int(len(syn_te)),
                            "scam_twins_n_test_only": int(len(syn_scam))}

    # Cluster-safe split of dated English scams (item 4).
    dated = pd.concat([d["early"].assign(split="early"), d["late"].assign(split="late")], ignore_index=True)
    dated["cluster"] = char_clusters(dated["norm"])
    first = dated.groupby("cluster")["year"].min()
    dated["cluster_first_year"] = dated["cluster"].map(first)
    late_mask = (dated["split"] == "late").to_numpy()
    safe = late_mask & (dated["cluster_first_year"] > TRAIN_LAST_YEAR).to_numpy()
    cl_late = set(dated.loc[late_mask, "cluster"]); cl_early = set(dated.loc[~late_mask, "cluster"])
    late_safe_norms = set(dated.loc[safe, "norm"])
    late = d["late"]
    V["cluster_safe_split"] = {
        "rule": "char_wb 3-5 TF-IDF, cosine > 0.8, connected components over all dated English scams; cluster date = "
                "first report year; clusters first seen <= 2021 are training-side; 2022+ test rows in those clusters "
                "are removed from the test",
        "dated_rows": int(len(dated)), "clusters_total": int(dated["cluster"].nunique()),
        "clusters_train_side": int((first <= TRAIN_LAST_YEAR).sum()), "clusters_test_side": int((first > TRAIN_LAST_YEAR).sum()),
        "clusters_spanning_the_cut": int(len(cl_late & cl_early)),
        "largest_cluster_rows": int(dated.groupby("cluster").size().max()),
        "late_test_rows_before": int(late_mask.sum()), "late_test_rows_removed": int(late_mask.sum() - safe.sum()),
        "late_test_rows_cluster_safe": int(safe.sum()),
        "training_rows_unchanged": int((~late_mask).sum())}
    late_safe = late[late["norm"].isin(late_safe_norms)].reset_index(drop=True)
    return {"india": india, "ind_tr": ind_tr, "ind_te": ind_te, "ind_a1": ind_tr.iloc[a1].reset_index(drop=True),
            "ind_a2": ind_tr.iloc[a2].reset_index(drop=True), "moz": moz, "syn_tr": syn_tr, "syn_te": syn_te,
            "syn_scam": syn_scam, "late_safe": late_safe, "dated": dated}, V


def _training_set(d, early_norm, india_tr=None, syn_tr=None, strip=False):
    """UCI train + early modern scams (+ India train ham) (+ synthetic train-half legit). Returns X, y, groups."""
    X = [d["uci_tr"]["norm"].to_numpy(dtype=object), np.asarray(early_norm, dtype=object)]
    y = [d["uci_tr"]["label"].to_numpy(), np.ones(len(early_norm), dtype=int)]
    g = [np.arange(len(X[0])) + 10_000_000, np.arange(len(X[1])) + 20_000_000]
    if india_tr is not None:
        X.append(india_tr["norm"].to_numpy(dtype=object)); y.append(np.zeros(len(india_tr), dtype=int))
        g.append(india_tr["group"].to_numpy())
    if syn_tr is not None:
        X.append(syn_tr["norm"].to_numpy(dtype=object)); y.append(np.zeros(len(syn_tr), dtype=int))
        g.append(np.full(len(syn_tr), 30_000_000) + pd.factorize(syn_tr["category"])[0])
    X = np.concatenate(X); y = np.concatenate(y); g = np.concatenate(g)
    if strip:
        X = strip_placeholders(X)
    return X, y, (g if (india_tr is not None or syn_tr is not None) else None)


V2_VARIANTS = {
    # name: (maker, uses India train ham, uses synthetic train half, description)
    "fix_plus_benign": ("word", False, True, "UCI train + scams <= 2021 + synthetic legit (train half, 3 categories)"),
    "char_fix_plus_benign": ("char", False, True, "char n-gram model; UCI train + scams <= 2021 + synthetic legit (train half)"),
    "fix_plus_real_ham": ("word", True, False, "UCI train + scams <= 2021 + real India legit SMS (train brand groups)"),
    "char_fix_plus_real_ham": ("char", True, False, "char n-gram model; UCI train + scams <= 2021 + real India legit SMS (train brand groups)"),
    "fix_plus_real_ham_and_benign": ("word", True, True, "fix_plus_real_ham + synthetic legit train half"),
}
MAKERS = {"word": make_word_model, "char": make_char_model}


def step_v2_train(d, D, models, thresholds):
    """Train v2 variants. Thresholds: same 5:1 cost rule on out-of-fold predictions (group-aware folds when
    India rows are in training). Also the alternative false-alarm-budget threshold (item 9b-ii)."""
    for name, (kind, use_ind, use_syn, desc) in V2_VARIANTS.items():
        X, y, g = _training_set(d, d["early"]["norm"], D["ind_tr"] if use_ind else None,
                                D["syn_tr"] if use_syn else None)
        p = oof_proba_v2(MAKERS[kind], X, y, g)
        thresholds[name] = pick_threshold(y, p)
        thresholds[name].update({"validation": "5-fold out-of-fold predictions on this model's training data"
                                 + (" (StratifiedGroupKFold: India brand/template groups never split)" if g is not None else ""),
                                 "validation_n": int(len(y)), "validation_scam_n": int(y.sum()), "trained_on": desc})
        if use_ind:
            n_ind = len(D["ind_tr"]); start = len(d["uci_tr"]) + len(d["early"])
            thresholds[name]["fa_budget_threshold"] = fa_budget_threshold(p[start:start + n_ind])
            thresholds[name]["fa_budget_rule"] = f"lowest threshold with out-of-fold false alarms <= {FA_BUDGET:.0%} on India-train legit"
        models[name] = MAKERS[kind]().fit(X, y)
    return models, thresholds


def _evalsets(d, D):
    return {"uci_te": d["uci_te"], "late": d["late"], "late_safe": D["late_safe"], "undated": d["undated"],
            "syn_te": D["syn_te"], "syn_all": d["twins"][d["twins"]["label"] == 0], "syn_scam": D["syn_scam"],
            "ind_te": D["ind_te"], "ind_all": D["india"], "moz": D["moz"]}


def v2_eval(flag_fn, E, trained_on_india=False, trained_on_syn=False):
    """flag_fn(norm_series) -> 0/1 array. Returns the standard v2 row for one model or rule."""
    f = lambda df: np.asarray(flag_fn(df["norm"])).astype(int)  # noqa: E731
    uci = E["uci_te"]; yte = uci["label"].to_numpy()
    r = {"uci_test": prf(yte, f(uci)), "late_recall": rate_ci(f(E["late"])),
         "late_cluster_safe_recall": rate_ci(f(E["late_safe"])), "undated_recall": rate_ci(f(E["undated"])),
         "synthetic_legit_heldout_false_alarms": rate_ci(f(E["syn_te"])),
         "synthetic_legit_all60_false_alarms": None if trained_on_syn else rate_ci(f(E["syn_all"])),
         "synthetic_scam_twins_recall": rate_ci(f(E["syn_scam"])),
         "india_heldout_false_alarms": rate_ci(f(E["ind_te"])),
         "india_all_false_alarms": None if trained_on_india else rate_ci(f(E["ind_all"])),
         "moz_false_alarms": rate_ci(f(E["moz"]))}
    fl = f(E["ind_te"])
    r["india_heldout_flagged_distinct_senders"] = int(E["ind_te"].loc[fl == 1, "sender"].nunique())
    R = r["late_recall"]["rate"]
    r["prevalence_adjusted_precision_assumed_5pct"] = {
        "assumption": "5% of incoming texts are scams (ASSUMED, not measured); recall = 2022-24 test recall",
        "vs_uci_test_ham": ppv_at(R, r["uci_test"]["false_alarm_rate"]),
        "vs_synthetic_heldout": ppv_at(R, r["synthetic_legit_heldout_false_alarms"]["rate"]),
        "vs_india_heldout": ppv_at(R, r["india_heldout_false_alarms"]["rate"]),
        "vs_moz": ppv_at(R, r["moz_false_alarms"]["rate"])}
    return r


def step_v2_compare(d, D, models, thresholds):
    """Items 1, 2, 3, 9: every model and rule on every set."""
    E = _evalsets(d, D)
    out = {}
    rules = {"rule_url_or_urgency": rule_flag, "rule_link_only": link_flag,
             "rule_link_or_phone": lambda s: np.array([("tok_url" in t) or ("tok_phone" in t) for t in s], dtype=int)}
    for n, fn in rules.items():
        out[n] = v2_eval(fn, E)
    for n, m in models.items():
        th = thresholds[n]["threshold"]
        ind = V2_VARIANTS.get(n, (None, False, False))[1]; syn = V2_VARIANTS.get(n, (None, False, False))[2]
        out[n] = v2_eval(lambda s, m=m, th=th: m.predict_proba(s)[:, 1] >= th, E, ind, syn)
        out[n]["threshold"] = th
        if "fa_budget_threshold" in thresholds[n]:
            tb = thresholds[n]["fa_budget_threshold"]
            out[n + "@fa_budget"] = v2_eval(lambda s, m=m, tb=tb: m.predict_proba(s)[:, 1] >= tb, E, ind, syn)
            out[n + "@fa_budget"]["threshold"] = tb
    return out


def step_v2_ablation_and_confound(d, D, cmp):
    """Item 2: placeholder-token ablation. Item 1: source-separation AUCs."""
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    E = _evalsets(d, D)
    E_strip = {k: v.assign(norm=strip_placeholders(v["norm"])) for k, v in E.items()}
    out = {"what": "every tok_* placeholder (url, phone, email, money, date, num) removed from train and test texts; "
                   "models retrained; thresholds re-chosen by the same out-of-fold cost rule"}
    for name, ind in [("word_fixed", False), ("fix_plus_real_ham", True)]:
        X, y, g = _training_set(d, d["early"]["norm"], D["ind_tr"] if ind else None, None, strip=True)
        th = pick_threshold(y, oof_proba_v2(make_word_model, X, y, g))["threshold"]
        m = make_word_model().fit(X, y)
        r = v2_eval(lambda s: m.predict_proba(s)[:, 1] >= th, E_strip, ind, False); r["threshold"] = th
        base = cmp[name]
        r["change_vs_with_placeholders"] = {
            k: _r(r[k]["rate"] - base[k]["rate"]) for k in
            ["late_recall", "synthetic_legit_heldout_false_alarms", "india_heldout_false_alarms", "moz_false_alarms"]}
        out[name + "_no_placeholders"] = r
    # Source separation (after normalisation): can a model tell the two sources apart?
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    def auc(a, b):
        X = np.array(list(a) + list(b), dtype=object); y = np.array([0] * len(a) + [1] * len(b))
        p = cross_val_predict(make_word_model(), X, y, cv=cv, method="predict_proba")[:, 1]
        return {"n_a": len(a), "n_b": len(b), "cv_roc_auc": _r(roc_auc_score(y, p))}
    uci = d["uci"]
    conf = {"uci_spam_vs_modern_scam": "see shortcut_check.cv_roc_auc (v1 key)",
            "uci_ham_vs_real_india_legit": auc(uci.loc[uci["label"] == 0, "norm"].sample(len(D["india"]), random_state=SEED),
                                               D["india"]["norm"]),
            "real_india_legit_vs_modern_scam": auc(D["india"]["norm"],
                                                   pd.concat([d["early"], d["late"]])["norm"].sample(len(D["india"]), random_state=SEED)),
            "reading_rule": "AUC near 0.5 = sources hard to tell apart; near 1.0 = easy (a shortcut a model can learn)"}
    return out, conf


def step_v2_half_life(d, models, thresholds, M, near):
    """Item 5: time zero = UCI test spam recall of the 2012 model; recall per report-date cohort; per top-3 scam type;
    rolling training cutoffs (train on UCI + English scams <= Y, test on later years)."""
    th12 = thresholds["word_2012"]["threshold"]
    dated = pd.concat([d["early"], d["late"]], ignore_index=True)
    dated["flag"] = (models["word_2012"].predict_proba(dated["norm"])[:, 1] >= th12).astype(int)
    rows = []
    for y, g in dated.groupby("year"):
        rows.append({"year": int(y), "n": int(len(g)), "recall_word_2012": _r(g["flag"].mean()),
                     "ci95": wilson(g["flag"].sum(), len(g)), "years_since_2012": int(y) - 2012})
    top3 = dated["scam_type"].value_counts().head(3).index.tolist()
    by_type = []
    for t in top3:
        for y, g in dated[dated["scam_type"] == t].groupby("year"):
            by_type.append({"scam_type": t, "year": int(y), "n": int(len(g)), "recall_word_2012": _r(g["flag"].mean()),
                            "ci95": wilson(g["flag"].sum(), len(g))})
    t0 = M["uci_test"]["word_2012"]["at_threshold"]
    zero = {"uci_test_spam_recall": t0["recall"], "ci95": t0["recall_ci95"], "n_spam": t0["tp"] + t0["fn"],
            "uci_test_spam_recall_without_near_dup_0.9": near["uci"].get("word_2012_recall_uci_test_spam_without_near_dup_0.9")}
    big = [r for r in rows if r["n"] >= 100]
    yrs = np.array([r["year"] for r in big]); rec = np.array([r["recall_word_2012"] for r in big])
    slope = float(np.polyfit(yrs, rec, 1)[0]) if len(big) >= 3 else None
    half = t0["recall"] / 2
    below = [r["year"] for r in rows if r["n"] >= 30 and r["recall_word_2012"] <= half]
    # Rolling cutoffs.
    roll = []
    X12 = d["uci_tr"]["norm"].to_numpy(dtype=object); y12 = d["uci_tr"]["label"].to_numpy()
    for Y in [2018, 2019, 2020, 2021, 2022]:
        tr = dated[dated["year"] <= Y]
        X = np.concatenate([X12, tr["norm"].to_numpy(dtype=object)]); y = np.concatenate([y12, np.ones(len(tr), int)])
        th = pick_threshold(y, oof_proba(make_word_model, X, y))["threshold"]
        m = make_word_model().fit(X, y)
        for yy, g in dated[dated["year"] > Y].groupby("year"):
            if len(g) < 30:
                continue
            f = m.predict_proba(g["norm"])[:, 1] >= th
            roll.append({"cutoff_year": Y, "test_year": int(yy), "years_since_cutoff": int(yy) - Y, "n": int(len(g)),
                         "train_modern_n": int(len(tr)), "threshold": th, "recall": _r(f.mean()), "ci95": wilson(f.sum(), len(f))})
    pd.DataFrame(rows).to_csv(RESULTS / "half_life_by_year.csv", index=False)
    pd.DataFrame(by_type).to_csv(RESULTS / "half_life_by_year_top3_types.csv", index=False)
    pd.DataFrame(roll).to_csv(RESULTS / "half_life_rolling_cutoff.csv", index=False)
    return {"label": "report-date cohorts (year shown in the reporter's screenshot, not the send date)",
            "time_zero_2012_model": zero, "by_year_word_2012": rows, "top3_scam_types": top3,
            "by_year_top3_types_word_2012": by_type,
            "linear_slope_per_year_word_2012_years_with_n_ge_100": _r(slope),
            "recall_halving_level": _r(half), "years_with_recall_at_or_below_half_of_time_zero": below,
            "half_life_years": None if not below else int(min(below)) - 2012,
            "half_life_note": ("not reached: no report-date cohort (n >= 30) falls to half of the time-zero recall"
                               if not below else "first report year at or below half of time-zero recall, minus 2012"),
            "rolling_cutoff": roll}


def step_v2_learning_curve(d, D):
    """Item 7: add 0 / 100 / 500 / 1,000 / all early scams (3 seeds for subsamples). 2,000 is not reachable:
    the early pool has fewer rows."""
    E = _evalsets(d, D)
    early = d["early"]["norm"].to_numpy(dtype=object)
    sizes = [0, 100, 500, 1000, len(early)]
    rows = []
    for base, use_ind in [("naive_fix", False), ("fix_plus_real_ham", True)]:
        for k in sizes:
            for s in ([0] if k in (0, len(early)) else [0, 1, 2]):
                idx = np.random.RandomState(SEED + s).choice(len(early), k, replace=False) if k < len(early) else np.arange(k)
                X, y, g = _training_set(d, early[idx], D["ind_tr"] if use_ind else None, None)
                th = pick_threshold(y, oof_proba_v2(make_word_model, X, y, g))["threshold"]
                m = make_word_model().fit(X, y)
                fl = lambda df: m.predict_proba(df["norm"])[:, 1] >= th  # noqa: E731
                rows.append({"base": base, "early_scams_added": int(k), "seed": SEED + s, "threshold": th,
                             "late_recall": _r(fl(E["late"]).mean()),
                             "synthetic_heldout_false_alarms": _r(fl(E["syn_te"]).mean()),
                             "india_heldout_false_alarms": _r(fl(E["ind_te"]).mean()),
                             "moz_false_alarms": _r(fl(E["moz"]).mean())})
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "learning_curve.csv", index=False)
    agg = df.groupby(["base", "early_scams_added"]).agg(
        runs=("seed", "size"), late_recall_mean=("late_recall", "mean"), late_recall_min=("late_recall", "min"),
        late_recall_max=("late_recall", "max"), synthetic_fa_mean=("synthetic_heldout_false_alarms", "mean"),
        india_fa_mean=("india_heldout_false_alarms", "mean"), moz_fa_mean=("moz_false_alarms", "mean")).round(4).reset_index()
    return {"sizes": sizes, "note": f"2,000 requested in the spec; the early pool has only {len(early)} rows, so 'all' = {len(early)}. "
                                    "Subsample sizes use 3 seeds (mean, min, max shown).",
            "runs": rows, "summary": agg.to_dict(orient="records")}


def step_v2_multilingual(d, D, models, thresholds):
    """Item 6: paired raw vs translation (oracle upper reference), OOV share, char n-gram multilingual model."""
    nonen = d["nonen"]
    out = {"translation_label": "oracle upper reference (dataset-provided English translation, not a deployed translator)"}
    paired = {}
    for n in ["word_2012", "char_2012", "word_fixed", "fix_plus_real_ham", "fix_plus_benign"]:
        m, th = models[n], thresholds[n]["threshold"]
        a = m.predict_proba(nonen["norm"])[:, 1] >= th; b = m.predict_proba(nonen["norm_tr"])[:, 1] >= th
        paired[n] = {"n": int(len(nonen)), "recall_raw": _r(a.mean()), "recall_translation_oracle": _r(b.mean()),
                     "both": int((a & b).sum()), "raw_only": int((a & ~b).sum()), "translation_only": int((~a & b).sum()),
                     "neither": int((~a & ~b).sum()),
                     "native_english_2022_24_recall": _r((m.predict_proba(d["late"]["norm"])[:, 1] >= th).mean())}
    out["paired_raw_vs_translation"] = paired
    vocab = {w for w in models["word_2012"].named_steps["tfidf"].get_feature_names_out() if " " not in w}
    def oov(series):
        toks = [[t for t in re.findall(r"(?u)\b\w+\b", s) if not t.startswith("tok_")] for s in series]
        allt = [t for ts in toks for t in ts]
        per = [np.mean([t not in vocab for t in ts]) for ts in toks if ts]
        return {"pooled_token_share": _r(np.mean([t not in vocab for t in allt])), "mean_per_message": _r(np.mean(per))}
    out["oov_share_vs_word_2012_vocabulary"] = {"nonenglish_raw": oov(nonen["norm"]), "nonenglish_translation": oov(nonen["norm_tr"]),
                                                "english_2022_24_test": oov(d["late"]["norm"]), "uci_test": oov(d["uci_te"]["norm"])}
    # Multilingual char model: UCI train + early scams in ALL languages (raw text).
    imc = load_imc()
    imc = imc[imc["text"].notna()].copy(); imc["norm"] = imc["text"].map(normalise); imc = imc[imc["norm"].str.len() > 0]
    early_ne = imc[(imc["language"] != "English") & (imc["year"] <= TRAIN_LAST_YEAR)].drop_duplicates("norm")
    E_norm = np.concatenate([d["early"]["norm"].to_numpy(dtype=object), early_ne["norm"].to_numpy(dtype=object)])
    X, y, _ = _training_set(d, E_norm)
    p = oof_proba(make_char_model, X, y)
    th = pick_threshold(y, p)["threshold"]
    mm = make_char_model().fit(X, y)
    models["char_multilingual"] = mm
    thresholds["char_multilingual"] = {**pick_threshold(y, p), "validation": "5-fold out-of-fold on training data",
                                       "trained_on": "UCI train + scams <= 2021 in all languages (raw text)"}
    test = nonen[~(nonen["year"] <= TRAIN_LAST_YEAR) & ~nonen["norm"].isin(set(early_ne["norm"]))].copy()
    for n in ["word_2012", "char_2012", "char_multilingual"]:
        test["raw_" + n] = (models[n].predict_proba(test["norm"])[:, 1] >= thresholds[n]["threshold"]).astype(int)
    test["tr_word_2012"] = (models["word_2012"].predict_proba(test["norm_tr"])[:, 1] >= thresholds["word_2012"]["threshold"]).astype(int)
    top8 = test["language"].value_counts().head(8).index
    rows = []
    for lang in top8:
        g = test[test["language"] == lang]
        rows.append({"language": lang, "n": int(len(g)),
                     **{c: _r(g[c].mean()) for c in ["raw_word_2012", "tr_word_2012", "raw_char_2012", "raw_char_multilingual"]},
                     "ci95_raw_char_multilingual": wilson(g["raw_char_multilingual"].sum(), len(g))})
    pd.DataFrame(rows).to_csv(RESULTS / "multilingual_by_language.csv", index=False)
    E = _evalsets(d, D)
    fa = lambda df: rate_ci(mm.predict_proba(df["norm"])[:, 1] >= th)  # noqa: E731
    out["char_multilingual"] = {
        "trained_on": "UCI train + English scams <= 2021 + non-English scams <= 2021 (raw text)",
        "early_nonenglish_train_n": int(len(early_ne)), "threshold": th,
        "test_rule": "non-English scams with a translation, undated or dated >= 2022, not in any training set",
        "test_n": int(len(test)),
        "recall_all_test_languages": {c: _r(test[c].mean()) for c in ["raw_word_2012", "tr_word_2012", "raw_char_2012", "raw_char_multilingual"]},
        "native_english_2022_24_recall": rate_ci(mm.predict_proba(d["late"]["norm"])[:, 1] >= th),
        "moz_portuguese_false_alarms": fa(E["moz"]), "india_heldout_false_alarms": fa(E["ind_te"]),
        "synthetic_heldout_false_alarms": fa(E["syn_te"]), "uci_test": prf(d["uci_te"]["label"].to_numpy(),
                                                                            (mm.predict_proba(d["uci_te"]["norm"])[:, 1] >= th).astype(int)),
        "per_language_top8": rows}
    return out


SELECTION_CANDIDATES = [  # (name, kind, India train ham, synthetic train half)
    ("word_2012", "word", None, None), ("word_fixed", "word", False, False),
    ("fix_plus_benign", "word", False, True), ("char_fix_plus_benign", "char", False, True),
    ("fix_plus_real_ham", "word", True, False), ("char_fix_plus_real_ham", "char", True, False),
    ("fix_plus_real_ham_and_benign", "word", True, True)]


def step_v2_select(d, D):
    """Item 10 + 8: choose the shipped model and threshold rule on VALIDATION data from the training period only.
    Selection models train on UCI train + scams <= 2020 (+ India group half A1) (+ synthetic train half);
    validation = English scams dated 2021 (recall) and India group half A2 (false alarms), both inside the training pool.
    Score = expected cost per message at an ASSUMED 5% scam rate, missed scam = 5 x false alarm."""
    e20 = d["early"][d["early"]["year"] <= TRAIN_LAST_YEAR - 1]["norm"]
    v_scam = d["early"][d["early"]["year"] == TRAIN_LAST_YEAR]["norm"]
    v_ham = D["ind_a2"]["norm"]
    rows = []
    for name, kind, ind, syn in SELECTION_CANDIDATES:
        if ind is None:
            X = d["uci_tr"]["norm"].to_numpy(dtype=object); y = d["uci_tr"]["label"].to_numpy(); g = None
        else:
            X, y, g = _training_set(d, e20, D["ind_a1"] if ind else None, D["syn_tr"] if syn else None)
        p = oof_proba_v2(MAKERS[kind], X, y, g)
        rules = [("cost_5to1_oof", pick_threshold(y, p)["threshold"])]
        m = MAKERS[kind]().fit(X, y)
        if ind:
            start = len(d["uci_tr"]) + len(e20)
            rules.append(("fa_budget_10pct_oof", fa_budget_threshold(p[start:start + len(D["ind_a1"])])))
        else:
            # Audit fix: give every model the strict rule too. A1 is not in this model's training data,
            # so its scores on A1 are already out-of-sample. Reported for comparison; not shippable as-is.
            rules.append(("fa_budget_10pct_on_india_a1", fa_budget_threshold(m.predict_proba(D["ind_a1"]["norm"])[:, 1])))
        ps, ph = m.predict_proba(v_scam)[:, 1], m.predict_proba(v_ham)[:, 1]
        for rule, th in rules:
            R, F = float((ps >= th).mean()), float((ph >= th).mean())
            cost = COST_FN * ASSUMED_PREVALENCE * (1 - R) + COST_FP * (1 - ASSUMED_PREVALENCE) * F
            rows.append({"model": name, "threshold_rule": rule, "threshold": th, "val_scam_recall_2021": _r(R),
                         "val_scam_n": int(len(v_scam)), "val_real_legit_false_alarms": _r(F), "val_real_legit_n": int(len(v_ham)),
                         "val_expected_cost_per_message": _r(cost)})
    for rname, fn in [("rule_link_only", link_flag),
                      ("rule_link_or_phone", lambda s: np.array([("tok_url" in t) or ("tok_phone" in t) for t in s], dtype=int))]:
        R, F = float(np.mean(fn(v_scam))), float(np.mean(fn(v_ham)))
        cost = COST_FN * ASSUMED_PREVALENCE * (1 - R) + COST_FP * (1 - ASSUMED_PREVALENCE) * F
        rows.append({"model": rname, "threshold_rule": "fixed rule (no threshold)", "threshold": None,
                     "val_scam_recall_2021": _r(R), "val_scam_n": int(len(v_scam)), "val_real_legit_false_alarms": _r(F),
                     "val_real_legit_n": int(len(v_ham)), "val_expected_cost_per_message": _r(cost)})
    df = pd.DataFrame(rows).sort_values("val_expected_cost_per_message", kind="stable").reset_index(drop=True)
    df.to_csv(RESULTS / "model_selection_validation.csv", index=False)
    shippable = df[df["threshold_rule"].isin(["cost_5to1_oof", "fa_budget_10pct_oof"])]
    best = shippable.iloc[0].to_dict()
    return {"rule": "lowest validation expected cost per message = 5 x 0.05 x (1 - recall) + 1 x 0.95 x false-alarm rate "
                    "(5% scam rate ASSUMED; cost ratio 5:1 as in v1)",
            "selection_training": "UCI train + English scams 2015-2020 (+ India train group half A1) (+ synthetic train half)",
            "validation": "English scams dated 2021 (recall) + India train group half A2 (false alarms); no 2022+ data, "
                          "no MOZ, no India test groups",
            "comparison_rows": "fa_budget_10pct_on_india_a1 (threshold set on India A1 scores for models not trained on India) "
                               "and the two link rules are scored for comparison only; the shipped choice is made among "
                               "cost_5to1_oof and fa_budget_10pct_oof rows",
            "lowest_cost_row_overall": {"model": df.iloc[0]["model"], "threshold_rule": df.iloc[0]["threshold_rule"],
                                        "val_expected_cost_per_message": df.iloc[0]["val_expected_cost_per_message"]},
            "validation_sizes": {"scams_2021": int(len(v_scam)), "india_a2_legit": int(len(v_ham))},
            "table": df.to_dict(orient="records"), "chosen": {"model": best["model"], "threshold_rule": best["threshold_rule"]}}


def step_v2_triage(d, D, models, thresholds, sel):
    """Item 10: evaluate the shipped three-tier triage; save model_shipped.joblib + shipped_config.json."""
    import joblib
    name, rule = sel["chosen"]["model"], sel["chosen"]["threshold_rule"]
    m = models[name]
    th = thresholds[name]["fa_budget_threshold"] if rule.startswith("fa_budget") else thresholds[name]["threshold"]
    def tiers(texts, norms):
        p = m.predict_proba(list(norms))[:, 1]
        return np.array([triage_tier(pp, th, n, t) for pp, n, t in zip(p, norms, texts)])
    E = _evalsets(d, D); nonen = d["nonen"]
    sets = {"scams_2022_24_english": (E["late"]["text"], E["late"]["norm"]),
            "scams_2022_24_cluster_safe": (E["late_safe"]["text"], E["late_safe"]["norm"]),
            "scams_undated_english": (E["undated"]["text"], E["undated"]["norm"]),
            "scams_nonenglish_translation_oracle": (nonen["translation"], nonen["norm_tr"]),
            "scams_nonenglish_raw_text": (nonen["text"], nonen["norm"]),
            "synthetic_scam_twins": (E["syn_scam"]["text"], E["syn_scam"]["norm"]),
            "synthetic_legit_heldout": (E["syn_te"]["text"], E["syn_te"]["norm"]),
            "real_legit_india_heldout": (E["ind_te"]["text"], E["ind_te"]["norm"]),
            "real_legit_moz_portuguese": (E["moz"]["text"], E["moz"]["norm"]),
            "uci_test_ham": (E["uci_te"].loc[E["uci_te"]["label"] == 0, "text"], E["uci_te"].loc[E["uci_te"]["label"] == 0, "norm"]),
            "uci_test_spam": (E["uci_te"].loc[E["uci_te"]["label"] == 1, "text"], E["uci_te"].loc[E["uci_te"]["label"] == 1, "norm"])}
    T, rows = {}, []
    for k, (txt, nrm) in sets.items():
        t = tiers(list(txt), list(nrm))
        rr = np.array([bool(rule_reasons(a, b)) for a, b in zip(txt, nrm)])
        T[k] = {"n": int(len(t)), "share_red": rate_ci(t == "RED"), "share_yellow": rate_ci(t == "YELLOW"),
                "share_red_or_yellow": rate_ci(t != "GREEN"), "share_green": rate_ci(t == "GREEN"),
                "share_with_a_rule_firing": rate_ci(rr), "yellow_from_rules_only": int(((t == "YELLOW") & rr).sum())}
        rows.append({"set": k, "n": len(t), "red": T[k]["share_red"]["rate"], "yellow": T[k]["share_yellow"]["rate"],
                     "green": T[k]["share_green"]["rate"], "red_or_yellow": T[k]["share_red_or_yellow"]["rate"],
                     "red_ci95": T[k]["share_red"]["ci95"], "red_or_yellow_ci95": T[k]["share_red_or_yellow"]["ci95"]})
    pd.DataFrame(rows).to_csv(RESULTS / "triage_tiers.csv", index=False)
    X = _triage_extras(d, E, nonen, T, tiers)
    cfg = {"label": V2_LABEL, "model": name, "threshold": th, "threshold_rule": rule,
           "trained_on": thresholds[name].get("trained_on"), "cost_ratio_missed_scam_to_false_alarm": COST_FN / COST_FP,
           "input": "raw text; the pipeline applies scam_drift.normalise() first",
           "tiers": {"RED": TIER_LABELS["RED"] + " = model flags AND the text has a link or phone number",
                     "YELLOW": TIER_LABELS["YELLOW"] + " = model flags with no link/phone, OR a rule fires "
                               "(asks for a code/PIN/password; 'hi mum / new number / wrong number' opener)",
                     "GREEN": TIER_LABELS["GREEN"] + " = otherwise; never worded as 'safe'"},
           "rule_regex": {"code_request": _CODE_REQ_RE.pattern, "negation_window": _NEGATION_RE.pattern,
                          "family_opener": _FAMILY_OPENER_RE.pattern},
           "not_built": "the 'unknown sender' condition (no sender metadata); on-device translation (non-English texts "
                        "were scored on the dataset's English translation as an oracle reference)",
           "selection": {k: v for k, v in sel.items() if k != "table"},
           "warn_only": True, "disclaimer": "This project is a prototype and is not financial advice."}
    MODELS.mkdir(exist_ok=True)
    joblib.dump({"pipeline": m, "threshold": th, "name": name, "config": cfg,
                 "input": "text must be passed through scam_drift.normalise() first"}, MODELS / "model_shipped.joblib")
    (MODELS / "shipped_config.json").write_text(json.dumps(_clean(cfg), indent=2), encoding="utf-8")
    return {"status": "post-hoc design (V2 consensus), evaluated; " + V2_LABEL, "shipped_model": name,
            "threshold": th, "threshold_rule": rule, "definition": cfg["tiers"], "sets": T, **X}


def _grp_warned(df, by, warned):
    out = []
    for key, g in pd.Series(warned, index=df.index).groupby(df[by]):
        out.append({by: key, "n": int(len(g)), **{k: v for k, v in rate_ci(g.to_numpy()).items() if k in ("rate", "ci95")}})
    return sorted(out, key=lambda r: -r["n"])


def _triage_extras(d, E, nonen, T, tiers):
    """Audit additions (post-deadline v2): triage-level precision, per-group tables, non-English by report-year
    cohort, undated near-copy check, and fixed-rule failure examples. Uses only test-side data already scored."""
    W = lambda k: T[k]["share_red_or_yellow"]  # noqa: E731
    # Precision. UCI test is the only set with both classes; the rest is at an ASSUMED 5% scam rate.
    tp, fp = W("uci_test_spam")["k"], W("uci_test_ham")["k"]
    R = W("scams_2022_24_english")["rate"]
    prec = {"uci_test_red_or_yellow": {"precision": _r(tp / (tp + fp)) if tp + fp else None, "tp": tp, "fp": fp,
                                       "recall": W("uci_test_spam")["rate"]},
            "assumed_5pct_scam_rate": {
                "assumption": "5% of incoming texts are scams (ASSUMED, not measured); recall = triage share warned "
                              "(RED or YELLOW) on 2022-24 scams; false-alarm rate = share warned on the named legit set",
                "vs_india_heldout": ppv_at(R, W("real_legit_india_heldout")["rate"]),
                "vs_moz": ppv_at(R, W("real_legit_moz_portuguese")["rate"]),
                "vs_synthetic_heldout": ppv_at(R, W("synthetic_legit_heldout")["rate"]),
                "vs_uci_test_ham": ppv_at(R, W("uci_test_ham")["rate"])}}
    # Per-group tables for the shipped triage (2022-24 English scams; non-English raw vs translation oracle).
    late = E["late"]
    lw = tiers(list(late["text"]), list(late["norm"])) != "GREEN"
    wr = tiers(list(nonen["text"]), list(nonen["norm"])) != "GREEN"
    wt = tiers(list(nonen["translation"]), list(nonen["norm_tr"])) != "GREEN"
    top8 = nonen["language"].value_counts().head(8).index
    by_lang = []
    for lang in top8:
        msk = (nonen["language"] == lang).to_numpy()
        by_lang.append({"language": lang, "n": int(msk.sum()), "warned_raw": rate_ci(wr[msk])["rate"],
                        "warned_translation_oracle": rate_ci(wt[msk])["rate"]})
    yr = nonen["year"]
    cohorts = {"dated_2021_or_earlier": (yr <= TRAIN_LAST_YEAR).to_numpy(), "dated_2022_or_later": (yr > TRAIN_LAST_YEAR).to_numpy(),
               "undated": yr.isna().to_numpy()}
    by_year = {k: {"n": int(m.sum()), "warned_raw": rate_ci(wr[m]), "warned_translation_oracle": rate_ci(wt[m])}
               for k, m in cohorts.items()}
    # Undated English scams: share with a near-copy (char_wb 3-5 cosine > 0.8) among training scams (<= 2021).
    from sklearn.feature_extraction.text import TfidfVectorizer
    und, early = E["undated"], d["early"]
    v = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2).fit(pd.concat([und["norm"], early["norm"]]))
    Be = v.transform(early["norm"]).T.tocsc()
    Au = v.transform(und["norm"])
    mx = np.concatenate([(Au[i:i + 2000] @ Be).max(axis=1).toarray().ravel() for i in range(0, Au.shape[0], 2000)])
    near = mx > CLUSTER_COSINE
    uw = tiers(list(und["text"]), list(und["norm"])) != "GREEN"
    undated_check = {"rule": f"char_wb 3-5 TF-IDF max cosine to any English training scam dated <= {TRAIN_LAST_YEAR}, "
                             f"near-copy if > {CLUSTER_COSINE}",
                     "n": int(len(und)), "with_near_copy_in_training": rate_ci(near),
                     "triage_warned_all": rate_ci(uw), "triage_warned_without_near_copy": rate_ci(uw[~near]),
                     "note": "the undated set is not cluster-safe; only the 2022-24 cluster-safe set is"}
    # Fixed-rule failure examples (public IMC25 reports and synthetic texts only; India/MOZ texts are never printed).
    gm = late.assign(tier=np.where(lw, "WARN", "GREEN"), chars=late["text"].str.len())
    gm = gm[gm["tier"] == "GREEN"]
    top_types = gm["scam_type"].value_counts().head(5).index
    misses = [{"scam_type": t, "year": int(g.iloc[0]["year"]), "chars": int(g.iloc[0]["chars"]), "text": g.iloc[0]["text"]}
              for t in top_types for g in [gm[(gm["scam_type"] == t) & (gm["chars"] >= 40)].sort_values(["chars", "text"])] if len(g)]
    syn = E["syn_te"].copy()
    syn["tier"] = tiers(list(syn["text"]), list(syn["norm"]))
    fa = syn[syn["tier"] != "GREEN"].assign(chars=syn["text"].str.len()).sort_values(["chars", "text"])
    fas = [{"category": r.get("category", ""), "tier": r["tier"], "text": r["text"], "label": "synthetic, written with AI assistance"}
           for _, r in fa.head(2).iterrows()]
    return {"precision": prec,
            "by_scam_type_2022_24": _grp_warned(late, "scam_type", lw),
            "by_length_bucket_2022_24": _grp_warned(late, "len_bucket", lw),
            "by_language_nonenglish_top8": by_lang,
            "nonenglish_by_report_year_cohort": by_year,
            "undated_near_copy_check": undated_check,
            "failure_examples": {
                "rule": "missed scams: real 2022-24 reports left GREEN; for each of the 5 scam types with the most GREEN "
                        "misses, the shortest text of at least 40 characters. False alarms: the 2 shortest held-out "
                        "synthetic legit texts that got RED or YELLOW.",
                "missed_scams_green": misses, "false_alarms_synthetic": fas}}


def _sweep(m, sets, grid=np.round(np.arange(0.02, 0.99, 0.02), 2)):
    ps = {k: m.predict_proba(v)[:, 1] for k, v in sets.items()}
    return [{"threshold": float(t), **{k: _r((p >= t).mean()) for k, p in ps.items()}} for t in grid]


def step_v2_figures(d, D, models, thresholds, V):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
    PAL = {"word_2012": "#2a78d6", "word_fixed": "#eb6834", "fix_plus_benign": "#8a5cc2",
           "fix_plus_real_ham": "#1f9e74", "char_fix_plus_real_ham": "#7fc6ad", "fix_plus_real_ham_and_benign": "#0f5c44",
           "char_fix_plus_benign": "#c3a6e3", "char_2012": "#8fb8ea", "char_fixed": "#f3a684"}
    C = V["model_comparison"]
    # Trade-off (updated): every model and rule, recall vs false alarms on held-out sets.
    order = [("rule_link_only", "Rule:\nlink only"), ("rule_link_or_phone", "Rule: link\nor phone"),
             ("word_2012", "2012\nmodel"), ("word_fixed", "Naive fix\n(+ scams)"),
             ("fix_plus_benign", "Fix + synth.\nlegit"), ("fix_plus_real_ham", "Fix + real\nlegit"),
             ("fix_plus_real_ham_and_benign", "Fix + real\n+ synth.")]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = np.arange(len(order)); w = 0.26
    series = [("late_recall", "Real 2022-24 scams caught (n=%d)" % C["word_2012"]["late_recall"]["n"], "#2a78d6"),
              ("synthetic_legit_heldout_false_alarms", "False alarms: held-out synthetic legit (n=%d)" % C["word_2012"]["synthetic_legit_heldout_false_alarms"]["n"], "#eb6834"),
              ("india_heldout_false_alarms", "False alarms: real India legit, held-out groups (n=%d)" % C["word_2012"]["india_heldout_false_alarms"]["n"], "#b8461b")]
    for i, (key, lab, col) in enumerate(series):
        vals = [C[n][key]["rate"] for n, _ in order]
        bars = ax.bar(x + (i - 1) * (w + 0.01), vals, w, color=col, label=lab)
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.0%}", ha="center", fontsize=7, color=INK)
    ax.set_xticks(x, [o[1] for o in order], fontsize=8); ax.set_ylim(0, 1.12); ax.set_ylabel("Share of messages")
    ax.set_title("The trade-off: modern scams caught vs. false alarms on held-out legitimate texts (" + V2_LABEL + ")", loc="left", fontsize=9.5)
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, -0.16), ncol=2, fontsize=8)
    fig.tight_layout(); fig.savefig(FIGURES / "tradeoff_catch_vs_false_alarm.png", dpi=150); plt.close(fig)

    # Half-life.
    H = V["half_life"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    by = [r for r in H["by_year_word_2012"] if r["n"] >= 30]
    t0 = H["time_zero_2012_model"]
    ax.errorbar([2012], [t0["uci_test_spam_recall"]], yerr=[[t0["uci_test_spam_recall"] - t0["ci95"][0]], [t0["ci95"][1] - t0["uci_test_spam_recall"]]],
                fmt="s", color=INK, label=f"time zero: UCI test spam (n={t0['n_spam']})")
    ys = [r["year"] for r in by]; rs = [r["recall_word_2012"] for r in by]
    ax.errorbar(ys, rs, yerr=[[r["recall_word_2012"] - r["ci95"][0] for r in by], [r["ci95"][1] - r["recall_word_2012"] for r in by]],
                fmt="-o", color=PAL["word_2012"], lw=2, label="2012 model, all types")
    for t, col in zip(H["top3_scam_types"], ["#1f9e74", "#eb6834", "#8a5cc2"]):
        tb = [r for r in H["by_year_top3_types_word_2012"] if r["scam_type"] == t and r["n"] >= 30]
        ax.plot([r["year"] for r in tb], [r["recall_word_2012"] for r in tb], "--.", color=col, lw=1.2, label=f"{t} (years n>=30)")
    for r in by:
        ax.text(r["year"], 0.04, f"n={r['n']}", ha="center", fontsize=6.5, color=MUTED, rotation=90)
    ax.axhline(t0["uci_test_spam_recall"] / 2, color=MUTED, lw=0.8, ls=":")
    ax.text(2012.2, t0["uci_test_spam_recall"] / 2 + 0.02, "half of time-zero recall", fontsize=7, color=MUTED)
    ax.set_ylim(0, 1.05); ax.set_xlabel("Report year (report-date cohorts)"); ax.set_ylabel("Recall (2012 model)")
    ax.set_title("2012 filter on later report-date cohorts", loc="left", fontsize=10)
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.legend(frameon=False, fontsize=7, loc="lower left")
    ax = axes[1]
    roll = pd.DataFrame(H["rolling_cutoff"])
    cols = ["#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b"]
    for (Y, g), col in zip(roll.groupby("cutoff_year"), cols):
        ax.plot(g["years_since_cutoff"], g["recall"], "-o", color=col, lw=1.6, label=f"trained on scams <= {Y}")
    ax.set_ylim(0, 1.05); ax.set_xlabel("Years since training cutoff"); ax.set_ylabel("Recall")
    ax.set_title("Retrained filters: recall on later cohorts", loc="left", fontsize=10)
    ax.set_xticks(sorted(roll["years_since_cutoff"].unique()))
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.legend(frameon=False, fontsize=7, loc="lower left")
    fig.suptitle("Filter half-life (" + V2_LABEL + ")", x=0.01, ha="left", fontsize=10)
    fig.tight_layout(); fig.savefig(FIGURES / "half_life.png", dpi=150); plt.close(fig)

    # Learning curve.
    L = pd.DataFrame(V["learning_curve"]["summary"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for base, col, lab in [("naive_fix", "#eb6834", "UCI + k early scams"), ("fix_plus_real_ham", "#1f9e74", "UCI + k early scams + real India legit")]:
        g = L[L["base"] == base]
        axes[0].plot(g["early_scams_added"], g["late_recall_mean"], "-o", color=col, label=lab)
        axes[0].fill_between(g["early_scams_added"], g["late_recall_min"], g["late_recall_max"], color=col, alpha=0.15)
        axes[1].plot(g["early_scams_added"], g["synthetic_fa_mean"], "-o", color=col, label=lab + ": synthetic held-out")
        axes[1].plot(g["early_scams_added"], g["india_fa_mean"], "--s", color=col, label=lab + ": real India held-out")
    axes[0].set_title("2022-24 scams caught", loc="left", fontsize=10); axes[1].set_title("False alarms on held-out legit texts", loc="left", fontsize=10)
    for ax in axes:
        ax.set_xlabel("Early (2015-2021) modern scams added to training"); ax.set_ylim(0, 1.05)
        ax.yaxis.grid(True, color=GRID, lw=0.8); ax.legend(frameon=False, fontsize=7)
    fig.suptitle("Learning curve (" + V2_LABEL + ")", x=0.01, ha="left", fontsize=10)
    fig.tight_layout(); fig.savefig(FIGURES / "learning_curve.png", dpi=150); plt.close(fig)

    # Triage tiers.
    T = V["triage"]["sets"]
    keys = [("scams_2022_24_english", "Real scams 2022-24 (English)"), ("scams_2022_24_cluster_safe", "Real scams 2022-24, cluster-safe"),
            ("scams_nonenglish_raw_text", "Non-English scams (raw text)"),
            ("scams_nonenglish_translation_oracle", "Non-English scams (translation = oracle)"),
            ("synthetic_legit_heldout", "Synthetic legit, held-out"), ("real_legit_india_heldout", "Real legit: India, held-out groups"),
            ("real_legit_moz_portuguese", "Real legit: Mozambique (Portuguese)"), ("uci_test_ham", "UCI 2012 test ham")]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for i, (k, lab) in enumerate(keys):
        left = 0
        for tier, col in [("share_red", "#c8312b"), ("share_yellow", "#e8b622"), ("share_green", "#3a9a5b")]:
            v = T[k][tier]["rate"]
            ax.barh(i, v, left=left, color=col, height=0.6)
            if v >= 0.06:
                ax.text(left + v / 2, i, f"{v:.0%}", ha="center", va="center", fontsize=8, color="white")
            left += v
    ax.set_yticks(range(len(keys)), [f"{lab} (n={T[k]['n']:,})" for k, lab in keys], fontsize=8); ax.invert_yaxis()
    ax.set_xlim(0, 1); ax.set_xlabel("Share of messages: RED / YELLOW / GREEN")
    ax.set_title(f"Three-tier triage, prototype model = {V['triage']['shipped_model']} (" + V2_LABEL + ")", loc="left", fontsize=10)
    fig.tight_layout(); fig.savefig(FIGURES / "triage_tiers.png", dpi=150); plt.close(fig)

    # Operating curve (descriptive threshold sweep).
    sets = {"late": d["late"]["norm"], "india_te": D["ind_te"]["norm"]}
    oc = []
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    for n in ["word_2012", "word_fixed", "fix_plus_benign", "fix_plus_real_ham", "char_fix_plus_real_ham", "fix_plus_real_ham_and_benign"]:
        sw = _sweep(models[n], sets)
        oc += [{"model": n, **r} for r in sw]
        ax.plot([r["india_te"] for r in sw], [r["late"] for r in sw], "-", color=PAL[n], lw=1.8, label=n)
        th = thresholds[n]["threshold"]; c = C[n]
        ax.plot([c["india_heldout_false_alarms"]["rate"]], [c["late_recall"]["rate"]], "o", color=PAL[n], ms=6)
    ax.set_xlabel("False alarms: real India legit, held-out groups"); ax.set_ylabel("2022-24 scams caught")
    ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02); ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_title("Operating curves (threshold sweep, descriptive); dot = frozen threshold", loc="left", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(FIGURES / "operating_curve.png", dpi=150); plt.close(fig)
    pd.DataFrame(oc).to_csv(RESULTS / "operating_curve.csv", index=False)

    # Lead chart v2 (same layout as tools/lead_chart.py, but from these v2 numbers, brand-or-template grouping).
    T = V["triage"]["sets"]
    lead = [("2012 filter", "#9aa5b1", [C["word_2012"][k]["rate"] for k in ("late_recall", "india_heldout_false_alarms", "moz_false_alarms")]),
            ("Retrained on modern scams", "#d9822b", [C["word_fixed"][k]["rate"] for k in ("late_recall", "india_heldout_false_alarms", "moz_false_alarms")]),
            ("+ real legit texts", "#2b6cb0", [C["fix_plus_real_ham"][k]["rate"] for k in ("late_recall", "india_heldout_false_alarms", "moz_false_alarms")]),
            ("Prototype triage (RED or YELLOW)", "#1f9e74", [T[k]["share_red_or_yellow"]["rate"] for k in
                                                             ("scams_2022_24_english", "real_legit_india_heldout", "real_legit_moz_portuguese")])]
    labs = [f"2022-24 scams caught (n={C['word_2012']['late_recall']['n']:,})\n(higher is better)",
            f"False alarms: real India legit, held-out groups\n(n={C['word_2012']['india_heldout_false_alarms']['n']:,}, lower is better)",
            f"False alarms: real Mozambique legit\n(n={C['word_2012']['moz_false_alarms']['n']:,}, lower is better)"]
    fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=150); w = 0.2
    for i, (lab, col, vals) in enumerate(lead):
        xs = [j + (i - 1.5) * w for j in range(3)]
        for b in ax.bar(xs, vals, w, label=lab, color=col):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.1%}", ha="center", fontsize=7.5)
    ax.set_xticks(range(3), labs, fontsize=9); ax.set_ylim(0, 1.12); ax.set_ylabel("Share of messages")
    ax.set_title("Catching modern scams costs false alarms on real legitimate texts (" + V2_LABEL + ")", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False); ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)
    fig.tight_layout(); fig.savefig(FIGURES / "lead_chart_v2.png"); plt.close(fig)


def step_v2(d, models, thresholds, M, near):
    """Run every v2 item; returns the metrics['v2'] dict. Writes v2 tables, figures and the shipped model."""
    t = time.time()
    models = dict(models)                                   # v1 dicts stay untouched (v1 keys unchanged)
    thresholds = {k: dict(v) for k, v in thresholds.items()}
    D, V = step_v2_data(d)
    models, thresholds = step_v2_train(d, D, models, thresholds)
    V["model_comparison"] = step_v2_compare(d, D, models, thresholds)
    V["placeholder_ablation"], V["source_confound"] = step_v2_ablation_and_confound(d, D, V["model_comparison"])
    V["half_life"] = step_v2_half_life(d, models, thresholds, M, near)
    V["learning_curve"] = step_v2_learning_curve(d, D)
    V["multilingual"] = step_v2_multilingual(d, D, models, thresholds)
    V["model_selection"] = step_v2_select(d, D)
    V["triage"] = step_v2_triage(d, D, models, thresholds, V["model_selection"])
    V["threshold_discipline"] = {
        "rule": "each threshold is chosen on out-of-fold predictions of the model's own training data "
                "(5 folds; group-aware when India rows are in training), minimising 5 x missed scams + 1 x false alarms; "
                "frozen before any 2022+ or held-out evaluation",
        "cost_ratio_missed_scam_to_false_alarm": COST_FN / COST_FP,
        "alternative_rule": f"false-alarm budget: lowest threshold with <= {FA_BUDGET:.0%} out-of-fold false alarms on India-train legit",
        "thresholds": {n: {k: v for k, v in thresholds[n].items() if k in ("threshold", "fa_budget_threshold")} for n in thresholds}}
    rows = []
    for n, r in V["model_comparison"].items():
        rows.append({"model": n, "threshold": r.get("threshold"), "uci_precision": r["uci_test"]["precision"],
                     "uci_recall": r["uci_test"]["recall"], "uci_false_alarm_rate": r["uci_test"]["false_alarm_rate"],
                     "late_recall": r["late_recall"]["rate"], "late_cluster_safe_recall": r["late_cluster_safe_recall"]["rate"],
                     "synthetic_heldout_fa": r["synthetic_legit_heldout_false_alarms"]["rate"],
                     "synthetic_heldout_fa_ci95": r["synthetic_legit_heldout_false_alarms"]["ci95"],
                     "india_heldout_fa": r["india_heldout_false_alarms"]["rate"],
                     "india_heldout_fa_ci95": r["india_heldout_false_alarms"]["ci95"],
                     "moz_fa": r["moz_false_alarms"]["rate"], "moz_fa_ci95": r["moz_false_alarms"]["ci95"],
                     "ppv_assumed_5pct_vs_india": r["prevalence_adjusted_precision_assumed_5pct"]["vs_india_heldout"]})
    pd.DataFrame(rows).to_csv(RESULTS / "v2_model_comparison.csv", index=False)
    step_v2_figures(d, D, models, thresholds, V)
    V["label"] = V2_LABEL
    V["privacy"] = "India/MOZ raw messages are never written to results/, figures/ or printed; aggregates only."
    V["runtime_seconds_v2"] = round(time.time() - t, 1)
    return V


def save_models(models, thresholds):
    import joblib
    MODELS.mkdir(exist_ok=True)
    for key, fname in [("word_2012", "model_2012.joblib"), ("word_fixed", "model_fixed.joblib")]:
        joblib.dump({"pipeline": models[key], "threshold": thresholds[key]["threshold"], "name": key,
                     "input": "text must be passed through scam_drift.normalise() first"}, MODELS / fname)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if o != o else round(float(o), 4)
    return o


def write_metrics(d, shortcut, near, thresholds, M, tables, t0, v2=None):
    import sklearn
    metrics = {"data": d["info"], "near_duplicate_check": near, "shortcut_check": shortcut,
               "thresholds": thresholds,
               "cost_model": {"cost_missed_scam": COST_FN, "cost_false_alarm": COST_FP}, **M, "tables": tables,
               "main_models": {"model_2012": "word_2012", "model_fixed": "word_fixed"},
               "v2": v2,
               "runtime_seconds": round(time.time() - t0, 1), "seed": SEED,
               "versions": {"pandas": pd.__version__, "numpy": np.__version__, "scikit-learn": sklearn.__version__}}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "metrics.json").write_text(json.dumps(_clean(metrics), indent=2, default=str), encoding="utf-8")
    return metrics


def main():
    t0 = time.time()
    np.random.seed(SEED)
    d = step_load_and_split()
    shortcut = step_shortcut_check(d)
    models, thresholds = step_train(d)
    M, P = step_evaluate(d, models, thresholds)
    tables = step_tables_and_figures(d, models, thresholds, M, P)
    near = step_near_duplicate_check(d, P, models, thresholds)
    M["tok_date_ablation"] = step_tok_date_ablation(d)
    M["demo_examples"] = step_demo_examples(models, thresholds, P)
    save_models(models, thresholds)
    v2 = step_v2(d, models, thresholds, M, near)
    metrics = write_metrics(d, shortcut, near, thresholds, M, tables, t0, v2)
    print(json.dumps({k: metrics[k] for k in ("data", "thresholds")}, indent=1, default=str))
    print("runtime_seconds", metrics["runtime_seconds"])
    return metrics


if __name__ == "__main__":
    main()
