# Extra data: real modern legitimate SMS

Data scout report, 2026-11-17. Checks were run on the downloaded files. Numbers below are measured, not copied from dataset cards, unless marked "card".

## Objective

Red-team flaw 1 (docs/CONSULT_LOG.md): all negatives are 2012 UCI ham, all modern texts are scams. A model can learn "modern = scam". We need REAL, public, licence-compatible MODERN legitimate SMS (bank OTPs, transaction alerts, delivery updates, appointment reminders, personal texts) to measure false alarms on real modern ham.

## Recommendation

1. Use two real modern-benign sets as TEST-ONLY false-alarm sets. Do not train on them.
   - **India inbox set** (English, 1,206 rows, dates 2019-2025): business SMS from registered Indian sender headers. Bank OTPs, card and UPI transaction alerts, delivery updates, telecom notices, booking confirmations. This set matches the three largest IMC scam types (banking, delivery, telecom) and is the main check.
   - **MOZ set** (Portuguese, 1,608 rows, dates mostly 2019-2023): crowd-sourced legitimate SMS from Mozambique. M-Pesa and bank transfer confirmations plus personal texts. Use it as a secondary, multilingual check (IMC has 280 Portuguese scams).
2. Report, for EVERY model (`word_2012`, `char_2012`, `word_fixed`, `char_fixed`, `fix_plus_benign`, the rule baseline), the false-alarm rate on each set separately, at the frozen threshold, with a Wilson 95% interval. Name the metric "false alarms on real modern legitimate SMS (India inbox / Mozambique)".
3. Keep the synthetic benign twins as they are. The new sets do not replace them. Real data answers "is the confound real?"; the twins answer "can the model tell a scam from its exact legitimate twin?".
4. Do not add these sets to training tonight. Reason: they are the only real evidence about the source confound. If you train on part of them, the test half shares one inbox and many templates with the training half, and the test becomes optimistic. If a training variant is still wanted later: split the India set by `sender` with a seeded `GroupShuffleSplit` (50/50), train on one group of senders only, test on the other, and label the variant clearly.

Interpretation guide (not a result): if `*_fixed` models flag far more of these real modern legitimate messages than `*_2012` models, the source confound is real and must be stated. If `fix_plus_benign` lowers that rate, the synthetic-benign fix works on real data too.

## Loading code

Run from the project root. The loader uses the local file and falls back to the pinned Hugging Face revision.

```python
import re
from pathlib import Path
import pandas as pd

EXTRA = Path("data/raw/extra")
URLS = {
    "india": "https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-sample-10k/resolve/2b6de4910ab9337a92f1b672d2de8ed11c6a3805/sample_10k.csv",
    "moz": "https://huggingface.co/datasets/MOZNLP/MOZ-Smishing/resolve/1092f9d9a545b29ae6be030ee9713b615fc2d987/test.csv",
}
DLT_SENDER = r"^[A-Z]{2}-?[A-Za-z0-9]{5,6}(?:-[A-Z])?$"   # Indian TRAI business header, e.g. VM-SCBANK, JX-ICICIO

def _key(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _read(local, url):
    p = EXTRA / local
    return pd.read_csv(p if p.exists() else url)

def load_extra_benign(uci_texts, imc_texts):
    """Real modern legitimate SMS. TEST ONLY. Columns: text, source, lang, sender, label (=0)."""
    ban = {_key(t) for t in uci_texts} | {_key(t) for t in imc_texts}
    a = _read("gandharvbakshi_sms_sample_10k.csv", URLS["india"])
    a = a[(a["classification_status"] != "synthetic") & a["sender"].fillna("").str.match(DLT_SENDER)]
    a = a.assign(text=a["sms_text"].astype(str), source="india_inbox_2019_2025", lang="en_or_hi", sender=a["sender"])
    b = _read("moz_smishing.csv", URLS["moz"])
    b = b[(b["label"] == "Legitimate") & (b["source"] == "sms")]
    b = b.assign(text=b["text"].astype(str), source="moz_smishing_2025", lang="pt", sender=None)
    cols = ["text", "source", "lang", "sender"]
    out = pd.concat([a[cols], b[cols]], ignore_index=True)
    out["k"] = out["text"].map(_key)
    out = out[~out["k"].isin(ban)].drop_duplicates("k").drop(columns="k").reset_index(drop=True)
    out["label"] = 0
    return out

# usage
uci = pd.read_csv("data/raw/SMSSpamCollection", sep="\t", header=None, names=["label", "text"], quoting=3)
imc = pd.read_csv("data/raw/imc25_smishing.csv")
xb = load_extra_benign(uci["text"], pd.concat([imc["text"].dropna(), imc["translation"].dropna()]))
# expected: 2814 rows = india_inbox_2019_2025 1206 + moz_smishing_2025 1608
```

