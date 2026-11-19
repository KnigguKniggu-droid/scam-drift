# Design brief v4: from "AI SaaS page" to one strong scroll story (Nov 18)

## What is wrong now (user review, agreed)
- Dark navy + Lexend + pill badges = the generic "AI-made SaaS" look.
- Most sections are static text blocks; the scroll effect is a counter that jumps (2012 -> 2021) instead of motion that tells the story.
- No single visual idea carries the page.

## References to study before building (open each live, scroll slowly, note one technique each)
1. apple.com product pages (e.g. iPhone): pinned sections, scroll-scrubbed canvas/video, giant type that scales on scroll.
2. stripe.com: interactive WebGL globe/gradients, precise easing, restrained colour.
3. linear.app: crisp typography, subtle light sweeps, motion only where it explains.
4. lusion.co / igloo.inc (Awwwards SOTD-style WebGL): one 3D concept, physical motion, depth.
5. Awwwards SOTD 2026 "scrollytelling" winners filtered by 3D/WebGL + scroll (studio kogel, evensix, monogrid inspirations): GSAP + three.js scrubbed scenes.
Trend note: 2026 SOTD winners favour ONE strong visual concept over many effects (svilenkovic.com/3d/awwwards-2026-3d, opinion).

## The one concept: "The inbox flood"
A WebGL scene (three.js InstancedMesh, ~600 message bubbles) streams down a phone-shaped funnel. A glowing horizontal "filter" plane sits in the middle.
- Scroll = time (2012 -> 2024). Bubble shapes/colours morph from 2012 SMS style to modern bank/delivery cards.
- Caught bubbles turn red and drop away; missed ones pass through. The RATIOS come from results/*.json via /api/story: 2012 filter catches 76% of 2022-24 scams (24% pass through).
- Chapter 2: "retrain" - the filter glows stronger, catches 97%, but now green "real legit" bubbles also get caught (99.5%) and pile up: alert fatigue made visible.
- Chapter 3: real legit texts added - pile shrinks to 71%. Honest end: still not solved.
- Data-driven motion = honest and memorable (judges see the numbers move).

## Visual system
- Paper background #F2EFE8, ink #111, one signal red #C8321F, muted grey #8A8680. No navy, no gradients, no pills.
- Type: editorial pair, e.g. "Instrument Serif" (display, huge, tight leading) + "Inter Tight" or "Geist" (UI). Headlines reveal with a line mask (overflow hidden + yPercent 100 -> 0, 0.9 s, ease "expo.out"), once.
- Grid: 12 columns, generous whitespace, numbers set huge (clamp 6-14 rem) with a counter that eases, not jumps.

## Motion rules (Emil Kowalski skills + Apple)
- Lenis lerp 0.08; ScrollTrigger scrub: 1 (smoothed), never scrub: true on text.
- Pinned chapters with clip-path circle/inset transitions between them; one horizontal-scroll strip for the four findings.
- Micro: magnetic primary button (max 6 px), verdict card enters with 220 ms ease-out rise, press scale .97.
- prefers-reduced-motion: static frames per chapter, no Lenis, no scrub. DPR cap 1.5, pause the scene off-screen.

## Checker
Keep it calm (older users) but restyle in the same paper/ink system; it becomes the final chapter: "Try it yourself".

## Done when
- Each chapter has visible, data-driven motion; no static text-only section above the checker.
- 60 fps on a mid laptop (Chrome performance panel), Lighthouse a11y >= 95, no horizontal scroll at 320.
- Impeccable critique finds no "AI slop" tells (generic fonts, purple/navy gradients, pill badges, emoji icons).
