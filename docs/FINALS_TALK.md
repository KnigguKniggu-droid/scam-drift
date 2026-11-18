# Finals talk: 5:00, one speaker

Status: READY TO REHEARSE. It is not rehearsed yet, so the timings are planned, not measured.
Speaker: Kartikeya Lathi (solo).
Event: Veritas AI finals, Nov 21, 11 AM ET. Format: 5-minute live demo and talk, then judge Q&A.
Score weights: demo and clarity 30, technical depth 30, impact 20, Q&A 20 (finals = 70% of the final score; Round 1 = 30%).

Companion files:
- `docs/DEMO_SCRIPT.md`: the commands, the 4 demo inputs, their verified outputs and the fallbacks.
- `docs/EXPLAINER.md`: every function, the formulas and 15 hard judge questions with answers.

## Number rules
- Every number in this talk comes from `results/metrics.json`, `results/real_ham_probe.json` or `results/real_ham_fix_probe.json`. The demo probabilities come from the app run recorded in `docs/DEMO_SCRIPT.md`.
- Never present the retrained model's 0.9657 recall as a win. Always say it together with its false alarms (597 of 600, 0.995).
- Say "about 76 percent" for 0.7565 and "nearly 97 percent" for 0.9657. Say the exact value if a judge asks.
- Do not say "accuracy". Say "scams caught" (recall) and "false alarms" (genuine texts flagged).

## What is on screen
| Window | Content | Prepared how |
|---|---|---|
| A | The app at `http://127.0.0.1:7860` in a browser, zoom 125% | `docs/DEMO_SCRIPT.md`, section 2 |
| B | `figures/lead_chart.png`, full screen | Open it in the Photos app before the call |
| C | The backup recording `video/backup_demo.mp4`, paused at 0:00 | `docs/DEMO_SCRIPT.md`, section 6 |
| D | A plain-text note with the 4 demo inputs | Copy them from `docs/DEMO_SCRIPT.md`, section 3 |

Share the whole screen, not one window. Then you can switch with Alt+Tab and not re-share.

## Running order

| Time | Section | Screen | Target words |
|---|---|---|---|
| 0:00-0:25 | 1. Hook with the main number | B (lead chart) | 55 |
| 0:25-0:50 | 2. User and moment | A (app, empty) | 68 |
| 0:50-2:10 | 3. LIVE demo, 4 inputs | A | 127 plus clicks |
| 2:10-3:00 | 4. How it works, with baselines | A, details table, then B | 121 |
| 3:00-3:55 | 5. The false-alarm finding | B (lead chart) | 129 |
| 3:55-4:35 | 6. Honest limits | B | 96 |
| 4:35-5:00 | 7. The ask | A or B | 62 |

Total: about 660 spoken words. At 150 words per minute that is about 4:25 of speech, plus about 20 seconds of clicks and pauses. This estimate is not measured; time the rehearsals.

Time checks: at 2:10 you must start section 4. At 3:55 you must start section 6. If you are late, use the cut plan below.

## Spoken lines

### 1. Hook (0:00-0:25). Screen B.
> "A scam filter trained on 2012 texts catches about 76 percent of real scams from 2022 to 2024.
> So I retrained it on modern scams. It caught nearly 97 percent.
> Then I tested it on real legitimate texts from one person's phone. It flagged 597 of 600.
> The obvious fix made the filter unusable. Here is why."

Numbers: 0.7565 (2012 filter, n=1,080 scams from 2022-24). 0.9657 (retrained). 597 of 600 = 0.995 (held-out brands). Source: `results/real_ham_fix_probe.json`.

### 2. User and moment (0:25-0:50). Switch to screen A.
> "My user is an older adult, a grandparent, and the family member who set up their phone.
> The moment: a text arrives. It says it is from the bank or a courier, and it has a link.
> Before she taps, she pastes it here.
> The checker has one job: warn her, without crying wolf. A warning that fires on every genuine text teaches her to ignore all warnings."

### 3. LIVE demo (0:50-2:10). Screen A.
Paste each input from the note (window D). Click "Check this text". Read the colour aloud. Inputs and verified outputs: `docs/DEMO_SCRIPT.md`, section 3.

Input 1, real 2022 bank scam (BOI ... `<URL>`). Expected: RED, 2012 model 0.82.
> "A real scam, reported in 2022. The dataset authors replaced the link with a placeholder.
> RED: do not tap, do not reply.
> The 2012 model scores it 0.82, threshold 0.32, and shows why: web link, visit, access, account."

Input 2, real 2023 "Hi Mum" scam. Expected: GREEN, 0.14 and 0.23.
> "A real 'Hi Mum, new number' scam from 2023. GREEN: both models miss it.
> No link, no scam words. It reads like family chat. The 2012 model caught 0 of 4 of these.
> That is why GREEN never says 'safe'."

Input 3, synthetic doctor reminder (Dr. Patel). Expected: YELLOW, 2012 model 0.48, updated model 0.98.
> "I wrote this one: a normal doctor's reminder. YELLOW. That is a false alarm.
> And the retrained model gives it 0.98."

