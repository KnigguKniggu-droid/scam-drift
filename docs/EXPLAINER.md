# Scam Drift explainer: code, formulas and hard questions

Purpose: help Kartikeya explain every part of the project in the finals Q&A.
Numbers come only from `results/metrics.json`, `results/real_ham_probe.json` and `results/real_ham_fix_probe.json`. Line numbers refer to the files on branch `post-deadline` on 2026-11-17.

Contents:
1. The project in 6 sentences
2. Every function, in plain English
3. Formula cheat sheet
4. 15 hard judge questions with honest answers

## 1. The project in 6 sentences
1. Model 2012 is TF-IDF + logistic regression trained on the 2012 UCI SMS Spam Collection. It catches 0.9435 of held-out 2012 spam, but 0.7565 of 1,080 real English scams reported in 2022-2024 (IMC 2025 "Fishing for Smishing").
2. The fixed model ("naive fix") adds 1,809 scams reported in 2015-2021. It catches 0.9657 of the 2022-24 scams.
3. But it flags 59 of 60 synthetic genuine-style texts (0.9833) and 597 of 600 real legitimate texts from held-out brands in one India inbox (0.995).
4. Cause: in its training data every formal notification is a scam and every genuine text is 2012 personal chat, so it learns "formal = scam".
5. Adding 606 real legitimate texts from 140 other brands keeps recall at 0.9593 and lowers false alarms on the held-out brands to 0.7117. That is better, but not enough.
6. The app is warn-only (RED / YELLOW / GREEN from Model 2012 plus a link or phone check). It is a prototype, not a product, and not financial advice.

## 2. Every function, in plain English

### 2.1 `src/scam_drift.py` (the full pipeline)
Module constants (lines 21-80): `SEED = 42` makes every run repeatable. `COST_FN = 5.0` and `COST_FP = 1.0` (lines 32-33) say a missed scam costs 5 times a false alarm. `TRAIN_LAST_YEAR = 2021` (line 35) is the time-split year. `PLACEHOLDER_MAP` (line 42) maps the dataset's anonymisation tags (for example `<URL>`, `<PHONE_NUMBER>`) to shared tokens. The regular expressions on lines 56-80 find emails, links, money, dates, phone numbers and numbers.

