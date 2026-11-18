# Finals talk outline (5 minutes, demo first)

Status: PLANNED. Use this only if we are named a finalist (announced Nov 18; live finals Nov 21).

Guidebook rules for the finals ("THE FINALS"): 5 minutes, then judge questions. Follow the video structure with more time on the demo and results. Run the demo live if it is reliable, and keep a recorded version open as a backup. Agree beforehand who answers which kinds of questions.

Roles
- Kartikeya: data, model, evaluation.
- William: user, demo, impact.

Every number below is copied from `results/metrics.json` (seeded run). Re-check them if the pipeline changes.

## Setup (before the call)
- Open `app.py` locally (`python app.py`) and test it with the three demo texts below.
- Open the backup demo recording in a second window, paused at 0:00.
- Open `figures/recall_by_year.png` and `figures/tradeoff_catch_vs_false_alarm.png` in a third window. Use only figures that exist in `figures/`.
- Paste the three demo texts into a note so nobody types under pressure.

## Running order

| Time | Speaker | Content | On screen |
|---|---|---|---|
| 0:00-0:20 | William | Hook. "This text arrived on a grandparent's phone. It says it is from a delivery company. She is not sure. Can a scam filter help her?" | The app, empty |
| 0:20-1:50 | William | Live demo, three texts. Use the app's examples (from `results/demo_examples.csv`). (1) The 2022+ scam that Model 2012 misses (p 0.3119, GREEN) and the fixed model catches (p 0.9074). (2) The 2022+ "handle a task" scam that both miss. (3) The synthetic bank code text: YELLOW, a false alarm. Read the warning text aloud. Say: "A warning means check first, not 'this is fraud'." | The app (backup: recording) |
| 1:50-2:30 | Kartikeya | The data. The 2012 filter learned from the UCI SMS Spam Collection. We tested it on real reports from the IMC 2025 "Fishing for Smishing" dataset: 1,080 dated 2022+ English scams, 12,364 undated English scams and 8,866 non-English scams. The organizers' sample tested 40 hand-written texts. | Dataset slide or README table |
| 2:30-3:10 | Kartikeya | The drift. "On held-out 2012 spam the filter catches 0.9435. On 2022+ scams it catches 0.7565." Say it is a step between datasets, not a steady decline by year (2017: 0.8175, 2023: 0.7751). | `figures/recall_by_year.png` |
| 3:10-3:50 | Kartikeya | The fix and its cost. Trained on earlier report years only, threshold frozen on a training-period validation split, tested on later years: recall 0.9657. False alarms on the 60 synthetic genuine-style texts: 0.9833 (95% interval 0.9114-0.9971), 59 of 60. One sentence on checks: link-only rule baseline, near-duplicate rate across the split (0.0139 at cosine >= 0.9). | `figures/tradeoff_catch_vs_false_alarm.png` |
| 3:50-4:15 | Kartikeya | Multilingual gap. Non-English scams (n=8,866): Model 2012 catches 0.508 from the raw text and 0.6959 from the English translation (an oracle upper reference). | README results table |
| 4:15-4:45 | William | Impact. Who uses it: the older adult and the family member who sets up the phone. What changes: a second opinion and a safe next step ("call the number on your card"). Limits: prototype, not financial advice; synthetic false-alarm set; report dates, not send dates. | The app warning text |
| 4:45-5:00 | Both | Takeaway (William): "A scam filter is not set-and-forget. It needs fresh data, and it must be checked for false alarms and other languages." Next step (Kartikeya, one line): test with real users and real genuine messages, with permission. | Title slide |

## Demo texts (fill in before rehearsal)
Use the three rows of `results/demo_examples.csv` (picked by a fixed rule in `src/scam_drift.py`, not by hand). They are also the first examples in the app.

Use only messages from the public dataset or our synthetic set. Use no personal data.

## Fallback
- If the live app fails, William says "We'll switch to the recording" and plays the backup at the same step. Do not debug live.
- If time runs short, cut the multilingual row (3:50-4:15) to one sentence. Never cut the false-alarm result.

## Questions: who answers

| Question type | Owner | Short answer to prepare |
|---|---|---|
| "How do you know it works?" | Kartikeya | Time split: trained on earlier report years, tested on later ones; threshold frozen before the test; comparison against "always not scam", a link-or-urgency-word rule and a link-only rule; near-duplicate rate across the split measured (0.0139 at cosine >= 0.9), but clusters were not forced to one side. |
| "What would cause it to fail?" | Kartikeya | New scam styles with no links; impersonation texts ("Hi Mum, new number"); languages with little training data; genuine bank and delivery texts (false alarms). |
| "Who would use this?" | William | An older adult (a grandparent) and the family member who sets up their phone. The moment: a text that claims to be from a bank, a delivery company or a government office. |
| Data, licences, leakage, metrics | Kartikeya | UCI SMS Spam Collection; IMC 2025 dataset, CC BY 4.0; synthetic benign twins written with AI assistance and labelled as a stress test. |
| User testing, design, ethics, what changes for people | William | Prototype, not financial advice. A warning means "check first". Next step: test with real users, with permission. |
| AI tool use | Either | Claude (Anthropic) via Claude Code wrote and ran the code and drafted the docs; the team reviewed every output and can explain every part. ChatGPT, Gemini and Claude chat were critics and red team (docs/CONSULT_LOG.md). |

## Rehearsal checklist
- Run the full talk twice with a timer. Target 4:45.
- Check every spoken number against `results/metrics.json`.
- Check that each figure named above exists in `figures/`.
