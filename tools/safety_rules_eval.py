"""How often do the post-deadline safety / money-offer rules fire on legitimate and scam texts?
Writes results/safety_rules_eval.json. Prints counts only (no raw messages)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import scam_drift as sd  # noqa: E402


def rate(texts, fn):
    k = sum(1 for t in texts if fn(t))
    return {"k": k, "n": len(texts), "rate": round(k / len(texts), 4) if texts else None, "wilson95": sd.wilson(k, len(texts))}


def main():
    d = sd.step_load_and_split()
    xb = sd.load_extra_benign()
    sets = {
        "uci_test_ham": d["uci_te"].loc[d["uci_te"]["label"] == 0, "text"].tolist(),
        "uci_test_spam": d["uci_te"].loc[d["uci_te"]["label"] == 1, "text"].tolist(),
        "synthetic_legit": d["twins"].loc[d["twins"]["label"] == 0, "text"].tolist(),
        "india_legit": xb.loc[xb["source"].str.startswith("india"), "text"].tolist(),
        "moz_legit_pt": xb.loc[xb["source"].str.startswith("moz"), "text"].tolist(),
        "scams_2022_24": d["late"]["text"].tolist(),
    }
    out = {}
    for name, texts in sets.items():
        out[name] = {"safety_rule_RED": rate(texts, lambda t: bool(sd.safety_reasons(t))),
                     "money_offer_rule_YELLOW": rate(texts, lambda t: bool(sd.money_offer_reasons(t))),
                     "grooming_any_category_YELLOW": rate(texts, lambda t: bool(sd.grooming_categories(t)))}
    (ROOT / "results" / "safety_rules_eval.json").write_text(json.dumps(out, indent=1))
    import pandas as pd
    from triage import triage
    b = pd.read_csv(ROOT / "data" / "safety_test_blind.csv")
    b["tier"] = [triage(t)["tier"] for t in b["text"]]
    out["blind_safety_set_SEEN_WHILE_TUNING"] = {lab: {t: int(((b.label == lab) & (b.tier == t)).sum()) for t in ("RED", "YELLOW", "GREEN")}
                                                 for lab in sorted(b.label.unique())}
    out["note"] = ("Rules are hand-written. The blind set (written by a separate agent that never saw the rules) was used to "
                   "revise the rules once, so its numbers are optimistic; a fresh unseen set is needed for a fair score.")
    (ROOT / "results" / "safety_rules_eval.json").write_text(json.dumps(out, indent=1))
    print(out["blind_safety_set_SEEN_WHILE_TUNING"])
    for k, v in list(out.items())[:6]:
        print(f"{k:18s} safety-RED {v['safety_rule_RED']['k']}/{v['safety_rule_RED']['n']}  money {v['money_offer_rule_YELLOW']['k']}  grooming-any {v['grooming_any_category_YELLOW']['k']}/{v['grooming_any_category_YELLOW']['n']}")


if __name__ == "__main__":
    main()