| Function | Line | What it does | Why it exists |
|---|---|---|---|
| `_ph_sub` | 83 | Replaces one tag such as `<URL>` with its shared token from `PLACEHOLDER_MAP` (for example `tok_url`). Unknown tags become their lowercase name. Named-entity tags become a space. | The IMC25 authors anonymised their texts with tags; UCI has no tags. One token set for both datasets stops the model from learning "has a tag = IMC25". Named-entity tags are deleted because UCI has no equivalent. |
| `normalise` | 88 | Unescapes HTML, maps tags, fixes "[.]" obfuscated dots, then replaces emails, links, money, dates, phone numbers (7+ digits) and other numbers with `tok_email`, `tok_url`, `tok_money`, `tok_date`, `tok_phone`, `tok_num`. Lowercases and collapses spaces. | Every source goes through the same function, so a link in 2012 and a link in 2023 look identical to the model. It also hides personal data such as phone numbers. The cost: the link's domain is lost, so an official link looks like a scam link. |
| `_phone` (inside `normalise`) | 100 | Turns a digit run into `tok_phone` only if it has 7 or more digits. | Short digit runs (prices, codes) are not phone numbers. |
| `_read_text` | 113 | Reads a file as text, trying UTF-8, then cp1252, then latin-1. | The raw data files use mixed encodings. |
| `load_uci` | 123 | Reads the UCI file (label, tab, text), normalises each text, drops texts that appear with both labels, then drops exact duplicates after normalisation. | Duplicates would sit on both sides of the train/test split and inflate results. Contradictory labels are noise. Result: 5,574 raw rows become 5,135. |
| `extract_year` | 145 | Finds a year (2015-2025) in the IMC25 `time` field, as a 4-digit year or a d/m/yy date. Returns NaN if none. | The `time` field is the raw screenshot timestamp ("Today 8:15 AM"). Only rows that show a year can be dated (5,295 of 33,869). Undated rows are never trained on. |
| `load_imc` | 159 | Reads the IMC25 CSV, adds the `year` column and fills a missing `scam_type` with "unlabelled". | Loads the modern scam reports. |
| `length_bucket` | 167 | Puts a message in one of 4 length groups: <80, 80-159, 160-319, 320+ characters. | Checks whether short scams are harder (they are: Model 2012 catches 0.4934 of scams under 80 characters, n=152). |
| `rule_flag` | 185 | Flags a text if it has a link or one of 12 urgency words ("urgent", "verify", "click", "prize" and others). | A simple baseline. A model must beat a rule to be worth it. |
| `link_flag` | 190 | Flags a text if it has a link. | The simplest "warn before you tap" rule; second baseline. |
| `triage` | 200 | Returns RED if Model 2012's probability is at or above its threshold and the text has a link; YELLOW if it is above the threshold with no link; GREEN otherwise. | The app's three colours. Post-hoc design: chosen after the first results. The fixed model is not used because it flags almost every genuine-style text. |
| `friendly_explain` | 210 | Calls `explain`, drops n-grams made only of stop words ("to the"), and writes tokens in plain words (`tok_url` becomes "[a web link]"). Returns the top k. | The app shows the words behind a verdict in language an older adult can read. |
| `make_word_model` | 224 | Builds a pipeline: TF-IDF on words and word pairs (1-2 grams, `min_df=2`, sublinear tf, single-letter tokens kept), then logistic regression (`C=10`, balanced class weights). | The main model. It is the brief's suggested baseline, trains in seconds and is explainable. |
| `make_char_model` | 235 | Same, but on character 2-5 grams inside word boundaries (`char_wb`), up to 200,000 features. | A robustness check: characters handle misspellings and other languages better. It shows the same pattern (char_fixed: 0.9602 recall, 0.95 false alarms on the synthetic twins). |
| `pick_threshold` | 246 | Tries every threshold from 0.02 to 0.98 in steps of 0.01 and keeps the one with the lowest cost 5 x missed scams + 1 x false alarms. | The threshold reflects the user's costs and is chosen without the test data. Model 2012: 0.32 (cost 142 = 5 x 19 + 47). Fixed model: 0.24. |
| `oof_proba` | 259 | 5-fold stratified cross-validation on the training data: each message gets a probability from a model that did not see it. | Gives honest validation predictions for `pick_threshold` without touching the test sets. |
| `explain` | 268 | For one text, multiplies each n-gram's TF-IDF value by its logistic-regression weight, keeps the positive ones and sorts them. | Each product is that n-gram's push on the log-odds of "scam". This is an exact decomposition for a linear model, not an approximation. |
| `prf` | 282 | Counts TP, FP, FN, TN and returns precision, recall, F1, false-alarm rate, and Wilson intervals for recall and false-alarm rate. | One place for all the metrics, so every table uses the same definitions. Precision is `None` when nothing is flagged. |
| `_r` | 294 | Rounds to 4 decimals, keeps `None`. | Clean numbers in `metrics.json`. |
| `wilson` | 298 | Wilson score 95% interval for k successes out of n. | Honest uncertainty, also for small n and rates near 0 or 1 (for example 0 of 60 gives 0.0-0.0602). |
| `rate_ci` | 310 | Returns rate, k, n and the Wilson interval for a 0/1 array. | Used for the triage shares and near-duplicate checks. |
| `recall_table` | 316 | Groups a dataframe (for example by scam type or year) and returns n, recall per model and Wilson intervals for the two word models. | Builds the per-type, per-year and per-length tables. |
| `step_load_and_split` | 331 | Loads UCI and splits it 80/20 stratified (seed 42). Loads IMC25, normalises, keeps English, dedupes keeping the earliest dated copy, drops 1 row that also exists in UCI, then splits: year <= 2021 = training pool (1,809), year >= 2022 = test (1,080), no year = undated (12,364). Builds the non-English set (8,866, excluding any text seen in training) and loads the 100 benign twins. | The time split is the core of the experiment. Keeping the earliest copy means a campaign text never sits on both sides. |
| `step_shortcut_check` | 383 | Trains a word model to tell UCI spam (619) from 3,000 IMC25 English scams, with 5-fold CV. Reports ROC AUC (0.9893), balanced accuracy (0.9454), the top tokens for each side, and how often each token appears. | Tests how easy it is to tell the two datasets apart. A high score means part of any gap is dataset style, not only time. |
| `step_train` | 410 | Trains 4 models: word and char on UCI train only ("2012"), and word and char on UCI train + 1,809 early scams ("fixed"). Picks each threshold with `oof_proba` + `pick_threshold`. | The two main models are `word_2012` (Model 2012) and `word_fixed` (fixed model). |
| `step_evaluate` | 428 | Scores every model on: UCI test, 2022-24 test, undated, benign twins and non-English (raw and translated). Adds the baselines (always not-scam, link-or-urgency rule, link-only rule), the link-gated mode and the triage shares. | Produces most of `metrics.json`. The lambdas `g` (line 484) and `tier` (line 501) apply the link gate and `triage` to a whole dataframe. |
| `_max_cos` | 516 | Fits TF-IDF (word 1-2 grams) and returns the cosine similarity of every text in `a` to every text in `b` (diagonal zeroed if `a` and `b` are the same set). | Finds near-duplicates. |
| `step_near_duplicate_check` | 526 | Measures: 2022+ test scams with a training scam at cosine >= 0.9 (0.0139) or >= 0.7 (0.0833); UCI test spam with a near-copy in UCI train (0.2903 at 0.9); Model 2012 recall on UCI spam without a near-copy (0.9205); greedy clusters inside the 2022+ test (985 clusters from 1,080 rows) and cluster-level recall. | Leakage check. It shows the 2012 model's 0.9435 is partly memorised UCI templates, and that the time split has little template overlap. |
| `step_tok_date_ablation` | 568 | Removes every `tok_date`, retrains the two word models, re-picks thresholds and re-measures. | The IMC25 anonymiser tagged dates far more often than our regex, so `tok_date` could be a dataset artifact. Result: small change (Model 2012 recall 0.7565 to 0.7472; fixed-model twin false alarms 0.9833 to 0.9667). |
| `step_demo_examples` | 589 | Picks 3 demo examples by a fixed rule (first match in row order): a linked 2022+ scam Model 2012 misses and the fixed model catches; a 2022+ scam both miss; the first genuine twin both flag. Writes `results/demo_examples.csv`. | Stops cherry-picking: the examples are chosen by code, not by hand. |
| `hypothesis_for_miss` | 616 | Gives a rule-based reason tag for a missed scam (for example "conversational opener with no link or urgency word"). | Fills the `auto_reason` column of `results/fixed_model_missed_scams.csv`. It is a tag, not an analysis. |
| `hypothesis_for_false_alarm` | 628 | Gives a rule-based reason tag for a false alarm (for example "contains a link; the normaliser hides the domain"). | Same, for `results/fixed_model_false_alarms.csv`. |
| `step_tables_and_figures` | 640 | Writes the CSV tables (by scam type, length, year, language, twin category, misses, false alarms, model comparison) and 5 figures (recall by type, recall by year, confusion matrices, PR curve, trade-off chart). | Everything a reader sees in `results/` and `figures/` (except the lead chart). |
| `save_models` | 818 | Saves `word_2012` and `word_fixed` with their thresholds to `models/model_2012.joblib` and `models/model_fixed.joblib`. | The app loads these, so it does not retrain. |
| `_clean` | 826 | Converts NumPy types to plain Python and NaN to `None`, rounds floats to 4 decimals. | Makes `metrics.json` valid JSON. |
| `write_metrics` | 838 | Assembles all results, the seed, the runtime and the library versions into `results/metrics.json`. | One source of truth for every number. |
| `main` | 851 | Runs all steps in order and prints the data summary and runtime (24.8 s in the recorded run). | `python src/scam_drift.py` runs the whole experiment. |

