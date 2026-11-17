# Finals talk outline (5 minutes, demo first)

Status: PLANNED. Use this only if we are named a finalist (announced Nov 18; live finals Nov 21).

Guidebook rules for the finals ("THE FINALS"): 5 minutes, then judge questions. Follow the video structure with more time on the demo and results. Run the demo live if it is reliable, and keep a recorded version open as a backup. Agree beforehand who answers which kinds of questions.

Roles
- Kartikeya: data, model, evaluation.
- William: user, demo, impact.

Replace every `<NUMBER_FROM_METRICS>` with the value in `results/metrics.json` before rehearsal.

## Setup (before the call)
- Open `app.py` locally (`python app.py`) and test it with the three demo texts below.
- Open the backup demo recording in a second window, paused at 0:00.
- Open `figures/half_life.png` and the false-alarm chart in a third window. Use only figures that exist in `figures/`.
- Paste the three demo texts into a note so nobody types under pressure.

## Running order

| Time | Speaker | Content | On screen |
|---|---|---|---|
| 0:00-0:20 | William | Hook. "This text arrived on a grandparent's phone. It says it is from a delivery company. She is not sure, and English is not her first language. Can a scam filter help her?" | The app, empty |
| 0:20-1:50 | William | Live demo, three texts. (1) A modern parcel or toll scam: the 2012 filter says "not flagged", the fixed filter says "SCAM". Read the plain-language warning aloud. (2) A non-English scam: show the gap honestly. (3) A genuine-style bank text: the fixed filter may flag it. Say: "A warning means check first, not 'this is fraud'." | The app (backup: recording) |
| 1:50-2:30 | Kartikeya | The data. The 2012 filter learned from the UCI SMS Spam Collection. We tested it on 33,869 real reported scams from the IMC 2025 "Fishing for Smishing" dataset: 2017-2024 report dates, 8 scam types, 69 languages. The organizers' sample tested 40 hand-written texts; we test tens of thousands of real ones. | Dataset slide or README table |
| 2:30-3:10 | Kartikeya | The drift. "On 2012 spam the filter catches <NUMBER_FROM_METRICS>%. On modern scams it catches <NUMBER_FROM_METRICS>%." Filter half-life by report-date cohort and by top 3 scam types. | `figures/half_life.png` |
| 3:10-3:50 | Kartikeya | The fix and its cost. Trained on earlier report years only, threshold frozen on a training-period validation split, tested on later years: recall <NUMBER_FROM_METRICS>%. False alarms on the synthetic benign stress test: <NUMBER_FROM_METRICS>% (95% interval <NUMBER_FROM_METRICS>-<NUMBER_FROM_METRICS>%). One sentence on fairness checks: link-only rule baseline, campaign clusters kept on one side of the split. | Trade-off or learning-curve figure |
| 3:50-4:15 | Kartikeya | Multilingual gap. English recall <NUMBER_FROM_METRICS>% vs non-English <NUMBER_FROM_METRICS>%; English translation as an oracle upper reference gives <NUMBER_FROM_METRICS>%. | Per-language chart, if it exists |
| 4:15-4:45 | William | Impact. Who uses it: the older adult and the family member who sets up the phone. What changes: a second opinion and a safe next step ("call the number on your card"). Limits: prototype, not financial advice; synthetic false-alarm set; report dates, not send dates. | The app warning text |
| 4:45-5:00 | Both | Takeaway (William): "A scam filter is not set-and-forget. It needs fresh data, and it must be checked for false alarms and other languages." Next step (Kartikeya, one line): test with real users and real genuine messages, with permission. | Title slide |

## Demo texts (fill in before rehearsal)
1. Modern delivery or toll scam from the late test cohort: `<DEMO_TEXT_1>` (expected: 2012 = not flagged, fixed = SCAM; confirm in the app).
2. Non-English scam: `<DEMO_TEXT_2>` (use whatever result the app gives; do not choose a text only because it makes us look good).
3. Synthetic genuine-style bank text: `<DEMO_TEXT_3>` (shows the false-alarm weakness).

Use only messages from the public dataset or our synthetic set. Use no personal data.

## Fallback
- If the live app fails, William says "We'll switch to the recording" and plays the backup at the same step. Do not debug live.
- If time runs short, cut the multilingual row (3:50-4:15) to one sentence. Never cut the false-alarm result.

## Questions: who answers

| Question type | Owner | Short answer to prepare |
|---|---|---|
| "How do you know it works?" | Kartikeya | Time split: trained on earlier report years, tested on later ones; threshold frozen before the test; comparison against the 2012 model and a link-or-phone rule baseline; near-duplicate campaigns kept on one side of the split. |
| "What would cause it to fail?" | Kartikeya | New scam styles with no links; impersonation texts ("Hi Mum, new number"); languages with little training data; genuine bank and delivery texts (false alarms). |
| "Who would use this?" | William | Non-native-speaking older adults and the family member who helps them. The moment: a text that claims to be from a bank, a delivery company or a government office. |
| Data, licences, leakage, metrics | Kartikeya | UCI SMS Spam Collection; IMC 2025 dataset, CC BY 4.0; synthetic benign twins written with AI assistance and labelled as a stress test. |
| User testing, design, ethics, what changes for people | William | Prototype, not financial advice. A warning means "check first". Next step: test with real users, with permission. |
| AI tool use | Either | Claude Code for coding help and planning; ChatGPT, Gemini and Claude chat as critics and red team (docs/CONSULT_LOG.md). We wrote and checked every result ourselves. |

## Rehearsal checklist
- Run the full talk twice with a timer. Target 4:45.
- Check every spoken number against `results/metrics.json`.
- Check that each figure named above exists in `figures/`.
