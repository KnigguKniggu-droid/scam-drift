# Scam Drift

**Track:** Finance
**Team:** Kartikeya Lathi and William Lu (Jordan High School)

This project is a prototype and is not financial advice.

> **post-deadline v2 (Nov 18).** The judged hackathon entry is git `main` at commit `01abbc9`; it does not change. This README describes the post-deadline branch. Every number comes from `results/metrics.json` (seeded run of `src/scam_drift.py`; v2 results under the key `v2`).

**Can yesterday's AI recognise tomorrow's scams?** Only partly. A filter trained on 2012 texts catches 75.7% of scams reported in 2022-24. Retraining it on new scams alone catches 96.6%, but it also flags 99.5% of real modern legitimate texts (held-out Indian inbox), so that "fix" is not a win. Our prototype warn-only triage warns on 65.7% of new scams and on 22.9% of those legitimate texts: false alarms on real modern texts remain high.

## The problem
People reported $470 million in losses to text-message scams in 2024 (FTC). Our user is an English-reading grandparent and the family member who set up their phone. The moment of use: a text claims to come from a bank, courier or government office; before tapping the link, the grandparent pastes it into the checker and gets RED, YELLOW or GREEN. Many simple filters still learn from 2012 UCI SMS data. Do they catch today's scams, whom do they fail, and can we fix them without false alarms on genuine modern texts? The tool currently fails non-English readers (see "every group" below).

## What we built
- `src/triage.py`, a warn-only three-tier check. **RED** "Likely scam - do not tap, do not reply": the model flags and the text has a link or phone number. **YELLOW** "Ask family before replying": the model flags without one, or a rule fires (asks for a code, PIN or password; "hi mum", "new number" or "wrong number" opener). **GREEN** "No warning signs found", never "safe".
- `app.py`, a Gradio demo that shows the verdict and its reasons; `src/scam_drift.py`, the seeded experiment (125.4 s on CPU); `scam_drift.ipynb`, the walk-through.
- Real example (2022-24 report): "Apple: Your Apple Pay has been suspended due to unusual activity. Please visit: `<URL>` ..." -> **RED**; top words "suspended", "[a web link]".

## What we added
We started from suggested project **4.2.1 Scam text filter**. The organizers' sample ScamCheck tested 40 hand-written texts. Unlike it, we:
- test thousands of real reported scams (IMC 2025 "Fishing for Smishing") across report years, scam types and languages: 1,080 dated 2022-24, 12,364 undated, 8,866 non-English;
- show the naive fix's (retrain on new scams) false-alarm failure on real modern legitimate SMS: an Indian inbox (1,206) and Mozambique (1,608, Portuguese, never trained on);
- evaluate a three-tier warn-only design. **Disclosure:** the tiers, the YELLOW rules and the strict-threshold rule were designed after we saw the v1 results (post-hoc), and the India and Mozambique legit sets were looked at during exploration. Only the model and its threshold rule were then chosen on validation data. Treat the triage numbers as optimistic.

## How it works
One normaliser turns links, phones, money, dates and numbers into shared tokens. Models: TF-IDF n-grams + logistic regression. Training: UCI 2012, scams reported up to 2021, and half of the India inbox (split by brand or template group; 0 brands on both sides). Test: 2022-24 scams, the other India half, Mozambique, and 30 synthetic legitimate texts (written with AI assistance). The model (`char_fix_plus_real_ham`) and its threshold rule were chosen on validation data only (2021 scams, India training texts). Its threshold, 0.94, aimed at 10% false alarms on India training texts; on held-out India texts the model alone flags 20.4%, about double.

## Results
![Three-tier triage shares per test set](figures/triage_tiers.png)

