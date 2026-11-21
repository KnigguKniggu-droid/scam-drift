# Scam Drift | Solo finals script

**Cover → Check → Chart → Thank you.** Read the **Say** lines aloud. Use the **Do** lines to move through the demo. Aim for **2:45**.

## Set up before you share

Open four tabs in this order in one browser window. Share that window in Zoom.

1. [Cover](http://127.0.0.1:8174/)
2. [Checker](http://127.0.0.1:8174/#try)
3. [Submitted study chart](../tools/qa/submitted-study-chart.png)
4. [Saved RED result for the same example](../tools/qa/captured-red.jpg)

Paste the message below into tab 2. Leave it ready to submit. Return to tab 1. Keep the Q&A panel outside the shared window. If the local site is down, open the [public demo](https://macro-benefits-police-festivals.trycloudflare.com/) in tabs 1 and 2 and go to the checker in tab 2.

```text
We locked your bank account. Reply with your verification code to restore access: https://bank.example.test
```

## 0:00–0:25 | Cover

**Do** · Stay on tab 1. Leave the cover on screen.

**Say**

> Imagine your grandparent gets a text that says their bank account is locked. It asks for a verification code. What should they do next? I’m Kartikeya. William and I built Scam Drift to help with that decision. We also wanted to know how well a spam filter trained on older texts holds up against newer scams.

## 0:25–1:05 | Check the text

**Do** · Click tab 2 or press **Ctrl+2**. Point at the message.

**Say**

> Let me show you. This is a fictional bank text asking for a verification code.

**Do** · Click **Check a text**. Point to the RED warning and the next steps. If the result takes more than three seconds, press **Ctrl+4** and say “Here’s the result from an earlier run with the same text.” Then continue.

**Say**

> Scam Drift flags the request for a verification code. It tells you what to do next. Keep the code private, then open the bank app you already use or call a number you trust. Even a GREEN result leaves the sender unverified. You just saw our current demo. The chart shows what we measured in the submitted study.

## 1:05–2:15 | Show the evidence

**Do** · Click tab 3 or press **Ctrl+3**. Point to the left orange bar at “97 percent.” Move to the middle orange bar at “597.”

**Say**

> The old filter caught about 76 percent of 1,080 reported scams from 2022 to 2024. After we retrained it on newer scams, it caught about 97 percent. Here’s the catch. In our test on 600 genuine texts from one inbox, it flagged 597 of them. Imagine getting a warning almost every time a legitimate text comes in.

**Do** · Point to the middle blue bar at “427.” Point to the left blue bar at “96 percent.”

**Say**

> So we also trained the filter on genuine modern texts. False alarms fell from 597 to 427 out of 600. It still caught about 96 percent of the reported scams. That’s progress, and 71 percent false alarms is still too high for everyday use.

## 2:15–2:45 | Thank the judges

**Do** · Leave the chart on screen. Stop sharing after you say thank you.

**Say**

> The old and new datasets were collected differently, so we can’t say how much of the gap came from time. And our genuine test sample came from one inbox. My next step would be to test more inboxes with people’s consent and see whether older adults know what to do after a warning. That’s the decision Scam Drift was built to help with. Thank you.

**If you lose your place** · Old filter 76%. Retrained 97% and 597 false alarms. With genuine training texts, 96% and 427 false alarms. Both false-alarm counts are out of 600 genuine texts from one inbox.

## When the judges start Q&A

- If the organizers allow live assistance, keep Zoom playback on **Logitech USB Headset H540**. The panel should say **Armed · waiting for Q&A**. It listens to headset playback. Your own microphone alone will not trigger that mode.
- If the host opens Q&A and the panel still says **Armed**, click **Start Q&A now**. If it misses a question, ask the judge to repeat it or type it and click **Ask**.
- Give one direct answer and one supporting number or limitation. If asked about the fine-tuned model in the current demo, say it was added after submission and evaluated separately.