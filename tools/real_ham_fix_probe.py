"""Probe for the v2 headline test: does adding REAL modern legitimate SMS to training fix the false alarms?

Training negatives = UCI train ham + India-inbox ham from HALF of the sender BRANDS (GroupShuffleSplit,
seed 42; brand = sender header without the 2-letter operator prefix, so VM-ICICIB and JX-ICICIB are one group).
Tests: UCI test, 2022-24 real scams, India ham from the OTHER brands, all MOZ ham (Portuguese),
synthetic benign twins (legit and scam). Thresholds: 5-fold out-of-fold on each model's own training data.
Writes results/real_ham_fix_probe.json. Prints no raw messages.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
import scam_drift as sd  # noqa: E402
from real_ham_probe import load_extra_benign  # noqa: E402


def rate(flags):
    k, n = int(np.sum(flags)), len(flags)
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "wilson95": sd.wilson(k, n)}


def main():
    from sklearn.model_selection import GroupShuffleSplit
    d = sd.step_load_and_split()
    xb = load_extra_benign()
    xb["norm"] = xb["text"].map(sd.normalise)
    india = xb[xb.source == "india_inbox"].reset_index(drop=True)
    moz = xb[xb.source == "moz_pt"].reset_index(drop=True)
    brand = india["sender"].str.replace(r"^[A-Z]{2}-?", "", regex=True).str.replace(r"-[A-Z]$", "", regex=True).str.upper()
    tr_i, te_i = next(GroupShuffleSplit(1, test_size=0.5, random_state=sd.SEED).split(india, groups=brand))
    ind_tr, ind_te = india.iloc[tr_i], india.iloc[te_i]
    shared_templates = len(set(ind_tr["norm"]) & set(ind_te["norm"]))

    X12 = d["uci_tr"]["norm"].to_numpy(dtype=object); y12 = d["uci_tr"]["label"].to_numpy()
    E = d["early"]["norm"].to_numpy(dtype=object)
    R = ind_tr["norm"].to_numpy(dtype=object)
    sets = {
        "word_2012": (X12, y12),
        "word_naive_fix": (np.concatenate([X12, E]), np.concatenate([y12, np.ones(len(E), int)])),
        "word_fix_real_ham": (np.concatenate([X12, E, R]),
                              np.concatenate([y12, np.ones(len(E), int), np.zeros(len(R), int)])),
    }
    tw = d["twins"]; tw_legit = tw[tw.label == 0]["norm"]; tw_scam = tw[tw.label == 1]["norm"]
    out = {"split": {"india_train_rows": len(ind_tr), "india_test_rows": len(ind_te),
                     "india_train_brands": int(brand.iloc[tr_i].nunique()), "india_test_brands": int(brand.iloc[te_i].nunique()),
                     "identical_normalised_texts_across_split": shared_templates, "moz_rows": len(moz)}}
    for name, (X, y) in sets.items():
        th = sd.pick_threshold(y, sd.oof_proba(sd.make_word_model, X, y))["threshold"]
        m = sd.make_word_model().fit(X, y)
        P = lambda s: m.predict_proba(list(s))[:, 1] >= th  # noqa: E731
        yte = d["uci_te"]["label"].to_numpy(); pu = P(d["uci_te"]["norm"])
        out[name] = {"threshold": th,
                     "uci_test": sd.prf(yte, pu.astype(int)),
                     "late_2022_24_recall": rate(P(d["late"]["norm"])),
                     "fa_india_heldout_brands": rate(P(ind_te["norm"])),
                     "fa_moz_pt": rate(P(moz["norm"])),
                     "fa_synthetic_legit": rate(P(tw_legit)),
                     "recall_synthetic_scam_twins": rate(P(tw_scam))}
    (ROOT / "results" / "real_ham_fix_probe.json").write_text(json.dumps(out, indent=1, default=float))
    for k, v in out.items():
        if k == "split":
            print(v); continue
        print(k, "th", v["threshold"], "| UCI R", v["uci_test"]["recall"], "P", v["uci_test"]["precision"],
              "| late R", v["late_2022_24_recall"]["rate"], "| FA india", v["fa_india_heldout_brands"]["rate"],
              v["fa_india_heldout_brands"]["wilson95"], "| FA moz", v["fa_moz_pt"]["rate"],
              "| FA synth", v["fa_synthetic_legit"]["rate"], "| twin-scam R", v["recall_synthetic_scam_twins"]["rate"])


if __name__ == "__main__":
    main()