### 2.2 `app.py` (the demo)
Module-level code: lines 20-22 add `src/` to the import path and import `friendly_explain`, `normalise` and `triage`. Lines 24-25 load the two saved models once. Lines 27-37 build the example list: the 2 real scams from `results/demo_examples.csv` first, then 4 written examples. Lines 39-47 hold the warning texts for each colour.

| Function | Line | What it does | Why it exists |
|---|---|---|---|
| `score` | 50 | Runs a saved model on a normalised text. Returns the probability and whether it is at or above the model's threshold. | One call per model. |
| `words` | 55 | Returns the top 5 plain-English words from `friendly_explain`, comma-separated, or "none". | The "words behind it" line in the app. |
| `predict` | 60 | Normalises the text, scores both models, and calls `triage` with "has a link OR a phone number". Returns 3 Markdown blocks: the colour verdict, the table of both models, and the top words. An empty input returns "Paste a text message above." | The whole app logic. Note: the app's RED also fires on a phone number. `metrics.json` measured only the link version, so the phone part is not measured. |
| `build_demo` | 82 | Builds the Gradio page: title, disclaimer, a text box, a "Check this text" button, 3 output areas and the clickable examples. | The user interface. `python app.py` calls `build_demo().launch()` (line 98). |

### 2.3 `tools/real_ham_probe.py` (saved models on real legitimate texts)
| Function | Line | What it does | Why it exists |
|---|---|---|---|
| `_key` | 24 | Lowercases a text, trims it and collapses spaces. | A matching key for removing overlaps. |
| `load_extra_benign` | 28 | Loads two real legitimate SMS sets. India inbox: keeps non-synthetic rows whose sender matches the Indian business-sender header pattern (`DLT_SENDER`, line 21, for example `VM-ICICIB`). Mozambique: keeps `Legitimate` rows from source `sms`. Removes any text that also appears in UCI or IMC25, then removes duplicates. | Builds the real "genuine" test sets: 1,206 India texts from 555 senders and 1,608 Portuguese texts. The sender filter means the India set is business and service messages, not personal chat. |
| `main` | 43 | Scores both saved models at their stored threshold and at 0.5, on each set, with Wilson intervals. Adds the link-only rule. Writes `results/real_ham_probe.json`. | Measures false alarms on real texts. Model 2012 flags 0.8425 of the India inbox; the fixed model flags 0.9942. It never trains on these sets. |

