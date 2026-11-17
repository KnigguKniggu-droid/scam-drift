# AI consultation log

We used three chat assistants as critics during planning. They gave advice only. We wrote and checked every line of code and every result ourselves. All prompts contained no personal data.

| Phase | Assistant | Question | Advice we used |
|---|---|---|---|
| Idea | ChatGPT, Gemini, Claude | Rank 4 ideas (scam drift, PM2.5 forecast, heart-disease transfer, look-alike language ID) under the Round 1 rubric | All three ranked "Scam Drift" first. ChatGPT named the IMC 2025 "Fishing for Smishing" dataset. Gemini warned that the Mishra & Soni 2022 dataset reuses UCI ham, and suggested "benign twin" false-alarm tests. |
| Originality | ChatGPT, Gemini | The organizers' sample submission ("ScamCheck") already tests 40 hand-written modern texts. How do we differ? | Headline: "Can yesterday's AI recognise tomorrow's scams?". User: non-native-speaking older adults and the family member who helps them. Gemini: a "filter half-life" curve (recall against months since the training cutoff). ChatGPT: an unseen-campaign test (group near-duplicate templates so one campaign is never in both train and test). |
| Method red team | ChatGPT, Gemini, Claude | List the most serious flaws a skeptical ML judge would find | See the section below. |
| v1 results review | Claude, Gemini, ChatGPT | We shared the v1 numbers (naive fix: 97% recall but 98% false alarms on synthetic legit texts). What is the honest headline and what should we ship? | Claude: the headline is that the missing piece is modern legitimate texts, not more scam data; ship warn-only, link-gated, plus fixed rules for code requests and wrong-number openers. Gemini: a three-tier triage (red = flag + link/phone, yellow = "ask family before replying", green), translate first, add a real ham corpus (NUS SMS Corpus). We adopted the three-tier triage and evaluate it. |

## Red-team findings and our responses

| # | Flaw raised | Raised by | Our response (see docs/V2_SPEC.md) |
|---|---|---|---|
| 1 | Source confound: negatives are 2012 ham, positives are modern scams, so the fix model may learn "modern era = scam", not "scam". | Claude, ChatGPT | Source-separation AUC test. Fix variant trained with half of a frozen synthetic modern-benign set as extra negatives; the other half stays test-only. Report false alarms for every model. |
| 2 | The `<URL>` token alone may do most of the work. | Claude | Rule baseline "flag any `<URL>` or `<PHONE>`". Ablation: retrain without placeholder tokens. |
| 3 | Synthetic false-alarm set is small and written by us. | Claude, ChatGPT, Gemini | Freeze it before results; label it a "synthetic stress test"; report counts with Wilson 95% intervals; never claim real-world precision. Prevalence-adjusted precision at an assumed 5% scam rate is marked as an assumption. |
| 4 | Campaign/template leakage across the time cutoff. | Claude, ChatGPT, Gemini | Cluster near-duplicates (char n-gram TF-IDF cosine > 0.8), date each cluster by first report, split whole clusters; report removed counts. |
| 5 | Half-life curve mixes time with scam-type and language mix; dates are report dates, not send dates. | Claude, ChatGPT | Time zero = held-out UCI spam recall; per-year recall with counts and per scam type; call cohorts "report-date cohorts". |
| 6 | Multilingual gap is guaranteed for an English bag-of-words model; translations are an oracle. | Claude, ChatGPT, Gemini | Paired raw vs translated evaluation on the same messages, translation labelled "oracle upper reference"; out-of-vocabulary share; char n-gram model as the multilingual candidate; native-English vs translated scams reported separately. |
| 7 | "Fix works" may only mean "more data". | Claude | Learning curve: 100 / 500 / 2,000 modern examples added. |
| 8 | Threshold chosen on test data inflates results. | ChatGPT, Gemini | Threshold fixed on a validation split from the training period, frozen before the later-period test. |
