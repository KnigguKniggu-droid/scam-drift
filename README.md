# Scam Drift

**Track:** Finance
**Team:** Scam Drift team (names withheld for the blind Round 1 review; they are on the submission form)

This project is a prototype and is not financial advice.

## The problem
People reported $470 million in losses to text-message scams in 2024 ([FTC Data Spotlight, April 2025](https://www.ftc.gov/news-events/data-visualizations/data-spotlight/2025/04/top-text-scams-2024)). Our user is an older adult (a grandparent) and the family member who sets up their phone. The moment: a text arrives that claims to be from a bank, a courier or a pharmacy, and before tapping the link the grandparent pastes it in. Many simple scam filters still learn from the 2012 UCI SMS Spam Collection. We ask: **does a 2012-trained filter still catch today's scam texts, which scam types slip through, and can we fix it without false alarms on genuine modern texts?**

## What we built
A Gradio app (`app.py`): paste a text, get RED ("likely scam, do not tap or reply"), YELLOW ("ask a family member first") or GREEN ("no warning signs found", never "safe") and the words behind it. `src/scam_drift.py` runs the seeded experiment in under a minute on CPU; `scam_drift.ipynb` walks through it. Three examples, picked by a fixed rule in the code (`results/demo_examples.csv`):

| Text (shortened) | Truth | Model 2012 p (flag at 0.32) | Fixed model p (flag at 0.24) | App shows |
|---|---|---|---|---|
| "Hey M>itchel ... still interested in this >> `<URL>`" (2022+ report) | scam | 0.3119 | 0.9074 | GREEN (missed) |
| "`<NAMED_ENTITY>`, [I] need to know if you are available ... Need you to handle a task" (2022+ report) | scam | 0.0307 | 0.0628 | GREEN (missed) |
| "Your First Harbor Bank verification code is 482913 ... We will never call or text to ask for this code." (synthetic) | genuine | 0.6827 | 0.9273 | YELLOW (false alarm) |

## What we added
We started from suggested project **4.2.1 Scam text filter** (TF-IDF + logistic regression on SMS spam) and added our own user (above), our own data and our own question (drift):
- **Real modern scams:** the IMC 2025 "Fishing for Smishing" reports, split **by report year** (dated rows run 2015-2024, mostly 2017-2023).
- **Benign twins:** 60 synthetic genuine-style texts (bank codes, fraud alerts, couriers, pharmacy, doctors) and 40 look-alike scams, written with AI assistance before the first model run and never trained on.
- **Compared with the organisers' sample** (ScamCheck, 40 hand-written texts), we test 1,080 real 2022+ reports with a time split, 12,364 undated and 8,866 non-English real reports, run a dataset-shortcut check (ROC AUC 0.9893), and measure false alarms on 60 genuine-style texts.

## How it works
**Data.** UCI: 5,135 unique messages, stratified 80/20 split (test: 1,027, of which 124 spam). IMC25: 15,254 unique English reports. Only rows whose screenshot timestamp shows a year can be dated: 1,809 scams from 2015-2021 may be used for training; 1,080 scams from 2022-2024 are the untouched test; 12,364 undated scams are never trained on. One normaliser runs on every source: links, phones, emails, money, dates and numbers become shared tokens, then lowercase.

**Model.** TF-IDF word 1-2 grams + logistic regression: it is the brief's baseline, runs in seconds on CPU, and its weights explain each verdict word by word. *Model 2012* learns from UCI only. The *fixed model* adds the 2015-2021 scams; its only genuine examples are still 2012 UCI texts. Thresholds come from 5-fold out-of-fold predictions on training data, with a missed scam costing 5x a false alarm.

## Results
**Main takeaway: the 2012 filter misses about a quarter of 2022+ scams (recall 0.7565). Retraining on modern scams alone lifts recall to 0.9657 but flags 59 of 60 genuine-style texts. The missing ingredient is modern genuine texts, not more scam data** (an exploratory test with one real inbox shows they help but are not enough on their own: [details](docs/RESULTS_DETAIL.md)).

| Model | UCI test P / R / F1 | 2022+ scams caught (n=1,080) | False alarms, 60 genuine-style texts (95% CI) |
|---|---|---|---|
| Always "not scam" | undefined / 0.0 / 0.0 | 0.0 | 0.0 |
| Rule: link or urgency word | 0.8364 / 0.371 / 0.514 | 0.6185 | 0.1 (0.0466-0.2015) |
| Rule: link only | 0.8636 / 0.1532 / 0.2603 | 0.4065 | 0.05 (0.0171-0.137) |
| Model 2012 | 0.936 / 0.9435 / 0.9398 | 0.7565 | 0.5167 (0.3931-0.6383) |
| Fixed model | 0.7532 / 0.9597 / 0.844 | 0.9657 | 0.9833 (0.9114-0.9971) |
| Model 2012 + link (app's RED) | 0.95 / 0.1532 / 0.2639 | 0.3824 | 0.0 (0.0-0.0602) |

The modern test holds only scams, so precision is undefined there. The link-gated row and the app's tiers are post-hoc. Fixed model + link gate is not listed: on every 2022+ scam and benign twin it equals "link only".

1. **A step, not a slide.** Model 2012 catches 0.9435 of held-out 2012 spam but 0.7565 of 2022+ scams, with no clear decline inside the reports (2017: 0.8175, n=126; 2023: 0.7751, n=378). Part of the gap is dataset style (shortcut AUC 0.9893) and repeated UCI templates: on UCI test spam with no near-copy in training (cosine < 0.9), Model 2012 catches 0.9205.
2. **The fix floods the user.** Every formal text in its training data was a scam, so it learned "formal = scam".
3. **Versus the rule.** Model 2012 beats the link-or-urgency rule on UCI F1 (0.9398 vs 0.514) and 2022+ recall (0.7565 vs 0.6185), but not on false alarms (0.5167 vs 0.1). Only the link-gated Model 2012 has fewer (0.0), and it catches just 0.3824.
4. **Who it fails.** "Wrong number" openers (0.0833, n=24), "hey mum/dad" (0.0, n=4; indicative only), scams under 80 characters (0.4934, n=152), and non-English readers (0.508 on raw text vs 0.6959 on English translations, n=8,866). We have no age or gender data, so we cannot check those groups.

**Where it fails and why** (fixed model; 37 of 1,080 missed: 17 "others", 10 "wrong number", 6 "spam", 3 "hey mum/dad", 1 "delivery"):

| Message (shortened) | Error | Our hypothesis |
|---|---|---|
| "How are you doing" | missed scam | Opener only; the scam comes later in the chat. |
| "Ηello аll, guуsǃ I knоw..." | missed scam | Cyrillic look-alike letters make every word unknown. |
| "Fuck off" | missed "scam" | Label noise: a user report that is not a scam. |
| "Reminder: your credit card payment of $85.00 is due..." | false alarm | Money + card words match banking scams. |
| "Out for delivery: your order #48211 will arrive today by 8pm." | false alarm | Courier wording is now dominated by scams. |

More detail: [docs/RESULTS_DETAIL.md](docs/RESULTS_DETAIL.md).

## What we'd do next
- Add real modern genuine texts (consented, anonymised the same way) as negatives.
- Keep the link's domain as a feature, use multi-message context, fold look-alike letters, train on many languages.
- Test the warning wording with older users.

## Sources
- UCI SMS Spam Collection, Almeida & Gomez Hidalgo (2011): https://archive.ics.uci.edu/dataset/228/sms+spam+collection (CC BY 4.0)
- "Fishing for Smishing", Agarwal, Papasavva, Suarez-Tangil, Vasek, IMC 2025: https://github.com/reportsmishing/Smishing-Dataset-IMC25 , https://doi.org/10.1145/3730567.3764431 (CC BY 4.0)
- FTC Data Spotlight "Top text scams of 2024" (April 14, 2025): https://www.ftc.gov/news-events/data-visualizations/data-spotlight/2025/04/top-text-scams-2024
- Synthetic benign twins (`data/benign_twins.csv`): written with AI assistance for this project; test only.
- Libraries: scikit-learn https://scikit-learn.org , pandas https://pandas.pydata.org , NumPy https://numpy.org , matplotlib https://matplotlib.org , Gradio https://gradio.app , joblib https://joblib.readthedocs.io , Jupyter/nbconvert https://jupyter.org
- AI tools: Claude (Anthropic) via Claude Code https://claude.com/claude-code wrote and ran the code and drafted the docs; the team reviewed every output. ChatGPT (OpenAI) https://chatgpt.com , Gemini (Google) https://gemini.google.com and Claude chat critiqued the idea and method ([docs/CONSULT_LOG.md](docs/CONSULT_LOG.md)).
- Full list: [CREDITS.md](CREDITS.md)

## How to run
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
python src/scam_drift.py      # full pipeline; writes results/, figures/, models/
python app.py                 # Gradio demo at the local URL it prints
```
Put `SMSSpamCollection` and `imc25_smishing.csv` in `data/raw/` (the notebook's first cell downloads both and checks their SHA-256). The notebook has run locally; it has not yet been tested in Google Colab.

This project is a prototype and is not financial advice.