### 2.4 `tools/real_ham_fix_probe.py` (does real legitimate data fix it?)
| Function | Line | What it does | Why it exists |
|---|---|---|---|
| `rate` | 21 | Returns k, n, rate and Wilson interval for a 0/1 array. | Small helper for this script. |
| `main` | 26 | Splits the India inbox by brand (`GroupShuffleSplit`, half the brands each side, seed 42; the 2-letter operator prefix is removed, so `VM-ICICIB` and `JX-ICICIB` are one brand). Trains 3 word models: `word_2012`, `word_naive_fix` (+ early scams) and `word_fix_real_ham` (+ early scams + 606 India legitimate texts from 140 brands). Picks each threshold with out-of-fold predictions. Tests on UCI, 2022-24 scams, India texts from the other 141 brands, Mozambique and the synthetic twins. Writes `results/real_ham_fix_probe.json`. | The key experiment behind the lead chart. Splitting by brand stops the same bank's template being in train and test (0 identical normalised texts across the split). |

### 2.5 `tools/lead_chart.py` (the lead chart)
| Function | Line | What it does | Why it exists |
|---|---|---|---|
| `main` | 29 | Reads `results/real_ham_fix_probe.json` and draws 3 groups of 3 bars: 2022-24 recall, India held-out false alarms, Mozambique false alarms. Labels show 3 decimals. Writes `figures/lead_chart.png`. | The one chart that tells the story. It reads numbers only from the results file, so it cannot drift from them. |

