# Live demo runbook

Purpose: run the Scam Drift app live in the finals (Nov 21, 11 AM ET) without surprises.
Presenter: Kartikeya Lathi (solo). The demo is section 3 of `docs/FINALS_TALK.md` (0:50-2:10).

## 1. Verification record (2026-11-17)
These facts were observed on this machine on 2026-11-17, with the committed `models/model_2012.joblib` and `models/model_fixed.joblib`:
- `import app` works. `app.build_demo()` returns a Gradio `Blocks` object. Exit code 0.
- `app.predict()` returned the outputs in section 3 for all 4 inputs (plus 2 backups and an empty input).
- `.venv\Scripts\python.exe app.py` served HTTP 200 at `http://127.0.0.1:7860/` about 4 seconds after start.
- With `$env:GRADIO_SERVER_PORT='7861'`, the app served HTTP 200 at `http://127.0.0.1:7861/`.
- The command-line fallback in section 5 printed the RED verdict.
- Environment: Python 3.13.2, gradio 6.32.0, scikit-learn 1.9.1 (`.venv`).

Not verified:
- Whether the page loads with no internet connection: UNKNOWN. Test it in section 2, step 5.
- The full click-through in a browser by a person: not done by Claude. Do it in rehearsal.

Re-run this record if `models/*.joblib`, `app.py` or `src/scam_drift.py` changes.

## 2. Start the app (PowerShell)
Do this 30 minutes before the call.

1. Open PowerShell. Go to the project:
   ```powershell
   cd C:\Users\ganes\scam-drift
   ```
2. Check the model files exist (expected: `True True`):
   ```powershell
   (Test-Path models\model_2012.joblib), (Test-Path models\model_fixed.joblib)
   ```
3. Start the app. Leave this window open for the whole call:
   ```powershell
   .venv\Scripts\python.exe app.py
   ```
   Expected: a line with `http://127.0.0.1:7860` after a few seconds.
4. Open `http://127.0.0.1:7860` in the browser. Set the zoom to 125% (Ctrl + plus).
5. Offline check (one time, before Nov 21): turn Wi-Fi off, reload the page, run input 1. Write the result here: ______. Turn Wi-Fi on again.
6. Warm-up: run all 4 inputs once. Compare each result with section 3.
7. Clear the text box. Scroll to the top. Close other browser tabs and notifications (Windows: Focus assist / Do not disturb ON).

## 3. The 4 demo inputs, expected outputs and what to say
Put these 4 texts in a plain-text note (window D). Copy and paste them. Do not type under pressure.

Inputs 1, 2 and 4 are real reports from the IMC 2025 "Fishing for Smishing" dataset (2022+ test set, CC BY 4.0). The dataset authors replaced links and phone numbers with `<URL>` and `<PHONE_NUMBER>`. The app's normaliser reads those placeholders as a link and a phone number. Input 3 is a synthetic genuine text from `data/benign_twins.csv`.

Recorded outputs (from `app.predict()` on 2026-11-17; exact probabilities from `app.score()`):

| # | Input (paste exactly) | Truth | Colour | 2012 model p (threshold 0.32) | Updated model p (threshold 0.24) | Top words, 2012 model |
|---|---|---|---|---|---|---|
| 1 | `BOI: We have temporarily restricted access to your account due to suspicious activity. Please visit <URL>` | real scam, 2022, banking | RED | 0.8156 (app shows 0.82) | 0.9958 (app shows 1.00) | [a web link], visit, access, visit [a web link], account |
| 2 | `Hi Mum I accidentally dropped phone and smashed the screen so Im using an old one can you save my new number <PHONE_NUMBER> for the time being` | real scam, 2023, "hey mum/dad" | GREEN (miss) | 0.1417 (0.14) | 0.2325 (0.23), no flag | [a phone number], new, number, phone and, phone |
| 3 | `Reminder: you have an appointment with Dr. Patel on Tuesday, Nov 12 at 9:00 AM. Reply C to confirm or R to reschedule.` | genuine (synthetic) | YELLOW (false alarm) | 0.481 (0.48) | 0.977 (0.98) | reply, c, reminder, [a date or time] [a date or time], r |
| 4 | First example under the text box: `Hey M>itchel:\|, \| wanted to see if you are still interested in this >> <URL> t29zq1r` (click it; do not paste) | real scam, 2022+, "spam" | GREEN (miss by 2012 model) | 0.3119 (0.31) | 0.9074 (0.91), flags | [a web link], [a number], r, wanted to, t [a number] |

