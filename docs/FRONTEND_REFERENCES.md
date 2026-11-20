# Scam Drift front-end references

## Initial scanner redesign

- **One visual owns the first screen.** The scanner opens beside the checker entry point. The visitor can see an incoming message stream before scrolling. The three chapter controls change the same scene and its measured readout. Each chapter’s text explains its comparison.
- **The scan beam is rendered in Three.js.** A local shader moves one beam across the filter plane. Instanced meshes draw the message forms and markings. The scroll clock determines the message positions, outcomes and pile size. Idle motion does not advance the measured test.
- **The layout uses a scanner palette and two legible type roles.** Dark petrol frames the motion. Pale green-grey supports reading. Vermilion identifies the main action and the warning marks. Barlow Condensed handles headings and readouts. Atkinson Hyperlegible Next handles instructions and controls.
- **Keyboard and static views retain the data.** The filter controls are links to the chapter headings. The scanner is hidden for reduced motion. The comparison stays in the HTML, including labels and sample sizes.

## Sources applied

| Source | Technique supported by the source | Scam Drift decision |
|---|---|---|
| [MotionSites scroll-animation lesson](https://www.motionsites.ai/lesson/build-3d-scroll-animated-website-with-ai) and [the live Three.js lesson](https://motionsites.ai/lesson/astra-6-build-3d-websites-for-beginners) | Let one visual anchor the first screen. Derive the live scene and camera from a visual sequence. The gallery shell itself showed video elements and one canvas in the capture. | Use a visible scene immediately. Let progress reveal the real test rather than use a stock background clip. |
| [21st Sticky Scroll Reveal](https://mcp.21st.dev/@manuarora700/components/sticky-scroll-reveal) and [21st Scroll Gallery](https://docs.21st.dev/@soralabs/components/scroll-gallery) | Hold the specimen in place while the reading position changes. Use a constrained wipe for chapter handoffs. | Pin the same scanner and use a local crop between chapters. Add three accessible stage links. |
| [MONOGRID](https://monogrid.com/) and [Terminal Industries](https://terminal-industries.com/) | REA observed canvas, media, Lenis hooks and sticky and clip-path markers. The terminal case shows a visual state change that explains the system. | Keep one mounted scene and make the change in filter behavior visible through message trajectories and the pile. |
| [Lusion’s Oryzo case](https://lusion.co/projects/oryzo_ai/) and [Ponpon Mania](https://ponpon-mania.com/) | A persistent graphic carries the transition through the page. The Oryzo capture contained canvases and native video elements. | Keep the gate and silhouettes stable while color, position and the readout change. |
| [Igloo Inc](https://www.igloo.inc/) | REA observed a separately named `App3D` script. The selected headless window did not expose a canvas element. | Keep the explanation available independently of 3D initialization. |
| [Three.js dynamic instancing](https://threejs.org/examples/webgl_instancing_dynamic.html), [scatter example](https://threejs.org/examples/webgl_instancing_scatter.html) and [ShaderMaterial](https://threejs.org/docs/pages/ShaderMaterial.html) | Change repeated transforms in buffers and drive a material through uniforms. | Render the message field in a handful of draw calls. Animate the beam with uniforms and avoid a fullscreen glow pass. |

## REA capture method

REA ran in temporary Chrome profiles against the public page URLs. The survey used a 1365 × 800 CSS-pixel viewport and attempted 47 targets, including the 38 references in the original list and nine follow-ups. It captured the DOM on 46 targets. Nineteen controlled Page Down actions completed. Fifteen of those showed a changed DOM digest across the observation window. Animation, hydration and loading can also change the digest.

The counts below cover elements observed in one DOM snapshot. A canvas can be 2D, WebGL or another renderer. A CSS or framework marker can exist without driving the visible effect. A zero count means the element did not appear in that window. Network retention was bounded. All public captures used empty temporary profiles. The table links to the live source and includes the REA evidence identifier where available.

| Reference | Observed | Canvas / video | DOM markers | Page Down | Evidence ID |
|---|---:|---:|---|---|---|
| [Igloo Inc](https://www.igloo.inc/) | 200 | 0 / 0 | — | DOM stable | `ev_96e41d3b9227ef9f434b61b9d8fef1fa0cff6981503aa02316501f81d478be3e` |
| [The Notturno Experience](https://santionispirits.com/) | 200 | 1 / 0 | sticky, clip-path | DOM changed | `ev_e2b0902e840eaf431008d1f68f95613811dabe1d67b8daa49fb3f676ff1c7de2` |
| [Oryzo AI](https://oryzo.ai/) | 200 | 6 / 2 | — | DOM changed | `ev_fe2aabe059b809b0b0204e578fce4243bb286dd2b9f70cccb4d389ccbd1a36f8` |
| [Ponpon Mania](https://ponpon-mania.com/) | 200 | 1 / 0 | — | DOM changed | `ev_6a37b740211bc9d82fd0ed87e2809527101952b680ee2f26220f1e50b1d9b6e8` |
| [Lando Norris](https://landonorris.com/) | 200 | 21 / 0 | Lenis hook, clip-path | — | `ev_289f00097b5ea507da4daaa123850d17341e9e2f452202423e876c36989faec9` |
| [Hatom](https://www.hatom.com/) | 200 | 2 / 1 | Lenis hook, clip-path | — | `ev_9b80b3397ea044d271a0ea4ac81646758fc2389527c51e96c313e85130c7d8a9` |
| [Immersive Garden](https://immersive-g.com/) | 200 | 6 / 0 | Lenis hook | — | `ev_06c037324c0a145fb62b40779253d743e417f1583e4000af6b66a6e537a7c74d` |
| [Shopify Renaissance Edition](https://www.shopify.com/editions/winter2026) | 200 | 1 / 12 | Lenis hook, sticky | — | `ev_4b77a54468b566f4c80dd7187f02f96a3e75f970c3302deb6178648b6ca3b60a` |
| [Why Zero](https://why.zero.university/) | 200 | 1 / 2 | — | — | `ev_6a6e4b59731ce2a09c577d32fa35d324e726a88ae55f8b2ecda97fee1c00f4cb` |
| [Heron AI](https://heronaiapp.com/) | 200 | 0 / 0 | Lenis hook, clip-path | — | `ev_5183e6b856d90383dcba53de70bb5479c4742795aa056cce23e8db6c00dd94de` |
| [The Watch](https://thewatch.60fps.fr/) | 200 | 1 / 0 | Lenis hook | — | `ev_4440882e77825f1e9957fa2c077916b3c2e584b9ea44b5e10154b966022f08ef` |
| [Aevion / LiDAR Drone Scanning](https://drone.riotters.com/) | 200 | 7 / 3 | Lenis hook, clip-path, Next.js | — | `ev_af58a54be55d87993dd1c934de64b0fcd74be53bcebf7b7c979b442882c049b1` |
| [Léo Parpeix Portfolio](https://www.leoparpeix.com/) | 200 | 0 / 1 | Lenis hook | — | `ev_9eb01ed629ae7024e98e5a8214b36233c125eebcdb689bdf2864c1f40eae3dbc` |
| [illoca](https://illoca.unseen.co/) | 200 | 1 / 0 | Lenis hook, clip-path | — | `ev_8f2624c7290031dd2de5aad7b56b08733bb03ffb70be243922a8b1812e5eada6` |
| [EverSwap](https://everswap.com/) | 200 | 6 / 0 | — | — | `ev_49584a1bcf75fa76b6c8fe12b428db812402b8ea1507b33fbcecfc669994668a` |
| [Of the Oak](https://oftheoak.co.uk/) | 200 | 1 / 1 | clip-path | — | `ev_fc016e5c15851cb3e6785e3a4b3aa6b9690929fb2e84fcf305cd371a4724f4e3` |
| [Montfort](https://mont-fort.com/) | 200 | 2 / 0 | Lenis hook | — | `ev_ca2fea1a4fac64cae7480083c64e6e54c0053402f0473d9bf51c3a31eaa0ee82` |
| [Cartier Watches & Wonders 2025](https://cartier-waw-0225.dev.60fps.fr/) | 200 | 0 / 0 | — | — | `ev_758a1b72711dc7ba2ef5b7fb2641030a01df1775ab3daa0f35dd85b31e651d5d` |
| [GQ & Audemars Piguet The Extraordinary Lab](https://www.gq.com/sponsored/story/the-extraordinary-lab) | 200 | 1 / 0 | Lenis hook, clip-path | — | `ev_1fdada702a01c2184aa896179b72f42d4080efb901e574b6f76a448d6fdb034b` |
| [David Whyte Experience](https://davidwhyte.com/experience/) | 200 | 2 / 2 | Lenis hook, clip-path | — | `ev_eff8032a656b1834b9fea1a24f3d31efff2722456e201f9f2675f5a86d4e40eb` |
| [Aramco The Birth of Oil](https://www.aramco.com/en/about-us/our-history/the-birth-of-oil) | Unavailable | — | — | — | — |
| [Floema](https://floema.com/en) | 200 | 0 / 0 | sticky, clip-path | — | `ev_c19f446df3937549606d7877d6652cc3f015a0a1f079676a6de02e10ceb8f255` |
| [Vectr](https://www.vectrfl.com/) | 200 | 1 / 0 | Lenis hook | — | `ev_9f3916471775f057e72c2e74ba5a2786f9e4482827390f5af20469b41d340c38` |
| [Indigo Laboratory](https://indigo-laboratory.it/) | 200 | 0 / 1 | Lenis hook, sticky, clip-path | — | `ev_03591983f8f7ba9dcd9d0dacdd9dfd0352265024ef677b9623db907729de5cd8` |
| [Slosh Seltzer](https://sloshseltzer.com/) | 200 | 0 / 0 | clip-path | — | `ev_6b285b282675e9a5e027367a96c938551b48e8aea1278a8fec4bc77e554630bb` |
| [MONOGRID](https://monogrid.com/) | 200 | 1 / 1 | Lenis hook, sticky, clip-path | DOM changed | `ev_e67f7688b1280d47574c75ddba1cec1cd70246acc34d8a375d8935556c2760b0` |
| [Agrumea Farm](https://www.agrumeafarm.it/en) | 200 | 10 / 0 | clip-path | DOM changed | `ev_773edb5651a2040756eee9a778b18c1e2137bfdfce04c94e2ff635e35a23bb6d` |
| [Damn Good Brands](https://damngoodbrands.com/) | 200 | 0 / 2 | clip-path | DOM changed | `ev_da558bd4a13837a4a3d4c77a0209fc605d4e7dfb2bbed0d46c48a2454af8556b` |
| [David Estrada](https://david-estrada.dev/) | 200 | 14 / 0 | — | DOM changed | `ev_2323b63f43accaf8f1f3a8922cd1866bf7d1b8f30a337cb3ab9c07b78aaab308` |
| [Terminal Industries](https://terminal-industries.com/) | 200 | 1 / 4 | Lenis hook, sticky, clip-path | DOM changed | `ev_28787163462a2f3a585b0c579df2d87f9ff17190b1e6f604124ed881a2498c95` |
| [Zentry](https://zentry.com/) | 200 | 1 / 6 | — | — | `ev_a55fef3587632d54f7e31b582f98737fdc9758de761a836b74382f42a3f11cdb` |
| [Inkfish](https://inkfishnyc.com/) | 200 | 1 / 12 | Lenis hook, Next.js | — | `ev_360492553ef2af5bcf51711929e0560a82fdc4f2e63f16d58cffd68ba262ffff` |
| [iPhone Air](https://www.apple.com/iphone-air/) | 200 | 0 / 16 | sticky | DOM changed | `ev_d7e3e0ac36d81550ed62c0bdcc1698ddd9a01cffb7222a68e4c0616684ad5f3a` |
| [iPhone 18 Pro](https://www.apple.com/iphone-18-pro/) | 200 | 0 / 14 | — | — | `ev_7933b9e1020eaee6fa0d1ba6d86bd6605a2f383a2cf4678528c6689152a14fd9` |
| [Stripe Sessions 2026](https://stripe.com/sessions/2026) | 200 | 1 / 0 | sticky | — | `ev_12173e6c11c743ae29860d545ed03ad67a9c708a95a48c53711dffc3e6a47bcb` |
| [Linear](https://linear.app/) | 200 | 0 / 0 | clip-path | DOM changed | `ev_146f9b20f86aba85921fea1999578e3f7f2bb31cfb5ccbdbf399b2a2b471ef18` |
| [Vercel Ship 2025](https://vercel.com/ship/2025) | 200 | 0 / 0 | Next.js | DOM changed | `ev_992111a9a5d6d4b75c48fd92b368c82f0c268426ac33792a216cf6bff8454be3` |
| [MotionSites Academy architecture demo](https://soft-zoom-63098134.figma.site/) | 200 | 0 / 0 | — | DOM stable | `ev_ada29415cb29abcc81122db4ce8b69dbeacf3157ccbc9da6d45c79fec1af96ee` |
| [MotionSites Gallery](https://motionsites.ai/) | 200 | 1 / 24 | — | — | `ev_247396ab0203d8e52031b9926a83b98a192ee6a2e130095c3a1f629e0528ab9c` |
| [MotionSites Three.js lesson](https://motionsites.ai/lesson/astra-6-build-3d-websites-for-beginners) | 200 | 0 / 0 | — | — | `ev_c66d2251b82c4671b624b12159fa222b089efd745b3314118428a03a53a553a2` |
| [21st Scroll components](https://21st.dev/community/components/explore/scroll-animation-component) | 200 | 0 / 0 | Next.js | DOM changed | `ev_7086c9824d5c97b48b1239a9e7dda67f5740841b8b7814dc8e9cedac7b2a3814` |
| [21st Scroll Gallery](https://docs.21st.dev/@soralabs/components/scroll-gallery) | 200 | 0 / 0 | sticky, Next.js | DOM changed | `ev_40ebb40920fb7c9e835f048ada0b336713f7c1b3a76a3e48a0bb0910e3f57e9a` |
| [21st Sticky Scroll Reveal](https://mcp.21st.dev/@manuarora700/components/sticky-scroll-reveal) | 200 | 0 / 0 | sticky, Next.js | DOM changed | `ev_90297854f665fe774db7ddd58a35675abf51d8f074b2507de42c7c9add3c5470` |
| [Three.js Instancing Dynamic](https://threejs.org/examples/webgl_instancing_dynamic.html) | 200 | 1 / 0 | — | DOM stable | `ev_969401b6addaec1a0384933a67ded2b5a15a1c63036141283829a4693be99c54` |
| [Three.js Particle Sprites](https://threejs.org/examples/webgl_points_sprites.html) | 200 | 4 / 0 | — | — | `ev_55b2b1826c54ce56657d5930a95f376f9f0c5a832048472051360172c68acc8b` |
| [Three.js Instancing Scatter](https://threejs.org/examples/webgl_instancing_scatter.html) | 200 | 4 / 0 | — | DOM stable | `ev_0aa00b35847939467a28065879024c3da5a5c01ae1034acb467b3bb573ec8637` |
| [Trionn](https://trionn.com/) | 200 | 1 / 6 | Lenis hook, clip-path, Next.js | DOM changed | `ev_ba287a66296cbbfba90931395ae2c2b091be0081fe412eb006be5e1b3d80ec5e` |

## Focused bundle analysis

REA also parsed JavaScript from selected targets through a local browser debugging connection. Fingerprints are inferences about code present in a bundle. They do not prove a dependency drove a specific animation. MotionSites and 21st have usable page evidence above. Their separate bundle passes did not complete.

| Target | Parsed / observed scripts | Reported fingerprints | Evidence ID |
|---|---:|---|---|
| [Igloo Inc](https://www.igloo.inc/) | 2 / 2 | Generic route registration API (medium) | `ev_cda9e305adb13aee244d11effb3d27f6d98307998d54164b1b4cb6011ec029a6` |
| [Oryzo AI](https://oryzo.ai/) | 1 / 1 | No named vendor fingerprint | `ev_e2fe6fb17877ac380a23fb1b4f98e0d22c0b03879368a229498b296ad0394fe2` |
| [MONOGRID](https://monogrid.com/) | 57 / 57 | Vite (medium), Vue (medium), Generic route registration API (medium) | `ev_32c8485a1f70d10418ed01b738ddd53902888d438a2173f45058e3a69f36bd3c` |
| [Terminal Industries](https://terminal-industries.com/) | 43 / 43 | Vite (medium), Vue (medium), Generic route registration API (medium) | `ev_84f3a534c1c73a337733a7d31867ccb5315486b9ac2ab9a99e0d7ea89efef526` |
| [MotionSites](https://motionsites.ai/) | — | CLI bundle analysis did not complete | — |
| [21st](https://21st.dev/community/components/explore/scroll-animation-component) | — | CLI bundle analysis did not complete | — |
| [Three.js Instancing Dynamic](https://threejs.org/examples/webgl_instancing_dynamic.html) | 5 / 5 | No named vendor fingerprint | `ev_1f2e1e1b881217ef93f92fde59c09aa325c2bdc36628e748fb1f1f54259c715b` |

## Local implementation checks

Headless Chrome checks covered 320, 375, 390, 768, 1280, 1440 and 1920 CSS pixels. The canvas appeared within the first screen. The checks covered chapter links by mouse and keyboard, reverse scrolling, the mobile experiment link, the checker deep link, the three static test frames and the checker with WebGL unavailable. Axe found no violations in the tested desktop flow.

With DPR capped at 1.5, the active browser verification reported 5 draw calls and 28,578 triangles. A short software-WebGL scroll sample rendered about 53 scene frames per second at 1440px and 59 at 390px. Presentation-device frame rate is unknown.

Final local Lighthouse scores were desktop 100 performance and 100 accessibility, and mobile 98 performance and 100 accessibility. Reserving the canvas frame before WebGL loaded reduced measured layout shift to 0 on desktop and 0.001 on mobile. These are local lab measurements.

## Ignos follow-up

[Ignos](https://ignos.earth/) places cool pale text and compact mono readouts over a dark 3D scene. Chrome showed a single viewport-sized canvas. A series of scroll captures showed the camera moving from a wide view of the duct to a close view of the flame. Labels stayed tied to scene features. Computed styles showed Inter Tight for display text and Host Grotesk for secondary headings. The REA Page Down scenario completed with evidence `ev_1d482efba55b01613051741b284a279e497705cd37b5cf62f05dc08b6e6be31c`.

Scam Drift uses a separate inspection gantry with lit rails, a lavender scan plane and projected HTML labels. The chapter cameras reframe the message stream and the false-alarm pile. Cool violet slate frames the scanner. Coral identifies flagged scam bubbles. Mint identifies legitimate messages. Manrope takes the display role. Atkinson Hyperlegible Next remains the reading type. The scanner button pauses idle motion while preserving user-controlled scrolling.

## Section redesign

The experiment now uses an ink-dark stage with Fraunces display type. The results move onto a pale-blue comparison strip with monospace figures and sample counts. The checker uses a warm surface and Atkinson Hyperlegible Next. The live scene shows the current rate. The results strip shows every rate together. Static and reduced-motion views retain the inline readings.

The recovery guide is part of the checker interface. It offers separate paths for a link opened, credentials shared, and money sent. The response stays in the browser. The guidance is based on the [U.S. FTC recovery resource](https://consumer.ftc.gov/articles/what-do-if-you-were-scammed).

## Full-width layout

Space Grotesk replaces Fraunces in the display roles. A single headline sits above the 3D scene. The sticky scene shows the active chapter caption next to its API-driven rate. The comparison strip reveals bars for the measured rates. The checker starts with its own centered heading and a single-column form. The three static chapter frames remain available with reduced motion or without WebGL.

The [UI and onboarding audit](UI_ONBOARDING_AUDIT.md) records the reflow, history, and hierarchy issues found in this layout. The [component references](FRONTEND_COMPONENT_REFERENCES.md) map the prior REA survey to proposed changes and identify reference pages that have changed since capture.

## Oryzo motion follow-up

REA captured [Oryzo](https://oryzo.ai/) after the opening settled and after two Page Down actions. The captures show the cork object on a cutting mat, isolated against a dark background, then tilted to show its edge. The replay records the views and actions. It does not isolate scroll from timed object rotation. Evidence `ev_da30695b0e521556735576a1b573c2afd6c645e1b4bd02766230e8e253831f21`. [Lusion’s case study](https://lusion.co/projects/oryzo_ai/)

Scam Drift keeps the same scanner geometry as the last chapter moves into an overhead diagram. It uses the same scroll position to move the camera, flatten the messages, blend the outline, and select the caption and rate. The rate changes between the API’s measured values at each narrative beat.