## 3. Formula cheat sheet
Counts: TP = scams flagged, FN = scams missed, FP = genuine texts flagged, TN = genuine texts not flagged.
Worked examples use Model 2012 on the UCI test: TP 117, FP 8, FN 7, TN 895 (`metrics.json`, `uci_test.word_2012.at_threshold`).

| Metric | Formula | Plain meaning | Worked example |
|---|---|---|---|
| Precision | TP / (TP + FP) | Of the texts flagged, the share that are scams | 117 / 125 = 0.936 |
| Recall ("scams caught") | TP / (TP + FN) | Of the scams, the share flagged | 117 / 124 = 0.9435 |
| False-alarm rate | FP / (FP + TN) | Of the genuine texts, the share flagged | 8 / 903 = 0.0089 |
| F1 | 2 x P x R / (P + R) | One number that balances precision and recall (harmonic mean) | 2 x 0.936 x 0.9435 / (0.936 + 0.9435) = 0.9398 |
| Cost (threshold choice) | 5 x FN + 1 x FP | Lower is better; a missed scam weighs 5 false alarms | Model 2012 validation: 5 x 19 + 47 = 142 |

Why precision is "undefined" on the 2022-24 test: every row is a scam, so FP and TN are 0. Precision there would be 1.0 for any model that flags anything, which says nothing. False alarms are measured on separate genuine sets instead.

### Wilson score interval (95%)
With p = k / n and z = 1.96:
- centre = (p + z^2 / (2n)) / (1 + z^2 / n)
- half-width = z x sqrt( p(1 - p) / n + z^2 / (4n^2) ) / (1 + z^2 / n)
- interval = centre +/- half-width, clipped to [0, 1]

Worked example: fixed model, 597 false alarms out of 600 held-out India texts. p = 0.995. Interval = 0.9854 to 0.9983 (`real_ham_fix_probe.json`).
Why Wilson and not "p +/- 1.96 x standard error": the simple formula gives an interval of width 0 for 0 of 60 and can go below 0 or above 1. Wilson gives 0.0-0.0602 for 0 of 60.
Limit: Wilson assumes independent messages. Repeated templates (one bank sending the same text) break this, so our intervals are too narrow on the India set.

### TF-IDF (as configured in `make_word_model`)
- Term frequency, sublinear: tf(t, d) = 1 + ln(count of t in d), if the count is above 0.
- Inverse document frequency (scikit-learn default, smoothed): idf(t) = ln( (1 + N) / (1 + df(t)) ) + 1, where N = number of training texts and df(t) = number of training texts that contain t.
- Weight: tf x idf, then each text's vector is scaled to length 1 (L2 norm).
- Terms: single words and word pairs (1-2 grams) that appear in at least 2 training texts (`min_df=2`).
Plain meaning: a word scores high if it is frequent in this text but rare across all texts. "the" scores low; "verify" scores high.

### Logistic regression
- Probability of scam: p = 1 / (1 + e^-(b + w1 x1 + w2 x2 + ...)), where the x are the TF-IDF values and the w are learned weights.
- Log-odds: ln( p / (1 - p) ) = b + sum of w_j x_j. Each term w_j x_j is one n-gram's push. `explain()` shows the largest positive terms.
- Training: minimise the weighted log loss plus an L2 penalty on the weights. `C = 10` is the inverse penalty strength (weak penalty). `class_weight="balanced"` weights each class by n_samples / (2 x n_class), so the rare class counts as much as the common one.
- A text is flagged when p >= threshold (0.32 for Model 2012, 0.24 for the fixed model), not 0.5.

