# Scam Drift: detailed results

Every number below is copied from `results/metrics.json` or the CSV tables in `results/` from the seeded run of `src/scam_drift.py` (seed 42). The executed notebook produces identical metrics (all keys except `runtime_seconds`). "95% CI" means a Wilson score interval. Groups with n < 30 are indicative only.

## 1. Data and splits

| Item | Value |
|---|---|
| UCI messages (raw / after dedupe) | 5,574 / 5,135 |
| UCI train / test (spam) | 4,108 (495) / 1,027 (124) |
| IMC25 rows / rows with an explicit year in `time` | 33,869 / 5,295 |
| IMC25 English rows / unique after normalisation | 22,073 / 15,254 |
| English rows dropped because the same normalised text is in UCI | 1 |
| Modern train pool: English scams dated 2015-2021 | 1,809 |
| Modern test: English scams dated 2022-2024 | 1,080 |
| Undated English scams (never trained on) | 12,364 |
| Non-English scams evaluated (not in any training set) | 8,866 |

**Time split decision.** The IMC25 `time` field is the raw timestamp from the reporter's screenshot ("Today 8:15 AM", "Tuesday 7 March 12:52"). We date a row only if the string shows a four-digit year (2015-2025) or a d/m/yy date. English dated rows per year (after dedupe; `results/recall_by_year.csv`): 2015: 1, 2016: 3, 2017: 126, 2018: 175, 2019: 284, 2020: 521, 2021: 699 (train pool total 1,809), 2022: 694, 2023: 378, 2024: 8 (test total 1,080). A cut at the end of 2021 gives both sides more than 1,000 rows. A cut at the end of 2022 would leave fewer than 400 test rows.

**The dated subset is not a random sample.** Only about 16% of IMC25 rows (5,295 of 33,869) show a year, and which timestamp formats show a year depends on the reporter's phone and locale. The year parser also misses some rows: strings with a 2010-2014 year and forms such as "Mon 15th May '23" are treated as undated. These rows go to the undated evaluation set, never to training, so this causes no leakage.

**Dedupe.** Exact duplicates after normalisation are removed, keeping the earliest dated copy, so a campaign text never appears on both sides of the split.

**Near-duplicate checks** (TF-IDF word 1-2 gram cosine; `near_duplicate_check` in metrics.json):

| Check | Value |
|---|---|
| 2022+ test scams with a 2015-2021 training scam at cosine >= 0.9 / >= 0.7 | 0.0139 / 0.0833 |
| UCI test messages with a UCI train message at cosine >= 0.9 | 0.036 |
| UCI test spam with a UCI train spam at cosine >= 0.9 / >= 0.7 | 0.2903 / 0.4435 |
| Model 2012 recall on UCI test spam with no near-copy (cosine < 0.9) | 0.9205 (81/88, 95% CI 0.8448-0.9609) |
| Model 2012 recall on UCI test spam with no near-copy (cosine < 0.7) | 0.8986 (62/69, 95% CI 0.8051-0.95) |
| Model 2012 recall on UCI test spam that has a near-copy (cosine >= 0.9) | 1.0 (36/36) |
| 2022+ test scams with another 2022+ test scam at cosine >= 0.9 | 0.1611 |
| Greedy clusters at cosine >= 0.9 inside the 2022+ test | 985 clusters from 1,080 rows |
| Cluster-level recall (mean of per-cluster recall): rule / Model 2012 / fixed | 0.6049 / 0.7521 / 0.9645 |

Reading: UCI spam repeats premium-rate templates across the plain stratified split, so the UCI test recall of 0.9435 is partly memorised templates. On UCI test spam with no near-copy, Model 2012 catches 0.9205 (cosine < 0.9) or 0.8986 (cosine < 0.7). The drift gap to 2022+ scams (0.7565) is therefore smaller than 0.9435 - 0.7565, but it remains. Near-duplicate variants inside the 2022+ test change the recall numbers only slightly at the cluster level.

## 2. Shortcut check
A word TF-IDF + logistic regression classifier separates UCI spam (n=619) from a 3,000-row sample of IMC25 English scams after normalisation with 5-fold CV ROC AUC **0.9893** (balanced accuracy 0.9454).

- Tokens that say "IMC25": `tok_date`, `please`, `tok_url`, `account`, `card`, `your`, `at`, `dear`, `bank`, `payment`, `of tok_money`, `dear customer`, `here`, `has`, `thank`, `pay`, `click`, `details`, `for tok_date`, `thank you`.
- Tokens that say "UCI 2012": `to tok_num`, `txt`, `tok_phone`, `text`, `call tok_phone`, `u`, `tok_num`, `call`, `tok_money`, `free`, `ringtone`, `content`, `reply`, `ur`, `on tok_phone`, `next`, `or`, `msg`, `wap`, `choose`.