Input 4 is also row 1 of `results/demo_examples.csv` (p_2012 0.3119, p_fixed 0.9074). It was picked by a fixed rule in `step_demo_examples`, not by hand.

### What to say
The exact spoken lines are in `docs/FINALS_TALK.md`, section 3. That file is the master. The short versions below are for the recording and for practice.
Say one line per input. Point at the colour, then the probability, then the words.

1. RED. "A real scam from 2022. RED: do not tap, do not reply, call the number on your card. The 2012 model gives 0.82 against a threshold of 0.32. The words: web link, visit, access, account."
2. GREEN, miss. "A real 'Hi Mum, new number' scam from 2023. GREEN. Both models miss it: 0.14 and 0.23. No link, no scam words. In the 2022-24 test the 2012 model caught 0 of 4 of these. GREEN never says 'safe'."
3. YELLOW, false alarm. "I wrote this: a normal doctor's reminder. YELLOW: ask a family member. That is a false alarm. The retrained model gives it 0.98."
4. GREEN, drift. "A real 2022+ scam. The 2012 model gives 0.31, just under 0.32: missed. The retrained model catches it at 0.91. Catch more, but at what cost? That is the next chart."

### Backup inputs (verified the same day)
| Use when | Input | Colour | 2012 p | Updated p |
|---|---|---|---|---|
| Input 1 fails or a judge asks for another scam | `AN POST: Your package has a €1.90 unpaid fee. To pay this visit <URL> . If this is not paid the package will be returned.` (real 2022 delivery scam; the euro sign can break in some notes, so input 1 is primary) | RED | 0.9427 (0.94) | 0.9993 (1.00) |
| A judge asks "what if the link is real text, not `<URL>`?" | `BOI: We have temporarily restricted access to your account due to suspicious activity. Please visit http://boi-secure-login.com` (input 1 with an invented link) | RED | 0.82 | 1.00 |
| A judge asks for a harsher false alarm | `Dental reminder: your cleaning is on Friday at 11 AM. Call 555-0142 to change it.` (synthetic genuine) | RED (false alarm) | 0.7721 (0.77) | 0.989 (0.99) |
| Empty box clicked by mistake | (empty) | "Paste a text message above." | - | - |

Honest note on the dental example: the app makes RED when the 2012 model flags AND the text has a link OR a phone number. `results/metrics.json` ("triage") measured only the link version (RED on 0 of 60 synthetic genuine texts). The phone part is not measured. The dental reminder shows it can produce a RED false alarm. Say this if a judge asks about the colours.

## 4. Timing inside the demo (80 seconds)
| Time | Action |
|---|---|
| 0:50 | Paste input 1. Click "Check this text". Speak line 1. |
| 1:10 | Select all in the box (Ctrl+A), paste input 2. Click. Speak line 2. |
| 1:30 | Ctrl+A, paste input 3. Click. Speak line 3. |
| 1:50 | Scroll down. Click example 1 under the box. Click "Check this text". Speak line 4. Skip if you are late (see the cut plan in `docs/FINALS_TALK.md`). |
| 2:10 | Stop. Go to section 4 of the talk. |

Clicking an example only fills the box. You must still click "Check this text".

## 5. Failure fallbacks
Rule: if something fails, say one sentence, switch, and continue. Do not debug live.