| Model | UCI 2012 test: precision / recall | 2022-24 scams warned (n=1,080) | India legit warned, held-out groups (n=608, 95% CI) | Mozambique legit warned (n=1,608) | Synthetic legit warned (n=30, 95% CI) |
|---|---|---|---|---|---|
| Always "not scam" | undefined / 0% | 0% | 0% | 0% | 0% |
| Rule: link only | 86.4% / 15.3% | 40.7% | 47.4% (43.4-51.3) | 2.0% | 6.7% (1.9-21.3) |
| 2012 model | 93.6% / 94.4% | 75.7% | 82.2% (79.0-85.1) | 39.4% | 36.7% (21.9-54.5) |
| Naive fix (+ new scams) | 75.3% / 96.0% | 96.6% | 99.5% (98.6-99.8) | 62.5% | 100% (88.7-100) |
| **Prototype triage** (RED or YELLOW) | 96.8% / 73.4% | 65.7% | 22.9% (19.7-26.4) | 2.2% | 16.7% (7.3-33.6) |

- **Precision where it matters.** Modern test sets hold only scams or only legit texts, so we estimate precision at an assumed 5% scam rate (not measured), against held-out India texts: prototype triage 13.1%, 2012 model 4.6%, naive fix 4.9%, link-only rule 4.3%. Even our best option gives about 7 false alarms per real warning.
- **Trade-off against the 2012 model:** the triage warns on fewer new scams (65.7% vs 75.7%) but on far fewer held-out India legit texts (22.9% vs 82.2%).
- **Against the link-only rule:** the triage warns on more new scams (65.7% vs 40.7%) and on fewer India legit texts (22.9% vs 47.4%). It does not beat the rule on Mozambique (2.2% vs 2.0%) or synthetic legit texts (16.7% vs 6.7%).
- **Fix ingredients.** Real modern legit texts in training lower India false alarms from 99.5% to 65.6%; the strict threshold lowers them further to 22.9%, still about 1 in 4 legit texts.
- **A step, not a slide.** The 2012 model catches 94.4% of 2012 test spam (92.1% without near-copies), then 74.5-83.5% per report year 2017-2023: a one-time era shift, not a yearly decline. Details, template-safe numbers and the learning curve: [docs/RESULTS_DETAIL.md](docs/RESULTS_DETAIL.md).

**Does it work equally well for every group?** No (prototype triage, 2022-24 scams). Per language: it warns on 16.1% of raw non-English scams vs 68.3% when we score the dataset's English translation (an "oracle": the best case if translation were perfect). Per scam type: "wrong number" 25.0% (n=24) vs banking 84.4% (n=468). Per length: under 80 characters 30.3% (n=152). Weakest: non-English readers without translation.

**Where it fails.** Five real 2022-24 reports left GREEN, picked by a fixed rule (the shortest text of 40+ characters from each of the 5 scam types with the most misses): "Tap to reset your Instagram password: `<URL>`"; "Collect request from PAYU for `<DATE_TIME>`"; "Breaking: USA Says Goodbye to Dr Oz:`<URL>`"; "`<URL>` has been reported as a malware site."; "Dear IEC Holder, It is mandatory to update your IEC before `<DATE_TIME>`...". Several read like genuine notices, so some may be label noise (our assumption, not checked). Two false alarms (synthetic, written with AI assistance) -> YELLOW: "Your copay for today's pickup is $10.00. Pay at the counter."; "Your parcel will arrive tomorrow between 10am and 2pm. No action needed."

**What we learned.** More scam data does not fix an old filter; modern legitimate texts and a false-alarm budget do more, but not enough. One recall number hides the cost: measure false alarms on real texts from the same era. Time splits leak: templates recur (153 of 1,080 test rows).

## What we'd do next
- Collect consented, anonymised legitimate texts from many inboxes and countries.
- Add on-device translation for non-English readers, then test the warning wording with older non-native speakers.
- Add multi-message context (many misses are short openers or fragments).

