"""Scam Drift: does a 2012-era SMS spam filter still protect a grandparent from 2020s smishing?

Run end to end (seeded) from the project root:
    python src/scam_drift.py

Outputs: results/metrics.json, results/*.csv, figures/*.png, models/*.joblib.
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
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:pounds|dollars|euros|usd|gbp|eur|pence|ppm|p)\b", re.I)
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
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": int(len(y))}


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


def recall_table(df: pd.DataFrame, by: str, pred_cols: list[str]) -> pd.DataFrame:
    g = df.groupby(by)
    out = g.size().rename("n").to_frame()
    for c in pred_cols:
        out["recall_" + c] = g["pred_" + c].mean().round(4)
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
    M["baselines"]["rule_url_or_urgency"] = rule
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
    # Link-gated mode (decided from the user's decision "warn before tapping a link", not tuned on test):
    # warn only when the model says scam AND the message contains a link.
    M["link_gated"] = {"rule": "warn = model flag at its threshold AND message contains tok_url"}
    for name in ["word_2012", "word_fixed"]:
        th = thresholds[name]["threshold"]
        g = lambda df, col: ((df[col] >= th) & df["norm"].str.contains("tok_url")).astype(int).to_numpy()
        late_g = g(late, "p_" + name)
        M["link_gated"][name] = {
            "uci_test": prf(yte, g(uci_te, "p_" + name)),
            "modern_late_recall": _r(late_g.mean()),
            "modern_late_recall_on_rows_with_link": _r(late_g[late["norm"].str.contains("tok_url").to_numpy()].mean()),
            "benign_twins": prf(twins["label"].to_numpy(), g(twins, "p_" + name))}
    M["link_gated"]["modern_late_share_with_link"] = _r(late["norm"].str.contains("tok_url").mean())
    return M, {"uci_te": uci_te, "late": late, "undated": undated, "twins": twins, "nonen": nonen}


def step_near_duplicate_check(d):
    """Fraction of late-test scams with a near-identical (cosine >= 0.9) early training scam."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    v = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b").fit(
        pd.concat([d["early"]["norm"], d["late"]["norm"]]))
    s = (v.transform(d["late"]["norm"]) @ v.transform(d["early"]["norm"]).T).max(axis=1).toarray().ravel()
    return {"late_test_frac_with_cosine_ge_0.9_to_train": _r((s >= 0.9).mean()),
            "late_test_frac_with_cosine_ge_0.7_to_train": _r((s >= 0.7).mean())}


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
    miss["hypothesis"] = [hypothesis_for_miss(n, s) for n, s in zip(miss["norm"], miss["scam_type"])]
    miss[["year", "scam_type", "p_word_fixed", "text", "hypothesis"]].round(4)\
        .to_csv(RESULTS / "fixed_model_missed_scams.csv", index=False)
    fa_rows = pd.concat([
        uci_te[(uci_te["label"] == 0) & (uci_te["p_word_fixed"] >= th_fx)].assign(source="uci_test_ham"),
        twins[(twins["label"] == 0) & (twins["p_word_fixed"] >= th_fx)].assign(source="benign_twins")])
    fa_rows = fa_rows.sort_values("p_word_fixed", ascending=False)
    fa_rows["top_scam_words"] = [", ".join(w for w, _ in explain(models["word_fixed"], n)) for n in fa_rows["norm"]]
    fa_rows["hypothesis"] = [hypothesis_for_false_alarm(n) for n in fa_rows["norm"]]
    fa_rows[["source", "p_word_fixed", "text", "top_scam_words", "hypothesis"]].round(4)\
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
    yp = yr[yr["n"] >= 20]
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
    # Figure 5: the trade-off - scams caught vs false alarms on the benign twins.
    rows = [("Rule", M["baselines"]["rule_url_or_urgency"]["modern_late_recall"],
             M["baselines"]["rule_url_or_urgency"]["benign_twins_false_alarm_rate"])]
    for n, lab in [("word_2012", "2012 model"), ("word_fixed", "Fixed model")]:
        rows.append((lab, M["modern_late_test"][n]["recall_at_threshold"],
                     M["benign_twins"][n]["at_threshold"]["false_alarm_rate"]))
    for n, lab in [("word_2012", "2012 model\n+ link gate"), ("word_fixed", "Fixed model\n+ link gate")]:
        rows.append((lab, M["link_gated"][n]["modern_late_recall"],
                     M["link_gated"][n]["benign_twins"]["false_alarm_rate"]))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(rows)); w = 0.38
    b1 = ax.bar(x - w / 2 - 0.01, [r[1] for r in rows], w, color=C12, label="Modern scams caught (2022+ test)")
    b2 = ax.bar(x + w / 2 + 0.01, [r[2] for r in rows], w, color=CFX, label="False alarms on benign modern texts")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.0%}",
                    ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, [r[0] for r in rows], fontsize=9); ax.set_ylim(0, 1.1); ax.set_ylabel("Share of messages")
    ax.set_title("The trade-off: catching modern scams vs. false alarms on real-looking texts", loc="left", fontsize=10)
    ax.yaxis.grid(True, color="#e6e5e0", lw=0.8); ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, -0.14), ncol=2)
    fig.tight_layout(); fig.savefig(FIGURES / "tradeoff_catch_vs_false_alarm.png", dpi=150); plt.close(fig)
    return {"recall_by_scam_type_late": st.to_dict(orient="records"),
            "recall_by_year": yr.to_dict(orient="records"),
            "by_length_bucket": lb.to_dict(orient="records"),
            "nonenglish_by_language": nl.reset_index().to_dict(orient="records"),
            "benign_twins_by_category": tw.to_dict(orient="records"),
            "fixed_model_missed_late_n": int(len(miss)),
            "fixed_model_false_alarms_n": {"uci_test_ham": int((fa_rows["source"] == "uci_test_ham").sum()),
                                           "benign_twins": int((fa_rows["source"] == "benign_twins").sum())}}


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


def write_metrics(d, shortcut, near, thresholds, M, tables, t0):
    import sklearn
    metrics = {"data": d["info"], "near_duplicate_check": near, "shortcut_check": shortcut,
               "thresholds": thresholds,
               "cost_model": {"cost_missed_scam": COST_FN, "cost_false_alarm": COST_FP}, **M, "tables": tables,
               "main_models": {"model_2012": "word_2012", "model_fixed": "word_fixed"},
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
    near = step_near_duplicate_check(d)
    save_models(models, thresholds)
    metrics = write_metrics(d, shortcut, near, thresholds, M, tables, t0)
    print(json.dumps({k: metrics[k] for k in ("data", "thresholds")}, indent=1, default=str))
    print("runtime_seconds", metrics["runtime_seconds"])
    return metrics


if __name__ == "__main__":
    main()