Token presence rates (share of messages containing the token):

| Token | UCI spam | UCI ham | IMC25 English |
|---|---|---|---|
| tok_url | 0.189 | 0.004 | 0.4223 |
| tok_phone | 0.5444 | 0.0009 | 0.146 |
| tok_email | 0.0097 | 0.0004 | 0.026 |
| tok_money | 0.5315 | 0.0031 | 0.159 |
| tok_date | 0.1276 | 0.0833 | 0.4327 |
| tok_num | 0.8304 | 0.1887 | 0.359 |

Reading: most top tokens are genuine change in scam style (2012 premium-rate "txt ... to 87121" vs. 2020s "dear customer, your account ... click"). `tok_date` is partly an artifact: the IMC25 anonymiser (Presidio) tagged durations such as "within 24 hours", and even some phone numbers, as `<DATE_TIME>`, while UCI text goes only through our regex. So part of any UCI-vs-IMC25 gap is dataset style.

**Ablation: `tok_date` removed** from every text, models retrained, thresholds re-chosen the same way (`tok_date_ablation`):

| Model | Threshold | UCI test R / F1 | 2022+ recall | Benign-twin false alarms |
|---|---|---|---|---|
| word_2012, with tok_date | 0.32 | 0.9435 / 0.9398 | 0.7565 | 0.5167 |
| word_2012, without tok_date | 0.34 | 0.9435 / 0.9435 | 0.7472 | 0.4833 |
| word_fixed, with tok_date | 0.24 | 0.9597 / 0.844 | 0.9657 | 0.9833 |
| word_fixed, without tok_date | 0.21 | 0.9677 / 0.8136 | 0.9694 | 0.9667 |

Removing `tok_date` changes the main results only a little. It is not the cause of the fixed model's false alarms.

## 3. All models

UCI test (n=1,027, 124 spam). P = precision, R = recall, FA = false-alarm rate on ham.

| Model | Threshold | P | R | F1 | FA | At 0.5: P / R / F1 / FA |
|---|---|---|---|---|---|---|
| Always not-scam | - | undefined | 0.0 | 0.0 | 0.0 | accuracy 0.8793 |
| Rule (link or urgency word) | - | 0.8364 | 0.371 | 0.514 | 0.01 | - |
| Rule (link only) | - | 0.8636 | 0.1532 | 0.2603 | 0.0033 | - |
| word_2012 | 0.32 | 0.936 | 0.9435 | 0.9398 | 0.0089 | 0.9664 / 0.9274 / 0.9465 / 0.0044 |
| char_2012 | 0.34 | 0.9512 | 0.9435 | 0.9474 | 0.0066 | 0.9746 / 0.9274 / 0.9504 / 0.0033 |
| word_fixed | 0.24 | 0.7532 | 0.9597 | 0.844 | 0.0432 | 0.8992 / 0.9355 / 0.917 / 0.0144 |
| char_fixed | 0.3 | 0.8676 | 0.9516 | 0.9077 | 0.0199 | 0.9286 / 0.9435 / 0.936 / 0.01 |

Modern scams (recall only; every row is a scam). Benign twins: 60 genuine-style and 40 scam texts, synthetic.

| Model | 2022+ test (n=1,080) at threshold (95% CI) / at 0.5 | Undated (n=12,364) | Twins FA at threshold (95% CI) / at 0.5 | Twins scam recall |
|---|---|---|---|---|
| Rule (link or urgency) | 0.6185 (0.5892-0.647) | 0.6637 | 0.1 (0.0466-0.2015) | 0.85 |
| Rule (link only) | 0.4065 (0.3776-0.4361) | 0.4357 | 0.05 (0.0171-0.137) | 0.725 |
| word_2012 | 0.7565 (0.73-0.7811) / 0.6278 | 0.7856 | 0.5167 (0.3931-0.6383) / 0.3667 | 0.95 |
| char_2012 | 0.6944 (0.6663-0.7212) / 0.5815 | 0.7375 | 0.5167 / 0.3 | 0.85 |
| word_fixed | 0.9657 (0.9531-0.975) / 0.9407 | 0.9693 | 0.9833 (0.9114-0.9971) / 0.8833 | 0.975 |
| char_fixed | 0.9602 (0.9468-0.9703) / 0.9426 | 0.9655 | 0.95 (0.863-0.9829) / 0.9 | 0.975 |