Evaluation sketch (same normaliser and frozen thresholds as the main pipeline):

```python
from src.scam_drift import normalise
xb["norm"] = xb["text"].map(normalise)          # raw URLs become tok_url, like IMC <URL>
for name, m in models.items():
    th = thresholds[name]["threshold"]
    for src, g in xb.groupby("source"):
        flagged = (m.predict_proba(g["norm"])[:, 1] >= th)
        k, n = int(flagged.sum()), len(g)       # false alarms; report k/n with a Wilson 95% interval
```

The loader was run on 2026-11-17 with `.venv` and returned 2,814 rows (1,206 + 1,608). No model was evaluated on these sets yet; all false-alarm numbers are UNKNOWN until the pipeline runs.

## Measured facts about the two chosen files

| Fact | India inbox (`gandharvbakshi_sms_sample_10k.csv`) | MOZ (`moz_smishing.csv`) |
|---|---|---|
| Real or synthetic | Real messages from one person's phone, by inspection: registered sender headers, the owner's first name in many messages, real brands. The file also has 1,632 rows marked `synthetic` (removed). Provenance is the author's claim; no paper. | Real. Crowd-sourced through a WhatsApp campaign, screenshots transcribed (paper, AfricaNLP 2025). |
| Raw rows | 10,000 | 2,561 (2,009 legitimate, 552 smishing) |
| Rows kept | 1,206 | 1,608 |
| Exact copies of UCI (lower-case, whitespace-collapsed) | 162 in the raw file (146 UCI ham); 0 after filtering | 0 |
| Exact copies of IMC text or translation | 4 in the raw file; 0 after filtering | 0 |
| Language | English (1,188 of 1,206 rows are >95% ASCII), a few Hindi | Portuguese (Mozambique, microtext) |
| Dates written in the text (dd-Mon-yy, dd/mm/yy) | 2019: 34, 2020: 36, 2021: 15, 2022: 12, 2023: 18, 2024: 17, 2025: 15 | 2019: 22, 2020: 152, 2021: 105, 2022: 57, 2023: 74 |
| Rows with a URL | 441 | 31 |
| Template diversity | 831 distinct digit-masked 60-character prefixes; 555 senders | 1,345 distinct prefixes |
| Licence | MIT (card) | CreativeML OpenRAIL-M (card) |

## Caveats

1. The India set is ONE person's inbox (mostly Bengaluru brands: ICICI, Yes Bank, Swiggy, Licious, Vi). It is not a sample of all legitimate SMS. Report it as "one real inbox", not as a population rate.
2. A registered sender header is strong but not perfect evidence of a legitimate message. The `is_phishing_original` label is not usable (659 of 1,497 header rows are labelled phishing; the rows we checked are ordinary notices). We filter by header, not by that label.
3. Many India rows share templates (for example card-debit alerts). Count-based rates are correlated; Wilson intervals are therefore too narrow. Also report the number of distinct senders.
4. Real ham has raw URLs and real names. IMC scams have `<URL>` and `<NAMED_ENTITY>` placeholders. `normalise()` maps raw URLs to `tok_url`, so URLs match. Names do not: a real first name is a token the scam side never shows. Mention this as a residual source difference.
5. The MOZ legitimate class contains personal money requests ("send me the value on M-Pesa") from known contacts. They look like "hey mum/dad" scams. They are legitimate by the dataset's label. Treat false alarms on them as expected hard cases, and say so.
6. Privacy: both files contain first names and phone-number-like strings. Do not quote raw messages in public deliverables. Decide before publication whether to commit the CSVs (see `data/raw/extra/README.md`).
7. Neither set is the target user's real phone (non-native-speaking older adults, US/EU scams). They are the closest real modern legitimate SMS we found that are public and licensed.

## All candidates checked

