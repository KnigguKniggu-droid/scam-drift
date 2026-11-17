# Scam Drift: detailed results

Every number below is copied from `results/metrics.json` or the CSV tables in `results/` from the seeded run of `src/scam_drift.py` (seed 42). The executed notebook produced identical metrics (all keys except `runtime_seconds`).

## 1. Data and splits

| Item | Value |
|---|---|
| UCI messages (raw / after dedupe) | 5,574 / 5,135 |
| UCI train / test (spam) | 4,108 (495) / 1,027 (124) |
| IMC25 rows / rows with an explicit year in `time` | 33,869 / 5,295 |
| IMC25 English rows / unique after normalisation | 22,073 / 15,255 |
| English rows dropped because the same normalised text is in UCI | 1 |
| Modern train pool: English scams dated 2015-2021 | 1,809 |
| Modern test: English scams dated 2022-2024 | 1,080 |
| Undated English scams (never trained on) | 12,365 |
| Non-English scams evaluated (not in any training set) | 8,870 |

**Time split decision.** The IMC25 `time` field is the raw timestamp from the reporter's screenshot ("Today 8:15 AM", "Tuesday 7 March 12:52"). We date a row only if the string shows a four-digit year (2015-2025) or a d/m/yy date. English dated rows per year: 2017: 126, 2018: 175, 2019: 284, 2020: 521, 2021: 699, 2022: 694, 2023: 378, 2024: 8 (after dedupe; see `results/recall_by_year.csv`). A cut at the end of 2021 gives both sides more than 1,000 rows. A cut at the end of 2022 would leave fewer than 400 test rows.

**Dedupe.** Exact duplicates after normalisation are removed, keeping the earliest dated copy, so a campaign text never appears on both sides of the split. **Near-duplicate check:** 0.0139 of 2022+ test scams have a training scam with TF-IDF cosine >= 0.9, and 0.0833 have one with cosine >= 0.7. Near-duplicate leakage is small.

## 2. Shortcut check
A word TF-IDF + logistic regression classifier separates UCI spam (n=619) from a 3,000-row sample of IMC25 English scams after normalisation with 5-fold CV ROC AUC **0.9895** (balanced accuracy 0.9445).

- Tokens that say "IMC25": `tok_date`, `at`, `tok_url`, `please`, `your`, `account`, `card`, `dear`, `payment`, `bank`, `of tok_money`, `here`, `has`, `click`, `in`, `dear customer`, `details`, `thank`, `thank you`, `for tok_date`.
- Tokens that say "UCI 2012": `to tok_num`, `txt`, `tok_phone`, `call tok_phone`, `u`, `text`, `call`, `free`, `tok_num`, `tok_money`, `ringtone`, `content`, `reply`, `ur`, `or`, `next`, `on tok_phone`, `wap`, `a tok_money`, `msg`.

Token presence rates (share of messages containing the token):

| Token | UCI spam | UCI ham | IMC25 English |
|---|---|---|---|
| tok_url | 0.189 | 0.004 | 0.4247 |
| tok_phone | 0.5477 | 0.0009 | 0.1463 |
| tok_money | 0.5315 | 0.0031 | 0.1477 |
| tok_date | 0.1276 | 0.0833 | 0.407 |
| tok_num | 0.8304 | 0.1887 | 0.3603 |

Reading: most top tokens are genuine change in scam style (2012 premium-rate "txt ... to 87121" vs. 2020s "dear customer, your account ... click"). `tok_date` is partly an artifact: the IMC25 anonymiser tagged words such as durations as `<DATE_TIME>` more often than our regex does. So part of any UCI-vs-IMC25 gap is dataset style.

## 3. All models

UCI test (n=1,027, 124 spam). P = precision, R = recall, FA = false-alarm rate on ham.

| Model | Threshold | P | R | F1 | FA | At 0.5: P / R / F1 / FA |
|---|---|---|---|---|---|---|
| Always not-scam | - | undefined | 0.0 | 0.0 | 0.0 | accuracy 0.8793 |
| Rule (link or urgency word) | - | 0.8364 | 0.371 | 0.514 | 0.01 | - |
| word_2012 | 0.32 | 0.936 | 0.9435 | 0.9398 | 0.0089 | 0.9664 / 0.9274 / 0.9465 / 0.0044 |
| char_2012 | 0.34 | 0.9512 | 0.9435 | 0.9474 | 0.0066 | 0.9746 / 0.9274 / 0.9504 / 0.0033 |
| word_fixed | 0.2 | 0.7101 | 0.9677 | 0.8191 | 0.0543 | 0.8992 / 0.9355 / 0.917 / 0.0144 |
| char_fixed | 0.3 | 0.8676 | 0.9516 | 0.9077 | 0.0199 | 0.9286 / 0.9435 / 0.936 / 0.01 |