### ROC AUC
- The ROC curve plots the true-positive rate (recall) against the false-positive rate for every possible threshold.
- AUC = area under that curve = the probability that a randomly chosen positive gets a higher score than a randomly chosen negative.
- 0.5 = coin flip. 1.0 = perfect ranking.
- Our use: the shortcut check. A classifier separates UCI spam from IMC25 scams with AUC 0.9893. So the two datasets are very easy to tell apart, by style and by artifacts.

## 4. 15 hard judge questions, with honest answers

**1. Did you write this code?**
Not all of it by hand. Claude Code, an AI coding assistant, wrote much of it under my direction. I reviewed it, re-ran it, and I can explain any function in it. ChatGPT, Gemini and Claude chat critiqued the idea and the method, and that log is public in `docs/CONSULT_LOG.md`.

**2. Why should we trust results from one person's inbox?**
You should not treat them as a population rate, and I do not. The India set is 1,206 business texts from 555 senders in one inbox, I split it by brand so the 600 test texts come from 141 brands the model never saw, and 0 identical texts cross the split. What I trust is the direction, because three different sources agree: the retrained model flags 0.995 of the India held-out texts, 0.625 of the Portuguese Mozambique texts, and 0.9833 of my synthetic texts. I also looked at both sets while exploring, so they are not untouched holdouts.

**3. Is this drift or dataset shift?**
Mostly dataset shift, and I say so. The 2012 model catches 0.9435 of held-out 2012 spam (0.9205 without near-copies) but 0.7565 of 2022-24 scams; inside the IMC25 reports there is no clear decline (2017: 0.8175, 2023: 0.7751, intervals overlap). A shortcut classifier tells the two datasets apart with ROC AUC 0.9893, so part of the gap is source style. A true drift test needs one source collected the same way over many years.

**4. Why logistic regression?**
It is the brief's baseline, it trains in seconds on a CPU, and its weights give an exact word-by-word explanation, which the app shows to the user. My main finding is about training data, not model power, so a simple, transparent model makes the cause easy to see. I also ran a character n-gram version, and it shows the same pattern: 0.9602 recall but 0.95 false alarms on the synthetic genuine texts. Hyperparameters were fixed in advance, not searched.

**5. What would you do with 3 more months?**
First, collect consented, anonymised modern legitimate texts from many people and countries, and split by brand and by template cluster. Second, finish the checks I did not do: whole-campaign cluster splits across the time cut, a learning curve on how much data helps, and the RED tier's false-alarm rate on real texts. Third, model changes: keep the link's domain, use multi-message context for "Hi Mum" openers, fold look-alike letters, and train on many languages. Fourth, test the warning wording with older users.

**6. Your retrained model catches 0.9657 of modern scams. Why not ship that?**
Because it flags 597 of 600 real legitimate texts from unseen brands (0.995) and 59 of 60 synthetic ones. A filter that warns on almost everything teaches the user to ignore warnings, so it is less safe, not more. The recall number only looks good because the 2022-24 test contains only scams.

**7. The app uses Model 2012, which flags 0.8425 of the real inbox. Isn't the app useless?**
As a product, yes, today. I chose Model 2012 for the colours because its RED tier fired on 0 of 60 synthetic genuine texts, while the fixed model flags 59 of 60. But I have not measured the RED tier on the real inbox; that number is UNKNOWN. The app is a demonstration of the problem and of a warn-only design ("check first", never "safe"), not a deployable filter.

**8. How did you choose the threshold? Isn't 5 to 1 arbitrary?**
The 5:1 ratio is a judgement, and I say so: a missed scam can cost savings, but frequent false alarms teach people to ignore warnings, so I did not choose a much larger ratio. The threshold minimises 5 x missed + 1 x false alarms on 5-fold out-of-fold predictions on training data only, so the test sets never influence it. I did not run a sensitivity analysis on the ratio, but the false-alarm finding also holds at a plain 0.5 cut: the fixed model flags 0.9859 of the real India inbox at 0.5.