## Sources
- UCI SMS Spam Collection (CC BY 4.0): https://archive.ics.uci.edu/dataset/228/sms+spam+collection
- "Fishing for Smishing", IMC 2025 (CC BY 4.0): https://github.com/reportsmishing/Smishing-Dataset-IMC25
- India SMS inbox sample (MIT): https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-sample-10k
- MOZ-Smishing (OpenRAIL-M): https://huggingface.co/datasets/MOZNLP/MOZ-Smishing
- FTC "Top text scams of 2024": https://www.ftc.gov/news-events/data-visualizations/data-spotlight/2025/04/top-text-scams-2024
- Full list with licences: [CREDITS.md](CREDITS.md). Full tables: [docs/RESULTS_DETAIL.md](docs/RESULTS_DETAIL.md).

## How to run
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
python src/scam_drift.py      # full seeded pipeline (about 2 min on CPU); writes results/, figures/, models/
python src/triage.py          # prototype triage on example texts
python app.py                 # Gradio demo of the triage at the local URL it prints
jupyter nbconvert --to notebook --execute --inplace scam_drift.ipynb
```
By default the notebook loads the saved `results/metrics.json` and re-scores the saved model live. Set `RUN_PIPELINE = True` in its section 1 to rerun the whole seeded pipeline (about 2 min on CPU); the live check then reproduces `metrics.json`. In Colab, run the clone cell at the top first.
Put `SMSSpamCollection` and `imc25_smishing.csv` in `data/raw/` (the notebook's first cell downloads both and checks their SHA-256). The pipeline downloads the India and Mozambique sets from pinned Hugging Face revisions; they are not stored in this repository because the texts contain first names.

## Repository map
| Path | What it is |
|---|---|
| `src/scam_drift.py` | Pipeline: data, splits, models, thresholds, all v1 and v2 analyses, figures, `results/metrics.json` |
| `src/triage.py` | Prototype three-tier triage, `triage(text)` |
| `scam_drift.ipynb` | Executed walk-through of every v2 analysis |
| `app.py` | Gradio demo: triage verdict, reasons, 2012-filter comparison |
| `results/` | `metrics.json` (source of every number) and CSV tables |
| `figures/` | Charts used here and in the results doc (`lead_chart_v2.png` = v2 lead chart) |
| `models/` | Saved models; `model_shipped.joblib`, `shipped_config.json` |
| `data/benign_twins.csv` | 100 synthetic texts (written with AI assistance), test and stress set |
| `docs/RESULTS_DETAIL.md` | Full results (generated by `tools/write_results_detail.py`) |
| `docs/PLAN.md`, `docs/V2_SPEC.md`, `docs/CONSULT_LOG.md` | Plan, v2 spec, AI consultation log |
| `CREDITS.md` | Datasets, libraries and AI tools with licences |

## AI tools we used
- **Claude (Anthropic) via Claude Code** wrote much of the code under the team's direction and helped plan and audit the method. The team reviewed the code, re-ran every result and can explain every part.
- **ChatGPT (OpenAI), Gemini (Google) and Claude chat** acted as critics of the idea, the method and the results. Their advice and what we did with it: [docs/CONSULT_LOG.md](docs/CONSULT_LOG.md).
- The synthetic legitimate and scam twins were written with AI assistance and are labelled synthetic everywhere.

## Pipeline
```mermaid
flowchart LR
    U[UCI 2012 SMS] --> N[Shared normaliser<br/>links, phones, money,<br/>dates, numbers -> tokens]
    I[IMC25 scam reports<br/>English + translations] --> N
    H[Real legit SMS<br/>India inbox, Mozambique] --> N
    S[Synthetic twins<br/>AI-assisted, labelled] --> N
    N --> SP[Splits: report year 2021/2022,<br/>India by brand or template group,<br/>cluster-safe test]
    SP --> T[TF-IDF + logistic regression<br/>2012, naive fix, + real legit]
    T --> TH[Thresholds on training data only<br/>cost 5:1 or 10% false-alarm budget]
    TH --> SEL[Select on validation:<br/>2021 scams + India train half]
    SEL --> TR[Three-tier triage<br/>RED / YELLOW / GREEN]
    TR --> E[Evaluate: 2022-24 scams, India held out,<br/>Mozambique, synthetic, non-English]
    E --> MJ[results/metrics.json]
```

This project is a prototype and is not financial advice.