Modern scams (recall only; every row is a scam):

| Model | 2022+ test (n=1,080) at threshold / at 0.5 | Undated (n=12,365) at threshold | Benign twins FA (60 genuine) at threshold / at 0.5 | Benign twins scam recall (40) |
|---|---|---|---|---|
| Rule | 0.6185 | 0.6636 | 0.1 | 0.85 |
| word_2012 | 0.7574 / 0.6269 | 0.7854 | 0.5167 / 0.35 | 0.95 |
| char_2012 | 0.6944 / 0.5824 | 0.7369 | 0.5167 / 0.3 | 0.85 |
| word_fixed | 0.9704 / 0.9407 | 0.9723 | 0.9833 / 0.8833 | 0.975 |
| char_fixed | 0.9602 / 0.9426 | 0.9654 | 0.95 / 0.9 | 0.975 |

Undated rows were never trained on, but they may share campaigns with the 2015-2021 training scams, so the fixed model's undated number is less clean than its 2022+ number.

**Threshold choice.** Each threshold minimises 5 x missed scams + 1 x false alarms on 5-fold out-of-fold predictions of the model's own training data. Why 5x: a missed scam can lead to an irreversible loss of savings; a false alarm costs a short check with the bank or family, but frequent false alarms teach the user to ignore warnings, so we did not choose a much larger ratio. Caveat: the fixed model's validation data is 2,304 scams out of 5,917 messages, far more scams than a real inbox, which pushes its threshold down (0.2).