**9. How do you know there is no leakage between train and test?**
Three checks. Exact duplicates are removed after normalisation, keeping the earliest dated copy, so a campaign text cannot sit on both sides. Only 0.0139 of the 2022-24 test scams have a training scam at cosine >= 0.9, and cluster-level recall (0.7521) is close to row-level (0.7565). The limit: I did not force whole template clusters to one side of the time split, and the UCI split does repeat spam templates (0.2903 of UCI test spam has a near-copy), which is why I also report 0.9205.

**10. A classifier tells your datasets apart with ROC AUC 0.9893. Doesn't that invalidate everything?**
It does not invalidate it; it explains it. Most top tokens are real style change ("txt", "ringtone" in 2012 against "dear customer", "account" now), and some are artifacts: the IMC25 anonymiser tagged dates far more often. I removed `tok_date` and retrained: Model 2012 recall moved from 0.7565 to 0.7472 and fixed-model false alarms on the twins from 0.9833 to 0.9667. The fixed model's false alarms come from exactly this kind of source shortcut: it learned "formal style = scam".

**11. Your 60 genuine-style texts are synthetic and written with AI. Why believe them?**
I treat them as a stress test, not a real-world rate. They were written and frozen before the first model run and never used for training or threshold choice, and their intervals are wide (59 of 60 is 0.9114-0.9971). Because they are synthetic, I added two real sets, and the real India texts showed the problem is worse, not better: 0.995 against 0.9833.

**12. Why not use a large language model or BERT?**
I did not test one, so how it would perform is UNKNOWN. My finding is about the training data: a supervised model whose only genuine examples are 2012 chat learns "formal = scam", and I expect any supervised model to need modern legitimate texts, but that is an expectation, not a result. A small linear model also runs on the phone, so the grandparent's texts do not leave the device.

**13. The RED / YELLOW / GREEN colours were designed after you saw the results. Isn't that cherry-picking?**
Yes, it is post-hoc, and the code, `metrics.json` and the README all say so. I report the tiers as a design choice, not as a validated model: RED fired on 0.3824 of 2022-24 scams and on 0 of 60 synthetic genuine texts, but those numbers are optimistic because I chose the design after seeing them. The app also adds phone numbers to the RED rule, and that part is not measured at all.

**14. Why does it miss "Hi Mum, new number" scams?**
They look like 2012 personal chat, which is exactly what the model learned as genuine: no link, no money, no formal words. Model 2012 caught 0 of 4 in the 2022-24 test and 0.098 in the undated set (n=51); for "wrong number" openers it caught 0.0833 (n=24). The scam starts later in the conversation, so one message is not enough; a fix needs multi-message context or a rule for "new number" plus a request, which I did not build.

**15. What precision would a real user see?**
I did not measure it. Precision depends on how many of a person's texts are scams, and I have no real inbox with both scams and genuine texts labelled; the prevalence-adjusted estimate was planned and not done. What I can say is directional: when the large majority of texts are genuine, a false-alarm rate of 0.91 (Model 2012) or 0.995 (fixed model) on real legitimate texts means most warnings would be false.

### Backup one-liners
- "What is the main number?" 0.7565 of 2022-24 scams caught by the 2012 filter; retraining raises it to 0.9657 but flags 0.995 of real legitimate texts from held-out brands.
- "How big is the test?" 1,080 English scams from 2022-24, plus 12,364 undated and 8,866 non-English scams, none trained on.
- "Non-English?" Model 2012 catches 0.508 of 8,866 non-English scams from the raw text and 0.6959 from the dataset's English translation (an oracle reference).
- "Short messages?" Model 2012 catches 0.4934 of 2022-24 scams under 80 characters (n=152).
- "Runtime?" The full pipeline ran in 24.8 seconds on a CPU (seed 42).