| Failure | What you see | What to do | Verified? |
|---|---|---|---|
| Port 7860 in use | Error `Cannot find empty port` or the app opens on another port | Stop the old app (Ctrl+C in its window), or start on port 7861: `$env:GRADIO_SERVER_PORT='7861'; .venv\Scripts\python.exe app.py`, then open `http://127.0.0.1:7861` | Port 7861: yes, HTTP 200. The exact error text: not verified |
| Model files missing | `FileNotFoundError` for `models\model_2012.joblib` | Run `git checkout post-deadline -- models` (the models are committed). Retraining (`.venv\Scripts\python.exe src\scam_drift.py`) needs the raw data in `data\raw` and took 24.8 s in the recorded run; do not retrain during the call. | Model check: yes. Retrain: not re-run today |
| Page does not load or freezes in the call | Blank page, spinner | Say "I will switch to the recording." Alt+Tab to window C. Press play. | Recording: to be made (section 6) |
| Browser works but you prefer a terminal | - | Command-line fallback, prints the colour and the 2012 row of the table: `.venv\Scripts\python.exe -c "import app; v,d,x = app.predict('BOI: We have temporarily restricted access to your account due to suspicious activity. Please visit <URL>'); print(v.splitlines()[0]); print(d.splitlines()[2])"` | Yes, printed RED and 0.82 |
| Screen share fails | Judges see nothing | Say the 4 results aloud from the table in section 3. Then describe the lead chart: "0.995 false alarms after retraining, 0.7117 after adding real legitimate texts." | - |
| Wrong colour appears | Output differs from section 3 | Say "This differs from my rehearsal; the recorded result is in the runbook", give the recorded colour, and move on. Check later whether the models changed. | - |
| Internet drops | Video call drops | Rejoin. The app runs locally and keeps running. Whether the page needs the internet is UNKNOWN until step 5 of section 2 is done. | - |

## 6. Backup screen recording (make it before Nov 21)
Goal: a 60-90 second recording of the same 4 inputs, so the demo can be shown if the live app fails.
Save it as `video/backup_demo.mp4`. The `video/` folder is gitignored, so the file stays local.

### What to capture (target 75 seconds)
| Time | Capture |
|---|---|
| 0:00-0:05 | The empty app page, title "Scam Drift" visible |
| 0:05-0:22 | Paste input 1, click, hold on the RED verdict and the details table |
| 0:22-0:40 | Paste input 2, click, hold on GREEN and the two probabilities (0.14, 0.23) |
| 0:40-0:58 | Paste input 3, click, hold on YELLOW and the updated model's 0.98 |
| 0:58-1:15 | Click example 1, click "Check this text", hold on GREEN, 0.31 and 0.91 |

Recording rules:
- Browser window only, 1920x1080 if possible, zoom 125%, so the verdict, the table and the words fit on one screen.
- No sound is needed. You speak over it live. Silent playback avoids audio echo in the call.
- Move the mouse slowly. Pause 3 seconds on each verdict.
- Do not show other tabs, bookmarks, notifications or personal files.

### Option A: Windows Game Bar (built in)
1. Click the browser window so it is active.
2. Press Win+Alt+R to start recording. Do the 4 inputs.
3. Press Win+Alt+R again to stop.
4. The file goes to `%USERPROFILE%\Videos\Captures`. Move it to `video\backup_demo.mp4`.
Note: Game Bar records one app window, not the whole desktop. That is enough here.

### Option B: OBS Studio
1. Add a source: Window Capture, choose the browser window.
2. Settings > Output: recording format mp4 (or mkv, then File > Remux Recordings to mp4).
3. Settings > Video: base and output resolution 1920x1080, 30 fps.
4. Click Start Recording, do the 4 inputs, click Stop Recording.
5. Move the file to `video\backup_demo.mp4`.

### After recording
- Play the file once from start to end. Check that every number in section 3 is readable.
- Open it in window C before the call, paused at 0:00.

## 7. Pre-call checklist (T minus 15 minutes)
- [ ] App running, page at 125%, box empty (section 2).
- [ ] All 4 inputs ran once today and matched section 3.
- [ ] Note with the 4 inputs open (window D).
- [ ] `figures/lead_chart.png` open full screen (window B).
- [ ] `video/backup_demo.mp4` open, paused at 0:00 (window C).
- [ ] Notifications off. Other tabs closed. Laptop charging.
- [ ] Whole screen shared in the call; Alt+Tab order tested.
