# Scam Drift UI and onboarding audit

## Objective

Help someone with a suspicious text reach a clear next action. Give the research story a separate path with a 3D scene that explains why the filters behave differently. This audit covers the local post-deadline preview.

The “After” column specifies proposed changes. See the [component references](FRONTEND_COMPONENT_REFERENCES.md) for the reference-to-implementation map.

## Findings

| Priority | Before | After | Why |
| --- | --- | --- | --- |
| P1 · Resize and reflow | At 320 px with 200% root text, the page grew to 483 px wide. The clipboard button measured 393 px, the title overflowed its box by 22 px, and part of the unfocused skip link entered the viewport. | Stack the field label and clipboard button when they cannot fit. Allow button text to wrap. Clip the skip link visually until focus and loosen the title measure. | A user who enlarges text must still be able to read and operate the page. |
| P1 · Chapter history | After advancing to chapter 3, browser Back restored `#retrained-filter` while the canvas remained on chapter 3. | Route chapter clicks, initial hashes, `popstate`, and external hash changes through one chapter seek function. Derive the visual state and `aria-current` from that position. | The URL, chapter selection, and visible evidence must agree. |
| P1 · First useful action | On a 390 × 844 phone the header or hero shortcut reached the checker in one tap. On arrival the sample button extended to y=991 px and the privacy note to y=848 px. Scrolling the story to the input took 4.52 viewport heights. | Put paste and one labeled working sample together at the entrance to the checker. Put the instruction to remove private details above the field. Offer the experiment as its own action. | Visitors can act with their own text or learn from a sample before committing to the story. |
| P1 · Result handoff | In the settled phone sample result, the warning headline began at y=462 px and the first action at y=661 px. Check, Clear, and the privacy note occupied the upper half. | Place the warning and first action at the top of the result view. Move focus to a result heading for an explicit sample check and provide an obvious way to edit the text. Keep safety text readable during transitions. | The first screen after a check should answer “What do I do now?” |
| P1 · Live story semantics | The live canvas, rate, and legend are hidden from assistive technology. CSS removes the corresponding static chapter rates. The later findings list still exposes those rates. | Keep a short, accessible summary and equivalent numbers in each chapter. Announce explicit chapter changes once. | A chapter link should expose its result in place. |
| P2 · Composition | The 163 px desktop headline sits above the canvas, but the first caption begins at y=1051 px at 1440 × 900. In the scene, the gantry fills the frame while the messages are small. On the phone the incoming stream is clipped at the left edge. | Use a large readable message as the opening subject. Reveal the gate as that message reaches it. Use a wider shot for through-versus-caught and a tray close-up for false alarms. Put a short caption beside the decisive action. | The object and its outcome should explain the chapter before the visitor studies the controls. |
| P2 · Motion continuity | The stage crop reaches 48% per side at a handoff. The caption switches separately. Settled idle rendering measured 23 frames over 1.2 seconds with six draw calls and 28,818 triangles. | Carry the gate and one message across the cut. Match camera target and scale before blending to the next pose. Let reversal resume from the displayed pose. Test idle and scroll rendering separately. | A near-total wipe hides the relationship between the two views. A fast reversal should remain visually intelligible. |
| P2 · Interpretation and touch | The phone rate label is 9.6 px. Chapter links are 11.52 px with 44 px height and adjacent edges. The legend is 11.68 px and depends on matching swatches to particles. | Use 14–16 px labels and 44 px controls with breathing room. Label caught and through destinations and give them different shapes or paths. | People must read what the percentage measures and tell the outcomes apart on a small screen. |

Both independent Impeccable assessments identified the same hierarchy problem. The detector reported `border-accent-on-rounded`, `cream-palette`, and `dark-glow`. The checker combines a 3 px accent border with a 2 px corner. The cream flag is a visual judgment. The flagged glow comes from the CSS scene-label leader. Preserve local lighting on the physical gate. [Impeccable critique](https://impeccable.style/docs/critique/) · [Impeccable audit](https://impeccable.style/docs/audit/) · [Detector](https://impeccable.style/docs/detector/)

## Typography and layout specification

| Role | Typeface and target | Placement |
| --- | --- | --- |
| Landing headline | Space Grotesk 650–700. 76–104 px desktop and 40–50 px phone at default text size. `line-height: .98–1.05`, tracking near `-.03em`. | Left-align “Check a suspicious text” with the explanation and primary action. Allow the line to wrap when text grows. |
| Scene title | Space Grotesk 600–650. 36–60 px desktop and 28–36 px phone. `line-height: 1.02`, tracking `-.025em`. | Place the current takeaway in a safe area of the visual. Use the same anchor across all three scenes. |
| Form, warning and actions | Atkinson Hyperlegible Next 18–20 px with `line-height: 1.5`. Use 600–700 for labels and 28–36 px for the result heading. Keep body tracking near zero. | Use one left-aligned reading column. Use a maximum line length near `48ch` on multi-sentence instructions. |
| Rates and interpretation | Tabular numerals at 32–52 px. Use Atkinson Hyperlegible Next 14–16 px with `line-height: 1.35` for labels. Reserve monospace for short values or sample counts. | Keep each rate adjacent to its full denominator label. Display the count below it. |

Use `rem`-based size limits and flexible containers so the hierarchy survives enlarged text. Use high-contrast off-white and graphite for the tool. Use charcoal metal and a localized filter light in the scene. Reserve warning color for outcomes. [Apple typography](https://developer.apple.com/design/human-interface-guidelines/typography) · [The Details of UI Typography](https://developer.apple.com/videos/play/wwdc2020/10175/) · [Braille Institute font](https://www.brailleinstitute.org/freefont/) · [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)

## Verification

- Chrome measured 1440 × 900, 390 × 844, and 320 × 640. The normal-size layouts fit those widths. The enlarged-root test was a browser simulation. The 390 px result returned zero automated axe findings. Keyboard Skip focused the text box. An empty submit focused the box and supplied a prompt. An injected 503 displayed a retry message and retained the test text.
- REA replayed the 390 px checker entrance and one published sample. It recorded one `POST /api/check`, a High risk result in the accessibility tree, and no page errors. Evidence `ev_8f1d2eba4233ae7923b858d6057e98d7287c32284433d92ce591d313755dde83`. The REA MCP transport closed, so the installed REA CLI ran the replay.
- The design fixes should pass Back and Forward, keyboard and touch, 200% text enlargement, all three outcome captions, and equivalent static content with reduced motion. Target 60 fps during active scrub and cap DPR at 1.5. Real-device frame rate and first-use comprehension with older adults are unknown.

[Apple onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding) · [Emil Kowalski Design Engineering](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md) · [Emil Kowalski Apple Design](https://github.com/emilkowalski/skills/blob/main/skills/apple-design/SKILL.md)
