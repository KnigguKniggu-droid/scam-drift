# Scam Drift | Two-presenter backup

**Kartikeya shares and controls all four tabs.** Kartikeya opens and runs the checker. William explains the research chart and closes. Use this version if William is connected and can unmute. Otherwise use the [solo script](SOLO_FINALS_SCRIPT.md).

**If William drops** · Keep sharing. Continue with the next unread **William says** paragraph yourself. If he drops mid-paragraph, pick up at the next number or sentence. If he comes back mid-talk, finish the section yourself.

## Set up before you share

Open four tabs in this order in one browser window. Share that window in Zoom.

1. [Live cover](https://macro-benefits-police-festivals.trycloudflare.com/)
2. [Live checker](https://macro-benefits-police-festivals.trycloudflare.com/#try)
3. [Submitted study chart](https://raw.githubusercontent.com/KnigguKniggu-droid/scam-drift/post-deadline/tools/qa/submitted-study-chart.png).
4. [Saved RED result](https://raw.githubusercontent.com/KnigguKniggu-droid/scam-drift/post-deadline/tools/qa/captured-red.jpg) for the same message.

In tab 2, scroll until you see **Paste the text message here** and the **Check a text** button. Click inside the text box. Paste the message below with **Ctrl+V**. Leave it ready to check. Return to tab 1. Keep this script and the Q&A panel outside the browser window you share.

If the public pages fail on your PC, open `http://127.0.0.1:8174/` and `http://127.0.0.1:8174/#try` in tabs 1 and 2 if your local server is running. The saved RED result works if neither server is available.

```text
We locked your bank account. Reply with your verification code to restore access: https://bank.example.test
```

## 0:00–0:25 | Cover

**Do** · Start on tab 1 with the site title and scanner visible. Keep the cover on screen while you introduce the problem.

**Kartikeya says**

> A text says your bank account is locked, and the only way back in is to send a code. You have a few seconds to decide what to do. I’m Kartikeya. William and I built Scam Drift to help someone make that decision. And building it led us to a harder question. How do you catch more scams without making people tune out the warnings?

## 0:25–1:05 | Check the text

**Do** · Click tab 2 or press **Ctrl+2**. Point at the pasted message in the box. If tab 2 is missing, use **Try it** in the site header, then paste the same message.

**Kartikeya says**

> Here’s that bank text. It’s an example we wrote for the demo. I’ll run it through the checker.

**Do** · Click **Check a text** below the box. Look for the result card beside the form. On a narrow window, it is below the form. Point to **RED** and **Stop and verify the request.** Then move the pointer to the advice about keeping the code private and using the official app or a trusted number. If the card does not appear within three seconds, press **Ctrl+4** and say “Here’s the saved result from the same message.” Then read the next lines.

**Kartikeya says**

> It comes back red. Look at the advice. Keep the code private. Open the bank app yourself, or call a number you already trust. That gives someone a next step they can actually use. Green still means the sender is unverified. This is our current demo. Now let me show you what we learned in the submitted study.

## 1:05–2:15 | Show the evidence

**Kartikeya does** · Switch to tab 3. If William is connected, say “William, what happened when we retrained it?” Give him two seconds to start. If you hear nothing, say “Here’s what we found” and read William’s lines yourself. Point to the left gray bar at “76 percent,” the left orange bar at “97 percent,” and the middle orange bar at “597.”

**William says**

> We started with a filter trained on texts from 2012. It caught about 76 percent of 1,080 scams reported from 2022 to 2024. We retrained it on newer scams, and on that same test it got to about 97 percent. Then we gave it 600 genuine texts from one inbox. It flagged 597. That person would have seen a warning on almost every genuine text we tested.

**Kartikeya does** · Point to the left blue bar at “96 percent.” Then point to the middle blue bar at “427.”

**William says**

> So we gave the filter genuine modern texts to learn from, too. It still caught about 96 percent of the scams. And the false alarms came down from 597 to 427. That’s 170 fewer interruptions in one inbox. It’s also still a 71 percent false-alarm rate in that test. Both numbers matter if someone is going to rely on the warnings.

## 2:15–2:45 | Thank the judges

**Kartikeya does** · Leave the chart on screen. Stop sharing after the closing thank you.

**William says**

> We saw a real gap between the datasets, and they were collected differently. We can’t say how much of it came from time. Next I’d test more inboxes with permission, then put the checker in front of older adults. I’d give them a message and ask what they’d do next. That’s the test I want Scam Drift to pass. Thank you.

**If you lose your place** · Old filter 76%. Retrained 97% and 597 false alarms. With genuine training texts, 96% and 427 false alarms. Both false-alarm counts are out of 600 genuine texts from one inbox.

## When the judges start Q&A

- If the organizers allow live assistance, keep Zoom playback and the panel on the same headphones. Leave the panel paused while other teams present.
- When the host hands your team over to the judges, click **Start Q&A now** before their first question. If it misses a question, ask the judge to repeat it or type it and click **Ask**.
- Give one direct answer and one supporting number or limitation. If asked about the fine-tuned model in the current demo, say it was added after submission and evaluated separately.