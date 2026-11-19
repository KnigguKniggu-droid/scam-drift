# Scam Drift UI v3: structured implementation plan (post-deadline, Nov 18)

Branch: `post-deadline`. `main` (the judged entry, 01abbc9) never changes. Guard: skill `frontend-ship-guard` on every step (baseline -> change -> compare -> real-browser check).

## 0. Goal and constraints
- Users: older, often non-native-speaking adults, and the family member who helps them. Job: decide in 10 seconds whether to pay, tap or reply.
- Two surfaces with different rules:
  1. **Checker** (the tool): calm, large, zero decorative motion, WCAG 2.2 AA, works at 320 px, keyboard and screen reader.
  2. **Story page** (for judges, finals, portfolio): the research story with scroll-driven motion, one 3D hero, charts. Rich motion is allowed here, with a reduced-motion version.
- Honesty rules stay: numbers only from results/*.json, synthetic examples labelled, "never says safe", prototype disclaimer.

## 1. Architecture change (why Gradio is the ceiling)
Gradio controls the DOM, fonts and layout. Real design work (custom type scale, motion, smooth scroll, 3D) needs our own front end.
- Back end: `server.py` (FastAPI) exposes `POST /api/check` -> calls the existing `src/triage.py` + `app.predict` logic (no model changes). Serves `web/`.
- Front end: `web/index.html` (story + checker), `web/styles.css`, `web/app.js`. No build step; libraries pinned from a CDN: Lenis 1.x (smooth scroll), Motion One or GSAP ScrollTrigger (scroll animation), three.js r16x (one hero scene), Chart.js or plain SVG for the result charts.
- Keep `app.py` (Gradio) working as a fallback demo for the finals (runbook unchanged).

## 2. Design skills to apply (research, Nov 18)
| Skill | Source | What we use from it | Status |
|---|---|---|---|
| UI UX Pro Max | github.com/nextlevelbuilder/ui-ux-pro-max-skill (MIT) | style + palette + font-pair search, 99 UX guidelines, pre-ship checklist | install needs user OK |
| Impeccable | github.com/pbakaus/impeccable (Apache-2.0) | /critique, /audit, /polish, /animate, deterministic anti-pattern detectors ("AI slop" checks) | install needs user OK |
| Emil Kowalski skills | github.com/emilkowalski/skills | emil-design-eng review, animate, review-animations: ease-out not ease-in, 150-300 ms UI motion, no animation on high-frequency actions, interruptible springs | install needs user OK |
| Local: frontend-ship-guard | ~/.claude/skills | baseline/compare gate | in use |
| Local: design plugins (design-superpowers, design-council, design-drift, design-steward, design-system-by-blue, design-with-blocks, design-is-code, design-dev-bridge, design-skills, figma) | ~/.claude/scripts/design-plugins.py | design-system tokens, critique council, drift checks | switched ON; need /reload-plugins |
| Local: dataviz, artifact-design | skills | chart colour formula, accessible charts | available |

## 3. Design system (tokens first)
- Type: one humanist sans with large x-height (e.g. "Atkinson Hyperlegible Next" for the checker, designed for low-vision readers; pair with a display serif for story headings). Base 20 px, scale 1.25.
- Colour: neutral ink #111 on #F6F7F9; verdict colours RED #B93333 (5.9:1), AMBER #E07A1F with ink (6.3:1), GREEN label #2E8B57 on large text only; one accent blue #1F4FD1. Dark mode for the story page only.
- Spacing 4/8 grid, radius 12-16, focus ring 4 px accent.
- Motion tokens (Emil): enter 220 ms cubic-bezier(.23,1,.32,1); exit 160 ms; verdict reveal = opacity + 8 px rise, once; no motion on typing, button presses only a 0.97 scale.

## 4. Checker v3 (priority 1)
1. Paste box with "Paste from clipboard" button and character count; Enter submits.
2. Verdict card: icon + plain label + headline + "What to do now" (keep current copy), large, announced by aria-live.
3. "Why" with highlighted words *inside the original message* (mark the trigger words in place), not only chips.
4. One-tap "Read aloud" (Web Speech API, browser built-in, no data leaves the device) for low-vision users.
5. Language note when the text is not English (we know raw non-English recall is low; say "Ask family" instead of a confident GREEN).
6. Examples as cards with REAL / SYNTHETIC tags and source line.
7. Privacy line: "Nothing is stored; the text is checked on this computer."

## 5. Story page (priority 2, for finals)
1. Hero: one three.js scene: a phone with incoming message bubbles drifting from "2012" (grey SMS) to "2024" (modern bank/delivery texts); scroll scrubs the year. Reduced-motion: static illustration.
2. Scroll sections (Lenis + ScrollTrigger), each with one number from results/*.json: 76% caught -> naive fix 97% but 99.5% false alarms -> real legit texts 71% -> what ships.
3. Lead chart animated on enter (bars grow once, 600 ms ease-out), accessible table fallback.
4. Embedded checker section (same component).
5. Honesty section: limits, synthetic labels, data sources, "prototype, not financial advice".

## 6. Execution phases (agent swarm, each phase gated by frontend-ship-guard)
| Phase | Work | Agents | Gate |
|---|---|---|---|
| A | Install approved skills; /reload-plugins; run UI UX Pro Max search for "fintech safety tool, older users" and Impeccable /critique on the current app | 1 | user OK for installs |
| B | server.py + web/ checker v3 (section 4) | 1 builder | API parity test: same tiers as app.predict on 4 examples + 50 random IMC/benign texts |
| C | Story page (section 5) | 1 builder (parallel with B after the API exists) | Lighthouse a11y >= 95, no horizontal scroll 320/390/1440, reduced-motion check, 3D frame count increasing |
| D | Reviews: Impeccable /audit + /polish, Emil review-animations, design-council critique, AI-chat mock users (ChatGPT/Gemini/Claude tabs) | 2-3 critics | all critical findings fixed |
| E | Real-browser click-through in the user's Chrome; screenshots; commit on post-deadline | main worker | step-3 table of frontend-ship-guard passes |

## 7. Risks
- Motion and 3D can hurt older users: keep them out of the checker; honour prefers-reduced-motion.
- Third-party skills are unvetted code: read SKILL.md and scripts before use; install only with the user's OK.
- Never push or change main; finals demo uses the submitted behaviour unless the user decides otherwise.