Undated rows were never trained on, but they may share campaigns with the 2015-2021 training scams, so the fixed model's undated number is less clean than its 2022+ number.

**Threshold choice.** Each threshold minimises 5 x missed scams + 1 x false alarms on 5-fold out-of-fold predictions of the model's own training data. Why 5x: a missed scam can lead to an irreversible loss of savings; a false alarm costs a short check with the bank or family, but frequent false alarms teach the user to ignore warnings, so we did not choose a much larger ratio. Caveat: the fixed model's validation data is 2,304 scams out of 5,917 messages, far more scams than a real inbox, which pushes its threshold down (0.24).

**Link gate (post-hoc, exploratory).** Warn only if the model flags the message AND it contains a link. This was added after the first results were seen, so it is not a pre-registered model.

| Mode | UCI test P / R / F1 | 2022+ recall (95% CI) | Twins FA (95% CI) | Twins scam recall | Agreement with "link only" rule: 2022+ / twins |
|---|---|---|---|---|---|
| Model 2012 + link gate | 0.95 / 0.1532 / 0.2639 | 0.3824 (0.3539-0.4118) | 0.0 (0.0-0.0602) | 0.7 | 0.9759 / 0.96 |
| Fixed model + link gate | 0.9048 / 0.1532 / 0.2621 | 0.4065 (0.3776-0.4361) | 0.05 (0.0171-0.137) | 0.725 | 1.0 / 1.0 |

Only 0.4065 of 2022+ test scams contain a link after normalisation, so the gate caps recall there. The fixed model + link gate flags every linked 2022+ scam (1.0) and every linked benign twin, so on these sets it is exactly the link-only rule. Model 2012 + link gate catches 0.9408 of linked 2022+ scams and none of the linked genuine twins.

**Three-tier warning (post-hoc, used by the demo).** RED = Model 2012 flags AND link; YELLOW = Model 2012 flags, no link; GREEN = no flag (`triage` in metrics.json).

| Set | RED | YELLOW | RED or YELLOW |
|---|---|---|---|
| 2022+ test scams (n=1,080) | 0.3824 | 0.3741 | 0.7565 |
| Undated scams (n=12,364) | 0.4154 | 0.3702 | 0.7856 |
| Genuine benign twins (n=60) | 0.0 (0.0-0.0602) | 0.5167 (0.3931-0.6383) | 0.5167 |
| Scam benign twins (n=40) | 0.7 | 0.25 | 0.95 |
| UCI test ham (n=903) | 0.0011 | 0.0078 | 0.0089 |

So RED never fired on a genuine-style twin, but about half of them get YELLOW ("ask a family member").

## 4. Per scam type (2022+ test, at each model's threshold)

| scam_type | n | Rule | word_2012 (95% CI) | char_2012 | word_fixed (95% CI) | char_fixed |
|---|---|---|---|---|---|---|
| banking | 468 | 0.7564 | 0.8483 (0.813-0.8779) | 0.7073 | 1.0 (0.9919-1.0) | 1.0 |
| others | 246 | 0.3902 | 0.6341 (0.5723-0.6918) | 0.6585 | 0.9309 (0.8921-0.9564) | 0.9187 |
| government | 99 | 0.7273 | 0.8081 (0.7196-0.8736) | 0.798 | 1.0 (0.9626-1.0) | 1.0 |
| spam | 96 | 0.5625 | 0.7396 (0.6438-0.8169) | 0.7292 | 0.9375 (0.8703-0.971) | 0.9062 |
| delivery | 87 | 0.6552 | 0.6897 (0.5862-0.7771) | 0.6322 | 0.9885 (0.9377-0.998) | 0.9885 |
| telecom | 56 | 0.625 | 0.9107 (0.8074-0.9613) | 0.875 | 1.0 (0.9358-1.0) | 1.0 |
| wrong number | 24 | 0.0 | 0.0833 (0.0232-0.2585) | 0.0417 | 0.5833 (0.3883-0.7553) | 0.4583 |
| hey mum/dad | 4 | 0.0 | 0.0 (0.0-0.4899) | 0.75 | 0.25 (0.0456-0.6994) | 1.0 |

The larger undated set confirms the pattern for Model 2012: wrong number 0.0552 (n=145), hey mum/dad 0.098 (n=51), others 0.6653 (n=2,952), banking 0.8492 (n=5,061) (`results/recall_by_scam_type_undated.csv`).