| Dataset | Real or synthetic | Year | Size (ham) | Language | Licence | UCI overlap (exact, lower-cased) | Verdict |
|---|---|---|---|---|---|---|---|
| gandharvbakshi/SMS-dataset-sample-10k (free preview) | Mixed: real inbox rows + 1,632 synthetic + 162 UCI copies | 2025 (texts 2019-2025) | 10,000 (1,206 kept) | en, some hi/bn/te/kn | MIT | 162 rows | **USE (test only), filtered** |
| MOZNLP/MOZ-Smishing | Real, crowd-sourced | 2025 (texts 2019-2023) | 2,561 (2,009 legit, 1,609 SMS) | pt | OpenRAIL-M | 0 | **USE (test only)** |
| gandharvbakshi/SMS-dataset-OTP-OTP_INTENT_Phishing (full 73,470 rows) | Same source as the preview | 2025 | 73,470 | en | MIT, but gated (manual approval) | not checked | Not used: gated |
| alusci/sms-otp-spam-dataset | Synthetic templates | 2025 | 10,000 (8,100 "valid") | en | MIT | 0 | Reject: templated; "not valid" rows include ordinary OTPs (label noise) |
| CloveAI/india-spam-sms | Synthetic templates (fill errors such as "appointment is confirmed for 16725 at August") | 2025 | 20,010 (14,059 ham) | en | MIT | 0 | Reject: no card, no provenance, 780 internal duplicates |
| Ridham115/indian-scam-sms-synthetic-audited | Synthetic (LLM), audited | 2026 | 1,580 (783 safe) | en, hinglish, hi, 4 code-mixed | CC BY 4.0 | 0 | Optional: independent third-party synthetic hard negatives; not downloaded. URL: `https://huggingface.co/datasets/Ridham115/indian-scam-sms-synthetic-audited/resolve/main/data/synthetic_audited.csv`, filter `label == "safe"` |
| trannguyenthaituan/vietnamese_sms_dataset | Real (card), PII replaced with tokens | 2026 | 2,991 (2,193 legit) | vi | CC BY 4.0 | 0 | Runner-up: real and clean, but IMC has 1 Vietnamese scam, so low relevance. URL: `.../resolve/main/full_dataset.csv`, `label == 0` |
| Mendeley "SMS Phishing Dataset" (Mishra & Soni 2022, f45bkkt8pr) | Ham reused from UCI | 2022 | 5,971 (4,844 ham) | en | CC BY 4.0 | 4,319 of 4,844 ham are exact UCI ham | Reject: not modern ham |
| Mendeley "Balanced Dataset ... using LLMs" (Munoz & Islam 2025, vmg875v4xs) | Described as LLM-made, but ham is mostly UCI | 2025 | 10,191 (3,397 ham) | en | CC BY 4.0 | 3,026 of 3,397 ham are exact UCI ham | Reject: ham is UCI |
| VusalShahbazovAz/smishing-AZ-SC | Hybrid: translated UCI + 20 users + self-generated (paper, section 2.2) | 2026 | 4,538 (3,037 ham; 2,750 ham have no sender) | az | CC BY 4.0 | 3 exact (others are translations) | Reject: ham mostly translated UCI |
| shariul-islam/bengali-sms-smishing-dataset | Unclear, looks authored; a "normal" row asks for money urgently | 2025 | 7,005 (2,240 normal in train+test splits) | bn, en, banglish | MIT | 0 | Reject: provenance unclear, label noise |
| rasheq/scam-shield-sms | Derived: IMC 2025 scams + Mishra & Soni ham + synthetic | 2026 | 24,072 | en | CC BY 4.0 (card) | via Mishra & Soni | Reject: contains our IMC test scams (leakage) and UCI ham |
| notd5a/malicious-benign-sms-mms-dataset | Mixed, includes AI-generated rows | 2026 | 442,282 | en | CC BY-NC 4.0 | not checked | Reject: non-commercial, provenance mixed |
| Super SMS Dataset (Salman, Ikram, Kaafar, IEEE Access 2024, doi 10.1109/ACCESS.2024.3364671) | UNKNOWN | 2024 | >68k, 61% ham (search summary) | en | UNKNOWN | UNKNOWN | Not verified: no public file found on HF/GitHub in this session |
| useKled/phishing-text-messages, KR smishing sets | Screenshots (commercial) / scams only, NC | - | - | - | commercial / NC | - | Reject |

## Sources

- https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-sample-10k
- https://huggingface.co/datasets/MOZNLP/MOZ-Smishing and https://aclanthology.org/2025.africanlp-1.23.pdf
- https://huggingface.co/datasets/Ridham115/indian-scam-sms-synthetic-audited
- https://huggingface.co/datasets/trannguyenthaituan/vietnamese_sms_dataset
- https://data.mendeley.com/datasets/f45bkkt8pr and https://data.mendeley.com/datasets/vmg875v4xs
- https://huggingface.co/datasets/VusalShahbazovAz/smishing-AZ-SC and https://jpit.az/en/journals/355
- Hugging Face API `https://huggingface.co/api/datasets/<id>` for licence tags, file lists and revisions.