**Link gate** (warn only if the model flags the message AND it contains a link; chosen from the user's decision, not tuned on test): Model 2012 + gate catches 0.3824 of 2022+ scams with 0.0 benign-twin false alarms; fixed model + gate catches 0.4065 with 0.05. Only 0.4065 of 2022+ test scams contain a link after normalisation, so the gate caps recall there. Among test scams that do contain a link, the gated fixed model catches 1.0 and the gated Model 2012 catches 0.9408.

## 4. Per scam type (2022+ test, at each model's threshold)

| scam_type | n | Rule | word_2012 | char_2012 | word_fixed | char_fixed |
|---|---|---|---|---|---|---|
| banking | 468 | 0.7564 | 0.8504 | 0.7073 | 1.0 | 1.0 |
| others | 246 | 0.3902 | 0.6341 | 0.6585 | 0.9309 | 0.9187 |
| government | 99 | 0.7273 | 0.8081 | 0.798 | 1.0 | 1.0 |
| spam | 96 | 0.5625 | 0.7396 | 0.7292 | 0.9583 | 0.9062 |
| delivery | 87 | 0.6552 | 0.6897 | 0.6322 | 0.9885 | 0.9885 |
| telecom | 56 | 0.625 | 0.9107 | 0.875 | 1.0 | 1.0 |
| wrong number | 24 | 0.0 | 0.0833 | 0.0417 | 0.6667 | 0.4583 |
| hey mum/dad | 4 | 0.0 | 0.0 | 0.75 | 0.5 | 1.0 |

The larger undated set confirms the pattern for Model 2012: wrong number 0.0552 (n=145), hey mum/dad 0.098 (n=51), others 0.6647 (n=2,953), banking 0.8504 (n=5,061) (`results/recall_by_scam_type_undated.csv`).

## 5. Per year (drift)
Model 2012 recall on dated English scams (none were trained on): 2017: 0.8175, 2018: 0.8, 2019: 0.8345, 2020: 0.8042, 2021: 0.7454, 2022: 0.7464, 2023: 0.7751. The drop from 2012-era spam (UCI test recall 0.9435) to the 2017-2023 range is large; the change inside 2017-2023 is small. Fixed model on test years: 2022: 0.9769, 2023: 0.9577. (2024 has only 8 rows.)

## 6. Fairness-style check: message length
We have no age, gender or other personal data, so we cannot check fairness across people. We check message length instead (short texts give the model less evidence).

| Length (chars) | 2022+ scams n | Rule | word_2012 | word_fixed | UCI test ham n | FA word_2012 | FA word_fixed |
|---|---|---|---|---|---|---|---|
| < 80 | 152 | 0.3158 | 0.4934 | 0.9013 | 628 | 0.0096 | 0.0557 |
| 80-159 | 644 | 0.6972 | 0.7888 | 0.9876 | 231 | 0.0043 | 0.0476 |
| 160-319 | 234 | 0.6068 | 0.8248 | 0.9658 | 36 | 0.0278 | 0.0833 |
| 320+ | 50 | 0.58 | 0.84 | 0.98 | 8 | 0.0 | 0.0 |

Short scams are the hardest for Model 2012 (0.4934).

## 7. Non-English scams (bonus finding)
Model 2012 on 8,870 non-English scams: 0.4933 from raw text, 0.6906 from the dataset's English translation. Fixed model: 0.7761 raw, 0.9815 translated. Per language (Model 2012 raw / translated): Spanish 0.4582 / 0.6779 (n=3,195), Dutch 0.4926 / 0.7937 (n=1,551), French 0.423 / 0.7057 (n=870), German 0.5186 / 0.6203 (n=590), Japanese 0.3353 / 0.4566 (n=173). Translating first helps, but the translations were made by the dataset authors, not by a phone.

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

**Missed 2022+ scams** (32 of 1,080; full list in `results/fixed_model_missed_scams.csv`):

| scam_type | p(scam) | Text (shortened) | Hypothesis |
|---|---|---|---|
| spam | 0.0022 | "Ηello аll, guуsǃ I knоw, my mesѕаge maу bе toо sрeсifіc..." | Homoglyphs: Cyrillic letters that look Latin turn every word into an unknown token. |
| wrong number | 0.0222 | "How are you doing" | Opener only; the scam starts later in the chat, so this one text has no scam words. |
| hey mum/dad | 0.0719 | "Hello-Mum I accidentally dropped my mobile-phone down the toilet..." | Family-impostor wording looks like 2012 personal ham; no link or money. |
| others | 0.0494 | "hope I did not offend you ... I need xbox game pass code..." | Gift-code begging is a new lure with no training examples. |
| delivery | 0.1888 | "We are only one drop away. We should be with you by 16:03..." | Reads exactly like a genuine courier update; the scam part (link) was cut from the report. |
| others | 0.0338 | "Fuck off" | Probably not a scam at all: label noise in user-submitted reports. |
| others | 0.197 | "Hello ... I recently changed my bank information and I would love to change my DD details..." | Payroll-diversion scam written in polite personal style. |

**False alarms** (49 UCI test ham and 59 benign twins; full list in `results/fixed_model_false_alarms.csv`):

| Source | p(scam) | Text (shortened) | Hypothesis |
|---|---|---|---|
| UCI ham | 1.0 | "staff.science.nus.edu.sg/~phyhcmk/teaching/pc1323" | A bare link; the normaliser hides the domain, so every link looks alike. |
| UCI ham | 0.9849 | "NEFT Transaction with reference number ... has been credited..." | A genuine bank notification; all formal bank wording in training was scam. |
| UCI ham | 0.6331 | "what is your account number?" | "your account" is a strong scam phrase in 2020s banking smishing. |
| twins | 0.9993 | "Reminder: your credit card payment of $85.00 is due on Nov 25..." | Money + card + payment words = banking-scam vocabulary. |
| twins | 0.9908 | "First Harbor Bank Fraud Alert: Did you use your card ending 4821..." | Genuine fraud alerts use the same words as fake fraud alerts. |
| twins | 0.9891 | "Dental reminder: your cleaning is on Friday at 11 AM. Call 555-0142..." | "call tok_phone" was a top 2012 spam pattern (premium-rate numbers). |
| twins | 0.984 | "Out for delivery: your order #48211 will arrive today by 8pm." | Delivery wording is now dominated by delivery scams in the training data. |

**Root cause of the false alarms.** In training, every formal notification was a scam (IMC25) and every genuine message was 2012 personal chat (UCI ham). The fixed model therefore learned "formal notification style = scam". The fix needs real modern genuine notifications as negatives.

## 10. Limitations
- No real modern genuine texts; benign twins are synthetic and small (100 messages).
- Only about 16% of IMC25 rows can be dated (5,295 of 33,869), so the time split uses a subset.
- IMC25 contains user reports; some "scams" are not scams (label noise), and some reports lost their link.
- Named-entity tags were deleted, so brand names that the IMC25 anonymiser removed are missing, while UCI keeps its names.
- UCI ham is mostly Singapore student chat, not grandparent texts.
- Hyperparameters (C=10, class_weight balanced, min_df) were fixed in advance, not searched.
