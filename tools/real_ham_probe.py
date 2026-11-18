"""Probe: false alarms of the saved v1 models on REAL modern legitimate SMS (test only).

Reads models/model_2012.joblib and models/model_fixed.joblib, the loader from docs/EXTRA_DATA.md,
and src/scam_drift.normalise. Writes results/real_ham_probe.json. Never trains on these sets.
Privacy: prints no raw messages.
"""
import json
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_drift import normalise, wilson, link_flag  # noqa: E402

EXTRA = ROOT / "data" / "raw" / "extra"
DLT_SENDER = r"^[A-Z]{2}-?[A-Za-z0-9]{5,6}(?:-[A-Z])?$"


def _key(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def load_extra_benign():
    uci = pd.read_csv(ROOT / "data/raw/SMSSpamCollection", sep="\t", header=None, names=["label", "text"], quoting=3)
    imc = pd.read_csv(ROOT / "data/raw/imc25_smishing.csv", encoding_errors="replace")
    ban = {_key(t) for t in uci["text"]} | {_key(t) for t in pd.concat([imc["text"].dropna(), imc["translation"].dropna()])}
    a = pd.read_csv(EXTRA / "gandharvbakshi_sms_sample_10k.csv")
    a = a[(a["classification_status"] != "synthetic") & a["sender"].fillna("").str.match(DLT_SENDER)]
    a = a.assign(text=a["sms_text"].astype(str), source="india_inbox", sender=a["sender"])
    b = pd.read_csv(EXTRA / "moz_smishing.csv")
    b = b[(b["label"] == "Legitimate") & (b["source"] == "sms")]
    b = b.assign(text=b["text"].astype(str), source="moz_pt", sender=None)
    out = pd.concat([a[["text", "source", "sender"]], b[["text", "source", "sender"]]], ignore_index=True)
    out["k"] = out["text"].map(_key)
    return out[~out["k"].isin(ban)].drop_duplicates("k").drop(columns="k").reset_index(drop=True)


def main():
    xb = load_extra_benign()
    xb["norm"] = xb["text"].map(normalise)
    res = {"n": xb["source"].value_counts().to_dict()}
    for name in ["model_2012", "model_fixed"]:
        m = joblib.load(ROOT / "models" / f"{name}.joblib")
        p = m["pipeline"].predict_proba(xb["norm"])[:, 1]
        for th_name, th in [("threshold", m["threshold"]), ("0.5", 0.5)]:
            for src, g in xb.assign(p=p).groupby("source"):
                k, n = int((g["p"] >= th).sum()), len(g)
                lo, hi = wilson(k, n)
                res[f"{name}|{th_name}|{src}"] = {"false_alarms": k, "n": n, "rate": round(k / n, 4),
                                                   "wilson95": [round(lo, 4), round(hi, 4)]}
    lf = link_flag(xb["norm"])
    for src, g in xb.assign(l=lf).groupby("source"):
        res[f"rule_link_only|{src}"] = {"flagged": int(g["l"].sum()), "n": len(g), "rate": round(float(g["l"].mean()), 4)}
    res["india_distinct_senders"] = int(xb.loc[xb.source == "india_inbox", "sender"].nunique())
    (ROOT / "results" / "real_ham_probe.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
