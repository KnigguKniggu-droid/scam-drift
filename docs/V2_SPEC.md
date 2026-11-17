# Scam Drift v2 spec (from the AI red-team round, 2026-11-17 ~18:30 ET)

Apply on top of the v1 pipeline (`src/scam_drift.py`). Keep every v1 number reproducible; add new keys to `results/metrics.json`; never invent numbers.

## Framing
- Headline: "Can yesterday's AI recognise tomorrow's scams?"
- User: non-native-speaking older adults and the family member who sets up their phone. The moment of use: a text arrives that claims to be from a bank, a delivery company or a government office, and they are unsure.
- State plainly in the README that the organizers' sample ("ScamCheck") tested 40 hand-written texts; we test tens of thousands of real reported scams across report years, scam types and languages, and we measure drift, a fix and its cost.

## Method additions (each must appear in metrics.json, the notebook and docs/RESULTS_DETAIL.md)
1. **Source confound.** Source-separation AUC (UCI spam vs modern scam, after normalisation). New model variant `fix_plus_benign`: training negatives = UCI ham + a random half of the synthetic modern-benign set (seeded); the other half stays test-only. Report modern recall and false alarms on the held-out benign half for EVERY model (2012, fix, fix_plus_benign). Label the benign set "synthetic stress test, written with AI assistance".
2. **URL shortcut.** Rule baseline "flag if `<url>` or `<phone>` present" (with its recall and false-alarm rate). Ablation: retrain the fix model with placeholder tokens removed; report the change.
3. **Uncertainty.** Wilson 95% intervals for every rate computed on fewer than 1,000 messages (benign false alarms, per-scam-type recall with small n). Prevalence-adjusted precision at an ASSUMED 5% scam rate (label it as an assumption).
4. **Template leakage.** Cluster modern texts (char_wb 3-5 TF-IDF, cosine > 0.8, e.g. via nearest neighbours or greedy grouping on a capped sample if needed for speed), date each cluster by its first report, assign whole clusters to train/test by that date; drop test clusters that overlap training clusters; report cluster counts and how many test rows were removed. Recompute the main fix result on the cluster-safe split and report both.
5. **Filter half-life.** Time zero = held-out UCI spam recall (2012 model). Then recall of the 2012 model per report year (counts shown) overall and for the 3 most common scam types separately. Optionally a model trained up to year Y tested on Y+1, Y+2 ... ("months since cutoff"). Call cohorts "report-date cohorts". Figure: figures/half_life.png.
6. **Multilingual.** Paired evaluation on non-English rows that have a translation: raw text vs English translation through the SAME model; label translation "oracle upper reference". Out-of-vocabulary share of raw non-English text. Char-n-gram model trained on UCI + early modern scams (all languages, raw text) as the multilingual candidate; per-language recall for the top 8 languages with counts. Native-English scams vs translated scams reported separately.
7. **Learning curve.** Fix model with 0 / 100 / 500 / 2,000 / all early-period modern scams added; recall on the later test + false alarms on held-out benign half. Figure: figures/learning_curve.png.
8. **Threshold discipline.** Threshold chosen on a validation split from the training period only; frozen before the later-period test; state the cost ratio used.

## v1 result that changes the plan (2026-11-17 ~18:35 ET)
The naive fix (UCI + modern scams) catches 97% of 2022-24 scams but flags 59 of 60 synthetic legitimate modern texts (98%). It learned "sounds modern/formal = scam". NEVER present the 97% as a win anywhere (README, form, video). The headline is now: "A 2012 filter misses new scam styles; retraining on new scams alone makes it cry wolf on almost every real modern text; the missing ingredient is modern legitimate texts."

9. **Modern negatives.** Add real legitimate SMS if docs/EXTRA_DATA.md (data scout) recommends a safe public set (also consider the NUS SMS Corpus, real 2010-2015 ham, licence permitting). Variants: `fix_plus_benign` (UCI ham + half of synthetic legit, phrasing-disjoint split by category/institution) and, if available, `fix_plus_real_ham`. Report false alarms on the held-out synthetic half AND on any held-out real modern ham.
10. **Shipped design = three-tier triage, warn-only, never blocks** (consensus of Claude, Gemini; evaluate it, do not just describe it):
    - RED "Likely scam - do not tap, do not reply": model flags AND (link or phone token).
    - YELLOW "Ask family before replying": model flags with no link/phone, OR a rule fires: asks for a code/PIN/password, or a 'wrong number'/'hi mum new number' opener from an unknown sender pattern.
    - GREEN otherwise.
    - Non-English text: score the provided English translation as an oracle reference and say a real deployment needs on-device translation (UNVERIFIED quality).
    - Report per tier: share of 2022-24 scams in RED, in RED+YELLOW; share of synthetic legit in RED, in YELLOW. Wilson intervals.
    - Gradio app shows the tier, a plain-language reason, and the top words, with a "prototype, not financial advice" line.

## Deliverable updates
- README: keep the official template order and about one page; update numbers from metrics.json only; add 2-3 lines for the new findings; add "Compared with the organizers' sample" line in "What we added".
- docs/RESULTS_DETAIL.md: full tables for 1-8.
- Notebook re-executed with outputs. app.py unchanged unless the chosen final model changes.
