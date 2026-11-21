# Scam Drift | Solo finals presentation

**Remember three moves. Cover → Check → Chart.** Share only the browser window. Put the cover, checker, and chart in three tabs. Pre-paste the example with the checker still empty of results. Keep the [RED screenshot](../tools/qa/captured-red.jpg) open as a fourth tab. Aim to finish by **2:45**.

- [Cover and 3D scanner](http://127.0.0.1:8174/)
- [Checker](http://127.0.0.1:8174/#try)
- [Submitted study chart](../tools/qa/submitted-study-chart.png)
- [Backup screenshot](../tools/qa/captured-red.jpg)
- [Public demo](https://macro-benefits-police-festivals.trycloudflare.com/)

**Paste into the checker before screen sharing**

```text
We locked your bank account. Reply with your verification code to restore access: https://bank.example.test
```

## 0:00–0:25 | Cover. Give them the problem.

> Imagine your grandparent gets a text that says their bank account is locked. It asks for a verification code. Would they know what to do before replying? I’m Kartikeya. William and I built Scam Drift to help with that decision. We also asked how well an old spam filter holds up against newer scams.

## 0:25–1:05 | Checker. Click once and point to the action.

> Here’s a fictional bank text. [Click **Check a text**.] The checker flags the request for a verification code. It says to open the bank app you already use or call a number you trust. Even a GREEN result leaves the sender unverified. You’re seeing our current demo. These next numbers come from the submitted study.

## 1:05–2:15 | Chart. Point left for scams caught, then center for false alarms.

> The old filter caught about 76 percent of 1,080 reported scams from 2022 to 2024. Retraining on newer scams brought that close to 97 percent. But look at the middle of the chart. That same model flagged 597 out of 600 genuine texts from one inbox. Imagine getting a warning almost every time a legitimate text comes in.
>
> Then we trained it on examples of normal modern texts too. It still caught about 96 percent of the scams, and false alarms fell from 597 to 427 out of 600. That’s an improvement, but 71 percent is still too high. The useful finding is that showing the model what genuine texts look like today helped reduce those false alarms.

## 2:15–2:45 | Close. Name the limit and the next test.

> The old and new datasets were collected differently, so we can’t say how much of the gap was caused by time. Our genuine test sample came from one inbox. Next, I’d test on more inboxes with people’s consent and see whether older adults actually know what to do after a warning. That’s the decision Scam Drift is meant to help with. Thank you.

**If you lose your place:** 76% with the old filter. 97% after retraining, but 597 of 600 genuine texts flagged. Adding genuine training texts cut those false alarms to 427 while keeping about 96% recall.

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
