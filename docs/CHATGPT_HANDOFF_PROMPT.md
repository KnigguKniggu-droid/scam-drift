Model: GPT-6.2 Sol. Reasoning effort: High (not Max). Keep usage low: no filler, no repeated drafts, batch your searches, stop when the deliverables below are done.

# Context (full dump)
I am a high-school student. My AI hackathon project "Scam Drift" (Veritas AI International High School Hackathon 2026, AI + Finance track) was submitted on time and shortlisted for an award (ceremony Nov 21). The judged version is frozen; I am now improving a separate post-deadline version for the finals demo and my portfolio.

What the project does: a scam-text checker for older, often non-native-speaking adults. Paste a text -> RED / YELLOW / GREEN warning, "what to do now" money-safety steps, and the words that triggered it. Research finding (all numbers measured): a filter trained on 2012 SMS spam catches 76% of real 2022-24 scam reports; retraining on modern scams raises that to 96.6% but flags 99.5% of a real person's legitimate texts; adding real legitimate modern texts cuts false alarms to 71% at 95.9% recall. A hand-written safety layer adds luring/grooming warnings. Never says "safe"; prototype, not financial advice.

Public repo (judged version): https://github.com/KnigguKniggu-droid/scam-drift
Current front end (post-deadline, local only): FastAPI server + plain HTML/CSS/JS (no build step). Libraries already loaded from CDNs: GSAP + ScrollTrigger, Lenis, three.js. API: POST /api/check, GET /api/examples, GET /api/story (all numbers come from this API; never hard-code numbers).

The problem: the site looks like generic "AI slop": dark navy, Lexend font, pill badges, mostly static text blocks, and a scroll effect that is just a jumping year counter. I want it to feel like the best live 3D scroll-story sites.

The concept we chose ("The inbox flood"): a three.js scene where hundreds of message bubbles (InstancedMesh) stream through a glowing filter plane as you scroll from 2012 to 2024. Caught bubbles turn red and fall away, missed ones pass through, and the ratios come from the real numbers. Chapter 2: the retrained filter also catches the legitimate (green) bubbles and they pile up (alert fatigue made visible). Chapter 3: real legitimate texts shrink the pile. The final chapter is a calm "Try it yourself" checker for older users. Visual system: paper #F2EFE8, ink #111, one signal red #C8321F; editorial serif display (e.g. Instrument Serif) + a clean UI sans (e.g. Inter Tight or Geist); masked line reveals; Lenis lerp 0.08; ScrollTrigger scrub 1; pinned chapters with clip-path transitions; one horizontal strip for the four findings; prefers-reduced-motion = static frames.

# Your tasks
1. Research (use web search): find 30-45 LIVE sites (2024-2026) with excellent smooth scrolling, real-time 3D/WebGL rendering, scroll-driven storytelling and non-generic typography and colour. Include Awwwards / FWA Site of the Day winners, motionsites.ai examples, and studios such as Lusion, Active Theory, igloo.inc, plus Apple product pages, Stripe, Linear, Vercel. For each: name, URL, and ONE concrete technique worth copying (with how it is likely built). Also ask Gemini (if you can reach it in this app) for its own list and merge the results, marking which came from where.
2. Find anti-"AI slop" design guidance (typography, colour, layout tells to avoid) and list the 15 most useful rules.
3. List up to 50 of the best open-source UI / animation / front-end skills and libraries (Claude Code or Codex skills such as Impeccable, UI UX Pro Max, Emil Kowalski's skills; GSAP plugins, Lenis, Theatre.js, React Three Fiber / drei, Motion, OGL), each with URL, licence and what it is best at. Mark the 10 you would actually use for this project.
4. Give a concrete build spec for "The inbox flood" in plain three.js + GSAP + Lenis (no build step): scene setup, InstancedMesh bubble system driven by scroll progress, shader or material for the glowing filter, chapter timeline with ScrollTrigger, typography reveals, reduced-motion fallback, performance budget (60 fps, DPR cap 1.5). Include code skeletons I can paste.

# Output format
One Markdown document: (A) site table, (B) anti-slop rules, (C) skills/libraries table + top 10, (D) build spec with code skeletons. No intro, no conclusion paragraph.