Input 4, real 2022+ scam, the first example under the box (one click: "Hey M>itchel ..."). Expected: GREEN, 0.31 and 0.91.
> "A real scam from the 2022-24 test. The 2012 model: 0.31, just under 0.32. Missed.
> The retrained model catches it at 0.91. Catch more, but at what cost?"

If the app fails: say "I will switch to the recording", Alt+Tab to window C, press play. Do not debug live.

### 4. How it works, with baselines (2:10-3:00). Screen A details table, then B.
> "The data: the 2012 UCI SMS Spam Collection, and real scam reports from the IMC 2025 'Fishing for Smishing' dataset.
> I split the reports by year. Scams up to 2021 may be used for training. 1,080 scams from 2022 to 2024 are the untouched test.
> One normaliser turns every link, phone number, amount and date into a shared token.
> The model is TF-IDF on words and word pairs, plus logistic regression, so each verdict comes with its words, as you saw.
> The threshold comes only from training data, by cross-validation, with a missed scam costing five times a false alarm.
> Baselines: a link-or-urgency-word rule catches 0.6185 of the 2022-24 scams. The 2012 model catches 0.7565, against 0.9435 on held-out 2012 spam."

Numbers: 1,080 (test n). 0.6185 (rule). 0.7565. 0.9435 (UCI test recall). Source: `results/metrics.json`.

### 5. The false-alarm finding (3:00-3:55). Screen B (lead chart).
> "This is the main chart. Grey is the 2012 filter. Orange is the filter retrained on modern scams. Blue adds real legitimate texts.
> Left group: scams caught. 0.756, 0.966, 0.959.
> Middle group: false alarms on real legitimate texts from one inbox in India, from brands the model never saw. The 2012 filter already flags 0.91. The retrained filter flags 0.995.
> Why? In its training data, every formal message was a scam, and every genuine message was 2012 chat. So it learned: formal means scam.
> Blue: I added 606 real legitimate texts from 140 other brands. False alarms drop to 0.712, and recall stays at 0.959.
> Right group: Portuguese texts from Mozambique barely move: 0.625 to 0.618.
> So the missing ingredient is not more scams. It is modern legitimate texts."

Numbers (chart labels are the stored values printed with 3 decimals, so 0.7565 shows as 0.756 and 0.6175 as 0.618; exact values in `results/real_ham_fix_probe.json`): recall 0.7565 / 0.9657 / 0.9593. India held-out false alarms 0.91 / 0.995 / 0.7117 (n=600). Mozambique false alarms 0.3937 / 0.625 / 0.6175 (n=1,608). Training rows added: 606 from 140 brands. Test: 600 rows from 141 other brands.

### 6. Honest limits (3:55-4:35). Screen B.
> "Four limits.
> One: the India set is one person's inbox, 1,206 business texts from 555 senders. It is not a population sample, and I looked at it while exploring.
> Two: the 60 genuine-style texts are synthetic, written with AI help before the first model run.
> Three: this is a step between datasets, not a slide over time: 2017 reports 0.8175, 2023 reports 0.7751, and the intervals overlap.
> Four: I designed the colours after the first results, and the app's own 2012 model flags 0.8425 of that real inbox. It is a prototype, and not financial advice."

Numbers: 1,206 texts, 555 senders, 0.8425 (`results/real_ham_probe.json`). 2017: 0.8175 (n=126), 2023: 0.7751 (n=378) (`results/metrics.json`, `tables.recall_by_year`).

### 7. The ask (4:35-5:00). Screen A or B.
> "My ask. A scam filter needs consented, anonymised, modern legitimate texts as much as it needs scams.
> If you can connect me with a bank, a phone carrier or a senior centre, that is the data that fixes this.
> And the next test is with older users themselves: does this warning wording help them?
> Thank you. I am happy to take questions."

## Cut plan (use it if you are late)
- Late at 1:50: skip demo input 4. Say one line instead: "One more real scam: the 2012 model scores it 0.31, just under its threshold."
- Late at 2:40: cut the baseline sentence to: "A link-or-urgency rule catches 0.6185. The 2012 model catches 0.7565."
- Late at 4:20: cut limits to limit One and Four only.
- Never cut section 5 (the false-alarm finding). Never cut the 0.995 number.

## Q&A plan (20% of the score)
- Answer in 2-4 sentences. Then stop. Prepared answers: `docs/EXPLAINER.md`, section 4.
- Lead with the direct answer, then one number, then the limit.
- If you do not know, say "I did not measure that", and say how you would measure it.
- If a question is about AI use, say the truth first: Claude Code, an AI coding assistant, wrote much of the code under my direction. I reviewed and re-ran it, and I can explain it.
- Impact question: the README cites the FTC: people reported $470 million in losses to text-message scams in 2024 (FTC Data Spotlight, April 2025). This is an external source, not a result of this project.

## Rehearsal checklist
- [ ] Run the full talk 3 times with a timer. Target 4:45. Record each time here.
- [ ] Run the demo with the real app each time (not the recording).
- [ ] Check each spoken number against the source named in this file.
- [ ] Do one run with the app closed, to practise the switch to the recording.
- [ ] Do one Q&A drill: someone reads 5 random questions from `docs/EXPLAINER.md`; answer each in 30 seconds.