## 5. Per year (drift)
Model 2012 recall on dated English scams (none were trained on): 2017: 0.8175 (n=126), 2018: 0.8 (n=175), 2019: 0.8345 (n=284), 2020: 0.8042 (n=521), 2021: 0.7454 (n=699), 2022: 0.745 (n=694), 2023: 0.7751 (n=378). 2015 (n=1), 2016 (n=3) and 2024 (n=8) are too small to read and are not plotted. The drop from 2012-era spam (UCI test recall 0.9435; 0.9205 on test spam with no near-copy) to the 2017-2023 range is large; the change inside 2017-2023 is small, and the 95% intervals for 2017 (0.741-0.8752) and 2023 (0.7304-0.8143) overlap. So we see a step between datasets, not a steady decline over time. Fixed model on test years: 2022: 0.9712, 2023: 0.955.

## 6. Fairness-style check: message length and language
We have no age, gender or other personal data, so we cannot check fairness across those groups. We check message length (short texts give the model less evidence) and language.

| Length (chars) | 2022+ scams n | Rule | word_2012 | word_fixed | UCI test ham n | FA word_2012 | FA word_fixed |
|---|---|---|---|---|---|---|---|
| < 80 | 152 | 0.3158 | 0.4934 | 0.8882 | 628 | 0.0096 | 0.0446 |
| 80-159 | 644 | 0.6972 | 0.7873 | 0.986 | 231 | 0.0043 | 0.0346 |
| 160-319 | 234 | 0.6068 | 0.8248 | 0.9615 | 36 | 0.0278 | 0.0833 |
| 320+ | 50 | 0.58 | 0.84 | 0.96 | 8 | 0.0 | 0.0 |

Short scams are the hardest for Model 2012 (0.4934).

## 7. Non-English scams (bonus finding)
Model 2012 on 8,866 non-English scams: 0.508 from raw text, 0.6959 from the dataset's English translation. Fixed model: 0.7672 raw, 0.9768 translated. Per language (Model 2012 raw / translated): Spanish 0.481 / 0.6863 (n=3,191), Dutch 0.4919 / 0.7937 (n=1,551), French 0.4667 / 0.7207 (n=870), German 0.5339 / 0.6271 (n=590), Japanese 0.3353 / 0.4566 (n=173). Translating first helps, but the translations were made by the dataset authors, not by a phone (an "oracle" reference).

## 8. Benign twins per category (share flagged)

| Label | Category | n | Rule | word_2012 | word_fixed |
|---|---|---|---|---|---|
| genuine | bank_alert | 10 | 0.0 | 1.0 | 1.0 |
| genuine | bank_otp | 10 | 0.2 | 0.6 | 1.0 |
| genuine | delivery | 10 | 0.1 | 0.4 | 1.0 |
| genuine | medical | 10 | 0.2 | 0.4 | 1.0 |
| genuine | pharmacy | 10 | 0.0 | 0.3 | 1.0 |
| genuine | utility_other | 10 | 0.1 | 0.4 | 0.9 |
| scam | all 6 categories | 40 | see `results/benign_twins_by_category.csv` | | |

The benign twins were written before the first model run and were never used for training or threshold choice. They are synthetic, so they show a risk, not a measured real-world rate.

## 9. Failure analysis (fixed word model)

**Missed 2022+ scams** (37 of 1,080: others 17, wrong number 10, spam 6, hey mum/dad 3, delivery 1; full list in `results/fixed_model_missed_scams.csv`, whose `auto_reason` column is a rule-based tag, not an analysis). Hand-written hypotheses:

| scam_type | p(scam) | Text (shortened) | Hypothesis |
|---|---|---|---|
| spam | 0.0022 | "Ηello аll, guуsǃ I knоw, my mesѕаge maу bе toо sрeсifіc..." | Homoglyphs: Cyrillic letters that look Latin turn every word into an unknown token. |
| wrong number | 0.0222 | "How are you doing" | Opener only; the scam starts later in the chat, so this one text has no scam words. |
| hey mum/dad | 0.0718 | "Hello-Mum I accidentally dropped my mobile-phone down the toilet..." | Family-impostor wording looks like 2012 personal ham; no link or money. |
| others | 0.0274 | "i'm really sorry if i'm wasting ur time ... small help..." (xbox game pass code) | Gift-code begging is a new lure with no training examples. Two variants differ only by an emoji. |
| delivery | 0.1885 | "We are only one drop away. We should be with you by 16:03..." | Reads exactly like a genuine courier update; the scam part (link) was cut from the report. |
| others | 0.0337 | "Fuck off" | Probably not a scam at all: label noise in user-submitted reports. |
| others | 0.1962 | "Hello ... I recently changed my bank information and I would love to change my DD details..." | Payroll-diversion scam written in polite personal style. |

