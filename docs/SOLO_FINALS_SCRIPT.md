# Scam Drift | Solo finals presentation

**Use one browser window. Share that window in Zoom.** Keep three tabs in this order: website cover, checker, submitted chart. Open the checker in advance, paste the prepared bank text, and leave it unchecked. Rehearse for **2:40–2:50**. The times below are targets.

- [Cover and 3D scanner](http://127.0.0.1:8174/)
- [Checker](http://127.0.0.1:8174/#try)
- [Submitted study chart](../tools/qa/submitted-study-chart.png)
- [Backup screenshot](../tools/qa/captured-red.jpg)
- [Public demo](https://macro-benefits-police-festivals.trycloudflare.com/)

**Paste into the checker before screen sharing**

```text
We locked your bank account. Reply with your verification code to restore access: https://bank.example.test
```

## 0:00–0:30 | Show the cover

> Imagine your grandparent gets a text saying their bank account is locked. It asks for a verification code, and they have seconds to decide whether to reply. I’m Kartikeya. William and I built Scam Drift for the AI and Finance track. We wanted to help people pause before they act, and find out why a filter trained on old texts can struggle with what lands on a phone today.

## 0:30–1:10 | Switch to the checker and click Check a text

> Here’s a fictional example. The checker flags it RED and points to the exact request: “Reply with your verification code.” Then it gives you something to do. Open the banking app you normally use, or call a number you already trust. Even on GREEN, we tell you the sender is unverified. The demo on screen uses our newer checker. The results I’m about to show are from our submitted study.

## 1:10–2:20 | Switch to the study chart

> We took a filter trained on 2012 SMS and tested it on 1,080 real scam reports from 2022 through 2024. It caught about 76 percent. Retraining on modern scams raised recall to almost 97 percent. Then we tried that model on 600 genuine texts from brands held out of training. It flagged 597. Imagine getting a warning on almost every legitimate message you receive.
>
> We added actual modern legitimate texts to training. The new model still caught about 96 percent of reported scams, and false alarms on that inbox fell to about 71 percent. That’s still too high. It tells us you need examples of what ordinary texts look like today if you want a filter to catch more scams without flooding people with warnings.

## 2:20–2:45 | Close on the chart

> The old and new datasets were collected differently, so we can’t isolate the effect of time. And that genuine sample came from one inbox. Next, I’d test on more consented inboxes and ask older adults what they’d do after each warning. The question I care about is whether it helps someone make the right call before they tap.

## If something stalls

- Wait at most three seconds. If the checker stalls, switch to the saved RED screenshot and keep speaking. The chart and screenshot work offline.
- Skip the opening scroll if it delays the demo. The study chart is the main evidence. Keep 15 seconds in reserve for clicks and Zoom.
- For Q&A, use one direct answer and one supporting number or limitation. Tell the judges which model and cohort the number describes. If they ask about the current checker, explain that the fine-tuned model was added after submission and has separate results.

## Where everything lives on the site

| Section | What it shows | When to use it |
| --- | --- | --- |
| Cover | William’s 3D scanner and the old-filter story | Open here. One short scroll is enough. |
| Reported texts and “Before the tap” | Corpus at a glance and the user’s moment of decision | Optional if a judge asks why you built it. |
| Findings and “Who it misses” | Cross-era gap and conversational misses | Use for questions about drift, wrong-number and family impersonation examples. |
| Every report | Searchable research mosaic and individual reports | Use only if asked to show a particular report. |
| The fix | The retraining trade-off and genuine look-alikes | The chart conveys this finding fastest. |
| How it works and colors | What the old filter reads and how to interpret a warning | Answer model and safety questions here. |
| Check a text | Current checker and practical next steps | Run the one prepared example. |
| If you already acted | Next steps after tapping, replying, sharing a code or paying | Use for a question about recovery. |
| Full results | Tables, scope, and sources | Use for follow-up. |
| Inbox Flood lab | Alternate 3D visualization of historical model results | Optional. Leave it out of the three-minute talk. |