**False alarms** (39 UCI test ham and 59 benign twins; full list in `results/fixed_model_false_alarms.csv`):

| Source | p(scam) | Text (shortened) | Hypothesis |
|---|---|---|---|
| UCI ham | 1.0 | "staff.science.nus.edu.sg/~phyhcmk/teaching/pc1323" | A bare link; the normaliser hides the domain, so every link looks alike. |
| UCI ham | 0.9848 | "NEFT Transaction with reference number ... has been credited..." | A genuine bank notification; all formal bank wording in training was scam. |
| UCI ham | 0.6326 | "what is your account number?" | "your account" is a strong scam phrase in 2020s banking smishing. |
| twins | 0.9993 | "Reminder: your credit card payment of $85.00 is due on Nov 25..." | Money + card + payment words = banking-scam vocabulary. |
| twins | 0.9907 | "First Harbor Bank Fraud Alert: Did you use your card ending 4821..." | Genuine fraud alerts use the same words as fake fraud alerts. |
| twins | 0.989 | "Dental reminder: your cleaning is on Friday at 11 AM. Call 555-0142..." | "call tok_phone" was a top 2012 spam pattern (premium-rate numbers). |
| twins | 0.9839 | "Out for delivery: your order #48211 will arrive today by 8pm." | Delivery wording is now dominated by delivery scams in the training data. |

**Root cause of the false alarms.** In training, every formal notification was a scam (IMC25) and every genuine message was 2012 personal chat (UCI ham). The fixed model therefore learned "formal notification style = scam". The fix needs real modern genuine notifications as negatives.

## 10. Demo examples
`results/demo_examples.csv` holds three examples chosen by a fixed rule in `step_demo_examples` (first matching row by order), not by hand: a 2022+ scam that Model 2012 misses and the fixed model catches, a 2022+ scam that both miss, and the first genuine twin that both flag. The README table copies them.

## 10b. Exploratory: real modern genuine texts (not in the main pipeline)
Post-hoc probe, run by separate scripts (`tools/real_ham_probe.py`, `tools/real_ham_fix_probe.py`) on two public sets described in `docs/EXTRA_DATA.md`. The raw texts contain first names, so they are not published (`data/raw/extra/` is gitignored); the scripts download them from pinned URLs. Numbers below are copied from `results/real_ham_fix_probe.json` (thresholds from 5-fold out-of-fold predictions on each model's own training data; 95% Wilson intervals). The India set is ONE person's inbox, so these are not population rates, and template repeats make the intervals too narrow.

| Model | 2022+ scams caught (n=1,080) | False alarms, real India inbox, held-out brands (n=600) | False alarms, real Mozambique SMS, Portuguese (n=1,608) | False alarms, synthetic genuine twins (n=60) |
|---|---|---|---|---|
| Model 2012 | 0.7565 | 0.91 (0.8844-0.9304) | 0.3937 | 0.5167 |
| Fixed model (naive fix) | 0.9657 | 0.995 (0.9854-0.9983) | 0.625 | 0.9833 |
| Fix + real India ham from 140 other brands (606 rows) | 0.9593 | 0.7117 (0.6742-0.7465) | 0.6175 | 0.8833 |

Reading: on real modern genuine SMS the false-alarm problem is worse than the synthetic twins suggest. Adding real genuine texts from other brands helps (0.995 to 0.7117 on held-out brands) but is far from enough. So modern genuine texts are necessary, but one inbox does not fix the filter.

## 11. Limitations
- The main pipeline has no real modern genuine texts; benign twins are synthetic and small (100 messages). The exploratory probe in section 10b uses one real inbox only.
- Only about 16% of IMC25 rows can be dated (5,295 of 33,869), and the dated subset depends on phone locale.
- IMC25 contains user reports; some "scams" are not scams (label noise), and some reports lost their link.
- Named-entity tags were deleted, so brand names that the IMC25 anonymiser removed are missing, while UCI keeps its names.
- The IMC25 anonymiser tags dates and durations more aggressively than our regex (see the `tok_date` ablation).
- UCI ham is mostly Singapore student chat, not grandparent texts. UCI spam repeats templates across the train/test split.
- Hyperparameters (C=10, class_weight balanced, min_df) were fixed in advance, not searched.
- The link gate and the three tiers were designed after the first results (post-hoc).
- The notebook has run locally; Colab compatibility is UNKNOWN (not tested).
