/* Story page (post-deadline v3, Nov 18).
   - Numbers: every number comes from GET /api/story (results/*.json, read by server.py). Nothing is typed in here.
   - Hero: one three.js scene (r160, pinned). Scroll moves the phone from 2012 prize texts to 2024 bank/parcel texts.
   - Motion: Lenis smooth wheel scroll (story only: off while the checker is on screen) + GSAP ScrollTrigger scrub for
     the hero year only. Data (waffles, numbers, chart values) is always shown at its true value; no scroll-scrubbed data.
   - Rendering: on demand (one frame per progress change), no idle loop.
   - Reduced motion (also when switched on mid-session): no Lenis, no scrub, one still render.
   - No WebGL: the static SVG in the story markup (index.html; web/story.html is the same fragment) stays.
   Debug: window.storyState() returns the live state (mode, frames, progress, lenis, scrub, chart). */
(() => {
  'use strict';

  const root = document.querySelector('[data-st-root]');
  if (!root || root.dataset.stReady) return;
  root.dataset.stReady = '1';

  const REDUCE_MQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  let REDUCE = REDUCE_MQ.matches;
  const LIBS = {
    gsap: { src: 'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js',
      integrity: 'sha384-g4NTh/Iv5PPU4xPyhEWqPcwtNXOvdaDI8LLnyYfyNZOjKJeYQyjzQ9X5275eBjpt', global: 'gsap' },
    scrollTrigger: { src: 'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js',
      integrity: 'sha384-Z3REaz79l2IaAZqJsSABtTbhjgOUYyV3p90XNnAPCSHg3EMTz1fouunq9WZRtj3d', global: 'ScrollTrigger' },
    lenis: { src: 'https://cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js',
      integrity: 'sha384-B2WBjDzEjJpYvhmi2UyEn7rektqkf5suS6sNoyyrf0EBAwBHdkiXxIlU0V5Ru2ed', global: 'Lenis' },
  };
  const THREE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js';
  const STILL_PROGRESS = 0.55; // reduced motion: one frame that shows both eras

  const state = {
    mode: 'loading', reason: '', frames: 0, progress: 0, lenis: false, scrub: false,
    numbers: 'loading', missing: [], chart: 'idle', reducedMotion: REDUCE, notes: [],
  };
  window.storyState = () => JSON.parse(JSON.stringify(state));

  const $ = (sel, el = root) => el.querySelector(sel);
  const $$ = (sel, el = root) => Array.from(el.querySelectorAll(sel));
  const clamp01 = (v) => Math.min(1, Math.max(0, v));
  const smooth = (a, b, v) => { const t = clamp01((v - a) / (b - a)); return t * t * (3 - 2 * t); };
  const lerp = (a, b, t) => a + (b - a) * t;

  function setMode(mode, reason) {
    state.mode = mode;
    state.reason = reason || '';
    root.dataset.stMode = mode;
  }

  function loadScript(lib) {
    if (window[lib.global]) return Promise.resolve(window[lib.global]);
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = lib.src;
      s.integrity = lib.integrity;
      s.crossOrigin = 'anonymous';
      s.referrerPolicy = 'no-referrer';
      s.onload = () => (window[lib.global] ? resolve(window[lib.global]) : reject(new Error('missing ' + lib.global)));
      s.onerror = () => reject(new Error('could not load ' + lib.src));
      document.head.appendChild(s);
    });
  }

  /* ------------------------------------------------------------------ numbers */
  const fmtPct = (v) => {
    if (typeof v !== 'number' || !isFinite(v)) return null;
    if (v >= 0.9995 && v <= 1) return '100%';
    return (Math.round(v * 1000) / 10).toFixed(1) + '%';
  };
  const fmtInt = (n) => (typeof n === 'number' ? n.toLocaleString('en-GB') : '');
  let NUM = {};
  const val = (id) => (NUM[id] && typeof NUM[id].value === 'number' ? NUM[id].value : null);

  function sourceLine(item) {
    if (!item || typeof item.value !== 'number') return 'Not available: this number is missing from the results files.';
    const parts = [];
    if (typeof item.k === 'number' && typeof item.n === 'number') parts.push(`${fmtInt(item.k)} of ${fmtInt(item.n)}`);
    if (Array.isArray(item.ci95) && item.ci95.length === 2) parts.push(`95% CI ${fmtPct(item.ci95[0])} to ${fmtPct(item.ci95[1])}`);
    parts.push(item.source);
    return 'Source: ' + parts.join(' · ');
  }

  function fillNumbers(data) {
    NUM = (data && data.numbers) || {};
    state.missing = (data && Array.isArray(data.missing)) ? data.missing.slice() : Object.keys(NUM);
    $$('[data-st-num]').forEach((el) => { el.textContent = fmtPct(val(el.dataset.stNum)) || 'UNKNOWN'; });
    $$('[data-st-inline]').forEach((el) => { el.textContent = fmtPct(val(el.dataset.stInline)) || 'UNKNOWN'; });
    $$('[data-st-src]').forEach((el) => { el.textContent = sourceLine(NUM[el.dataset.stSrc]); });
    $$('[data-st-n]').forEach((el) => { el.textContent = fmtInt(NUM[el.dataset.stN] && NUM[el.dataset.stN].n); });
    $$('[data-st-oneinx]').forEach((el) => {
      const v = val(el.dataset.stOneinx);
      el.textContent = v && v > 0 ? ` (about 1 in ${Math.round(1 / v)})` : '';
    });
    $$('[data-st-needs]').forEach((el) => {
      el.hidden = el.dataset.stNeeds.split(/\s+/).some((id) => val(id) === null);
    });
    const note = $('[data-st-splitnote]');
    if (note) note.hidden = !(NUM.y2012_fa_real_legit && NUM.y2012_fa_real_legit.n && NUM.ships_fa_real_legit && NUM.ships_fa_real_legit.n);
    const disc = $('[data-st-disclaimer]');
    if (disc && data && typeof data.disclaimer === 'string' && data.disclaimer.trim()) disc.textContent = data.disclaimer.trim();
    buildWaffles();
    buildTable();
    drawChart();
  }

  async function loadNumbers() {
    const status = $('[data-st-status]');
    try {
      const res = await fetch('/api/story', { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      fillNumbers(data);
      state.numbers = 'ok';
    } catch (err) {
      state.numbers = 'failed';
      state.notes.push('numbers: ' + err.message);
      fillNumbers(null);
      if (status) {
        status.hidden = false;
        status.textContent = 'The numbers could not be loaded. Start the app with "python server.py" and reload this page.';
      }
    }
  }

  /* ------------------------------------------------------------------ waffles */
  function buildWaffles() {
    $$('[data-st-waffle]').forEach((el) => {
      if (!el.children.length) {
        const frag = document.createDocumentFragment();
        for (let i = 0; i < 100; i += 1) frag.appendChild(document.createElement('i'));
        el.appendChild(frag);
      }
      const v = val(el.dataset.stWaffle);
      el.dataset.target = v === null ? '0' : String(Math.round(v * 200) / 2); // nearest half percent
      paintWaffle(el, 1); // data is never scrubbed: the squares always match the printed number
    });
  }

  function paintWaffle(el, frac) {
    el.dataset.frac = String(frac);
    const shown = Number(el.dataset.target || 0) * clamp01(frac);
    const full = Math.floor(shown);
    const half = shown - full >= 0.5;
    const cells = el.children;
    for (let i = 0; i < cells.length; i += 1) {
      const on = i < full;
      const isHalf = !on && half && i === full;
      if (cells[i].classList.contains('on') !== on) cells[i].classList.toggle('on', on);
      if (cells[i].classList.contains('half') !== isHalf) cells[i].classList.toggle('half', isHalf);
    }
  }

  /* ------------------------------------------------------------------ chart + table */
  const ROWS = [
    { name: '2012 filter', note: 'trained on 2012 texts only', scam: 'y2012_late_recall', legit: 'y2012_fa_real_legit' },
    { name: 'Retrained on new scams', note: 'the naive fix', scam: 'naive_fix_late_recall', legit: 'naive_fix_fa_real_legit' },
    { name: '+ real legitimate texts', note: 'added to training', scam: 'real_ham_fix_late_recall', legit: 'real_ham_fix_fa_real_legit' },
    { name: 'Shipped checker', note: 'High risk or Be careful', scam: 'ships_warned_scams_2022_24', legit: 'ships_fa_real_legit' },
  ];
  const chartWrap = $('[data-st-chart]');
  const chartSection = $('.st-chart');
  let chartW = 0;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  function drawChart() {
    if (!chartWrap) return;
    const w = Math.max(280, Math.round(chartWrap.clientWidth || 600));
    chartW = w;
    const narrow = w < 520;
    const valueW = 62;
    const plotW = w - valueW;
    const labelH = 26;
    const barH = narrow ? 18 : 22;
    const barGap = 6;
    const rowGap = narrow ? 26 : 32;
    const rowH = labelH + barH * 2 + barGap + rowGap;
    const top = 4;
    const axisH = 26;
    const h = top + ROWS.length * rowH + axisH;
    const font = 'font-family="Source Sans 3, Source Sans Pro, Segoe UI, system-ui, sans-serif"';
    let svg = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-labelledby="st-chart-svg-t" aria-describedby="st-chart-cap" ${font}>`;
    svg += `<title id="st-chart-svg-t">${esc(chartSummary())}</title>`;
    svg += '<defs><pattern id="st-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      + '<rect width="2" height="6" fill="#0F172A" fill-opacity="0.22"/></pattern></defs>';
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      const x = Math.round(t * plotW) + 0.5;
      svg += `<line x1="${x}" y1="${top}" x2="${x}" y2="${h - axisH + 4}" stroke="#E2E8F0" stroke-width="1"/>`;
      if (!narrow || t === 0 || t === 0.5 || t === 1) {
        const anchor = t === 0 ? 'start' : t === 1 ? 'end' : 'middle';
        svg += `<text x="${x}" y="${h - 6}" font-size="16" fill="#475569" text-anchor="${anchor}">${Math.round(t * 100)}%</text>`;
      }
    });
    ROWS.forEach((r, i) => {
      const y = top + i * rowH;
      svg += `<text x="0" y="${y + 18}" font-size="17" font-weight="600" fill="#0F172A">${esc(r.name)}`
        + (narrow ? '' : `<tspan font-weight="400" fill="#475569" dx="8">${esc(r.note)}</tspan>`) + '</text>';
      [['scam', '#1F4FD1'], ['legit', '#E07A1F']].forEach(([kind, color], j) => {
        const v = val(r[kind]);
        const by = y + labelH + j * (barH + barGap);
        if (v === null) {
          svg += `<text x="0" y="${by + barH * 0.72}" font-size="16" fill="#475569">not available</text>`;
          return;
        }
        const bw = Math.max(2, v * plotW);
        svg += `<g class="bar"><rect x="0" y="${by}" width="${bw.toFixed(1)}" height="${barH}" rx="3" fill="${color}"/>`
          + (kind === 'legit' ? `<rect x="0" y="${by}" width="${bw.toFixed(1)}" height="${barH}" rx="3" fill="url(#st-hatch)"/>` : '')
          + '</g>';
        svg += `<text class="val" x="${(bw + 8).toFixed(1)}" y="${by + barH * 0.74}" font-size="16" font-weight="600" fill="#0F172A">${fmtPct(v)}</text>`;
      });
    });
    svg += '</svg>';
    chartWrap.innerHTML = svg;
  }

  function chartSummary() {
    const bits = ROWS.map((r) => {
      const a = fmtPct(val(r.scam));
      const b = fmtPct(val(r.legit));
      return `${r.name}: ${a || 'not available'} of real 2022-24 scams warned, ${b || 'not available'} of real legitimate texts warned`;
    });
    return 'Bar chart. ' + bits.join('. ') + '.';
  }

  function buildTable() {
    const body = $('[data-st-table]');
    if (!body) return;
    const cell = (id) => {
      const it = NUM[id];
      if (!it || typeof it.value !== 'number') return '<td>not available</td>';
      const kn = typeof it.k === 'number' ? `${fmtInt(it.k)} of ${fmtInt(it.n)}` : '';
      return `<td>${fmtPct(it.value)}<small>${esc(kn)}</small></td>`;
    };
    const src = (r) => [r.scam, r.legit].map((id) => (NUM[id] ? `${NUM[id].source} → ${NUM[id].key}` : id))
      .map((s) => `<small>${esc(s)}</small>`).join('');
    body.innerHTML = ROWS.map((r) => `<tr><th scope="row">${esc(r.name)}<small>${esc(r.note)}</small></th>${cell(r.scam)}${cell(r.legit)}<td>${src(r)}</td></tr>`).join('');
  }

  function initChartMotion() {
    if (!chartSection) return;
    if (REDUCE || state.numbers !== 'ok') { state.chart = 'static'; return; }
    // Already on screen (or above it): no growth, the bars are simply there.
    if ((chartWrap || chartSection).getBoundingClientRect().top < window.innerHeight * 0.85) { state.chart = 'static'; return; }
    chartSection.classList.add('is-armed');
    state.chart = 'armed';
    // Grow once when the chart's top passes 85% of the viewport. A position check (not an intersection ratio)
    // also catches jumps past the chart (anchor links, End key), so the bars can never stay hidden.
    let ticking = false;
    const check = () => {
      ticking = false;
      const el = chartWrap || chartSection;
      if (el.getBoundingClientRect().top < window.innerHeight * 0.85) {
        window.removeEventListener('scroll', onScroll);
        window.removeEventListener('resize', onScroll);
        // next frame, so the scaleX(0) state is painted before the transition starts
        requestAnimationFrame(() => { chartSection.classList.add('is-in'); state.chart = 'in'; });
      }
    };
    const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(check); } };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    onScroll();
  }

  if (chartWrap && 'ResizeObserver' in window) {
    new ResizeObserver(() => {
      const w = Math.round(chartWrap.clientWidth);
      if (Math.abs(w - chartW) > 4) drawChart();
    }).observe(chartWrap);
  }

  /* ------------------------------------------------------------------ hero (three.js) */
  const hero = $('[data-st-hero]');
  const yearEl = $('[data-st-year]');
  const eraEl = $('[data-st-era]');
  let heroApi = null; // set when the 3D scene is live
  let requestHeroRender = () => {};

  function setProgress(p) {
    const v = clamp01(p);
    state.progress = Math.round(v * 1000) / 1000;
    const year = Math.round(2012 + v * 12);
    if (yearEl && yearEl.textContent !== String(year)) yearEl.textContent = String(year);
    const era = v < 0.38 ? 'Prize texts' : v < 0.72 ? 'Parcel fees' : 'Bank alerts and “Hi Mum”';
    if (eraEl && eraEl.textContent !== era) eraEl.textContent = era;
    if (heroApi) { heroApi.setProgress(v); requestHeroRender(); }
  }

  function hasWebGL() {
    try {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl2') || c.getContext('webgl');
      if (!gl) return false;
      const lose = gl.getExtension('WEBGL_lose_context');
      if (lose) lose.loseContext();
      return true;
    } catch (e) {
      return false;
    }
  }

  // Illustrative messages, written for this page (synthetic). Tokens [link] and [phone] stand in for real ones.
  const OLD_MSGS = [
    'FREE MSG: U have WON a cash prize! Txt CLAIM to 8xxxx now 2 collect. T&Cs apply',
    'Ur mobile no. was selected 4 a FREE ringtone! Reply YES 2 get it now',
    'Congrats! U r a winner of a FREE holiday. Call 09xxx now',
  ];
  const NEW_MSGS = [
    'Your parcel is on hold. Pay the small redelivery fee today: [link]',
    'Bank alert: a new payee was added to your account. Not you? Call [phone] now.',
    'Hi Mum, I dropped my phone. This is my new number. Can you help me with a payment?',
    'Your account will be suspended today. Confirm your details here: [link]',
  ];
  // Shorter lines for the floating 3D cards (same synthetic illustrations)
  const CARD_TEXT = [
    'WINNER! U have won a cash prize. Txt CLAIM now',
    'FREE ringtone! Reply YES 2 get it',
    'Parcel on hold. Pay the fee: [link]',
    'Bank alert: new payee added. Call [phone]',
  ];
  const FONT_UI = '"Source Sans 3", "Segoe UI", system-ui, sans-serif';
  const FONT_OLD = 'ui-monospace, "Cascadia Mono", Consolas, "Courier New", monospace';

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function wrapWords(ctx, text, maxW) {
    const words = text.split(' ');
    const lines = [];
    let line = [];
    words.forEach((w) => {
      const test = line.concat(w).join(' ');
      if (ctx.measureText(test).width > maxW && line.length) { lines.push(line); line = [w]; } else line.push(w);
    });
    if (line.length) lines.push(line);
    return lines;
  }

  function drawWords(ctx, lines, x, y, lh, ink, tokenInk) {
    lines.forEach((words, li) => {
      let cx = x;
      words.forEach((w, wi) => {
        const isToken = /^\[(link|phone)\][.,]?$/.test(w);
        ctx.fillStyle = isToken ? tokenInk : ink;
        const txt = wi < words.length - 1 ? w + ' ' : w;
        ctx.fillText(txt, cx, y + li * lh);
        cx += ctx.measureText(txt).width;
      });
    });
  }

  // Bubble card texture for the floating 3D messages
  function bubbleCanvas(text, era) {
    const c = document.createElement('canvas');
    c.width = 640;
    let ctx = c.getContext('2d');
    const old = era === 0;
    const font = old ? `600 40px ${FONT_OLD}` : `600 44px ${FONT_UI}`;
    const lh = old ? 50 : 54;
    ctx.font = font;
    const lines = wrapWords(ctx, text, c.width - 88).slice(0, 3);
    const h = 56 + lines.length * lh;
    c.height = h + 8; // resizing resets the context state
    ctx = c.getContext('2d');
    ctx.font = font;
    roundRect(ctx, 4, 4, c.width - 8, h, 36);
    ctx.fillStyle = old ? '#D6DBE3' : '#FFFFFF';
    ctx.fill();
    if (!old) { ctx.strokeStyle = '#CBD5E1'; ctx.lineWidth = 3; ctx.stroke(); }
    ctx.textBaseline = 'top';
    drawWords(ctx, lines, 44, 30, lh, old ? '#334155' : '#0F172A', '#1F4FD1');
    return { canvas: c, aspect: c.width / c.height };
  }

  function buildScene(THREE, host) {
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(26, 1, 0.1, 100);
    camera.position.set(0, 0, 18);

    scene.add(new THREE.HemisphereLight(0xdbe4ff, 0x0b1222, 1.25));
    const key = new THREE.DirectionalLight(0xffffff, 2.4); key.position.set(5, 7, 9); scene.add(key);
    const rim = new THREE.DirectionalLight(0x7c9cff, 2.2); rim.position.set(-7, 3, -6); scene.add(rim);

    const shapeRR = (w, h, r) => {
      const s = new THREE.Shape();
      const x = -w / 2; const y = -h / 2;
      s.moveTo(x + r, y);
      s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
      s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
      s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
      return s;
    };
    const fitUV = (geo, w, h) => {
      const pos = geo.attributes.position; const uv = geo.attributes.uv;
      for (let i = 0; i < pos.count; i += 1) uv.setXY(i, (pos.getX(i) + w / 2) / w, (pos.getY(i) + h / 2) / h);
      uv.needsUpdate = true;
    };

    const phone = new THREE.Group();
    scene.add(phone);
    const W = 3.3; const H = 6.7; const R = 0.55; const D = 0.34;
    const bodyGeo = new THREE.ExtrudeGeometry(shapeRR(W, H, R), {
      depth: D, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.07, bevelSegments: 5, curveSegments: 16,
    });
    bodyGeo.translate(0, 0, -D / 2);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x1b2436, metalness: 0.6, roughness: 0.32 });
    phone.add(new THREE.Mesh(bodyGeo, bodyMat));

    const SW = W - 0.26; const SH = H - 0.26;
    const scrGeo = new THREE.ShapeGeometry(shapeRR(SW, SH, R - 0.13), 16);
    fitUV(scrGeo, SW, SH);
    const scr = document.createElement('canvas');
    scr.width = 640; scr.height = Math.round(640 * SH / SW);
    const sctx = scr.getContext('2d');
    const scrTex = new THREE.CanvasTexture(scr);
    scrTex.colorSpace = THREE.SRGBColorSpace;
    scrTex.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
    const scrMat = new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false });
    const screen = new THREE.Mesh(scrGeo, scrMat);
    screen.position.z = D / 2 + 0.081;
    phone.add(screen);

    // soft floor shadow
    const sh = document.createElement('canvas'); sh.width = 256; sh.height = 64;
    const shx = sh.getContext('2d');
    const g = shx.createRadialGradient(128, 32, 4, 128, 32, 120);
    g.addColorStop(0, 'rgba(0,0,0,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    shx.fillStyle = g; shx.fillRect(0, 0, 256, 64);
    const shadowTex = new THREE.CanvasTexture(sh);
    const shadowMat = new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false, toneMapped: false });
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 1.3), shadowMat);
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.set(0, -H / 2 - 0.7, 0);
    scene.add(shadow);

    // floating message cards: two from 2012 drift away, two from 2024 drift in
    const CARD_SPECS = [
      { text: CARD_TEXT[0], era: 0, from: [-2.85, 2.55, 1.9], to: [-3.1, 5.2, 1.0], rot: 0.18 },
      { text: CARD_TEXT[1], era: 0, from: [2.6, -0.9, 1.5], to: [3.0, 3.9, 0.6], rot: -0.16 },
      { text: CARD_TEXT[2], era: 1, from: [2.7, -5.6, 1.2], to: [2.15, 1.25, 2.0], rot: -0.16 },
      { text: CARD_TEXT[3], era: 1, from: [-2.7, -6.2, 1.0], to: [-2.2, -1.9, 1.8], rot: 0.16 },
    ];
    const cards = CARD_SPECS.map((spec) => {
      const { canvas, aspect } = bubbleCanvas(spec.text, spec.era);
      const tex = new THREE.CanvasTexture(canvas);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
      const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false, opacity: 0 });
      const width = 3.0;
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, width / aspect), mat);
      mesh.rotation.y = spec.rot;
      mesh.renderOrder = 2;
      scene.add(mesh);
      return { spec, mesh, mat, tex, canvas };
    });

    // ----- screen drawing
    function layoutMessages(ctx) {
      const pad = 34; const maxW = scr.width * 0.76; const items = [];
      const push = (text, era, appear) => {
        ctx.font = era === 0 ? `500 29px ${FONT_OLD}` : `500 31px ${FONT_UI}`;
        const lines = wrapWords(ctx, text, maxW - 2 * 26);
        const lh = era === 0 ? 38 : 40;
        const bw = Math.min(maxW, Math.max(...lines.map((l) => ctx.measureText(l.join(' ')).width)) + 2 * 26);
        items.push({ kind: 'msg', text, era, lines, lh, w: bw, h: lines.length * lh + 2 * 20, appear });
      };
      items.push({ kind: 'sep', label: '2012', h: 60, appear: null });
      OLD_MSGS.forEach((t) => push(t, 0, null));
      // 2024 messages arrive one by one as the year moves on (like a real chat, newest at the bottom)
      const at = [0.18, 0.4, 0.6, 0.78];
      items.push({ kind: 'sep', label: '2024', h: 60, appear: at[0] });
      NEW_MSGS.forEach((t, i) => push(t, 1, at[i]));
      return { items, pad, gap: 22 };
    }
    let layout = null;
    let lastDrawn = -1;
    let fontsReady = false;

    function drawScreen(p) {
      const ctx = sctx; const w = scr.width; const h = scr.height;
      if (!layout) layout = layoutMessages(ctx);
      const modern = smooth(0.3, 0.75, p);
      // background drifts from 2012 grey to a modern light screen
      const c0 = [222, 226, 232]; const c1 = [248, 250, 252];
      const bg = c0.map((c, i) => Math.round(lerp(c, c1[i], modern)));
      ctx.fillStyle = `rgb(${bg.join(',')})`;
      ctx.fillRect(0, 0, w, h);
      // status bar + notch
      ctx.fillStyle = '#0F172A';
      roundRect(ctx, w / 2 - 78, 22, 156, 36, 18); ctx.fill();
      ctx.font = `600 26px ${FONT_UI}`; ctx.textBaseline = 'middle';
      ctx.fillText('9:41', 44, 40);
      // header
      const headY = 82;
      ctx.fillStyle = 'rgba(15,23,42,0.06)'; ctx.fillRect(0, headY + 92, w, 2);
      ctx.fillStyle = '#1E3A8A';
      ctx.beginPath(); ctx.arc(76, headY + 46, 30, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#FFFFFF'; ctx.font = `600 26px ${FONT_UI}`; ctx.textAlign = 'center';
      ctx.fillText('?', 76, headY + 47);
      ctx.textAlign = 'left'; ctx.fillStyle = '#0F172A'; ctx.font = `600 30px ${FONT_UI}`;
      ctx.fillText('Unknown sender', 124, headY + 34);
      ctx.fillStyle = '#475569'; ctx.font = `400 24px ${FONT_UI}`;
      ctx.fillText('Text message', 124, headY + 66);

      // conversation: 2024 messages arrive with progress; the list sticks to the bottom once it overflows
      const top = headY + 110; const viewH = h - top - 40;
      const shown = layout.items.map((it) => ({ it, a: it.appear === null ? 1 : smooth(it.appear, it.appear + 0.1, p) }));
      let total = 0;
      shown.forEach((s) => { s.y = total; total += (s.it.h + layout.gap) * s.a; });
      const offset = Math.max(0, total - viewH);
      ctx.save();
      ctx.beginPath(); ctx.rect(0, top, w, h - top); ctx.clip();
      ctx.textBaseline = 'top';
      shown.forEach(({ it, a, y: yy }) => {
        if (a <= 0.001) return;
        const y = top + 16 + yy - offset + (1 - a) * 28;
        if (y + it.h < top - 10 || y > h) return;
        ctx.globalAlpha = a;
        if (it.kind === 'sep') {
          ctx.font = `600 24px ${FONT_UI}`;
          const tw = ctx.measureText(it.label).width + 36;
          ctx.fillStyle = 'rgba(15,23,42,0.08)';
          roundRect(ctx, (w - tw) / 2, y + 12, tw, 38, 19); ctx.fill();
          ctx.fillStyle = '#334155'; ctx.textAlign = 'center';
          ctx.fillText(it.label, w / 2, y + 19);
          ctx.textAlign = 'left';
          ctx.globalAlpha = 1;
          return;
        }
        const old = it.era === 0;
        if (old) ctx.globalAlpha = 1 - 0.45 * smooth(0.45, 1, p);
        roundRect(ctx, layout.pad, y, it.w, it.h, 26);
        ctx.fillStyle = old ? '#C9D0DA' : '#FFFFFF';
        ctx.fill();
        if (!old) { ctx.strokeStyle = '#CBD5E1'; ctx.lineWidth = 2; ctx.stroke(); }
        ctx.font = old ? `500 29px ${FONT_OLD}` : `500 31px ${FONT_UI}`;
        drawWords(ctx, it.lines, layout.pad + 26, y + 20, it.lh, old ? '#334155' : '#0F172A', '#1F4FD1');
        ctx.globalAlpha = 1;
      });
      ctx.restore();
      scrTex.needsUpdate = true;
      lastDrawn = p;
    }

    // ----- camera fit
    let aspect = 1;
    function resize() {
      const w = Math.max(1, host.clientWidth); const h = Math.max(1, host.clientHeight);
      renderer.setSize(w, h, false);
      aspect = w / h;
      camera.aspect = aspect;
      const vFov = (camera.fov * Math.PI) / 180;
      const needH = 8.9; const needW = aspect < 0.95 ? 6.6 : 8.8; // narrow canvases: cards tuck in closer
      const distH = needH / 2 / Math.tan(vFov / 2);
      const distW = needW / 2 / (Math.tan(vFov / 2) * aspect);
      camera.position.z = Math.max(distH, distW);
      camera.updateProjectionMatrix();
    }

    // One smoothing layer only (Lenis on the wheel); the scene follows the scroll progress directly.
    let progress = 0;
    function update() {
      const p = progress;
      phone.rotation.y = lerp(-0.42, 0.3, p);
      phone.rotation.x = lerp(0.1, 0.02, p);
      phone.rotation.z = 0;
      phone.position.y = 0;
      shadow.material.opacity = 0.9;
      const narrowK = aspect < 0.95 ? 0.7 : 1;
      cards.forEach((c) => {
        const s = c.spec;
        const k = s.era === 0 ? smooth(0.05, 0.6, p) : smooth(0.35, 0.92, p);
        c.mesh.position.set(lerp(s.from[0], s.to[0], k) * narrowK, lerp(s.from[1], s.to[1], k), lerp(s.from[2], s.to[2], k));
        // Opaque while they cross the phone; fade only at the far end of the path (no half-transparent bubble on the screen)
        c.mat.opacity = s.era === 0 ? 1 - smooth(0.6, 1, k) : smooth(0, 0.3, k);
        // The still frame (reduced motion) shows no half-faded bubbles at all
        c.mesh.visible = REDUCE ? c.mat.opacity >= 0.99 : c.mat.opacity > 0.01;
        c.mesh.scale.setScalar(narrowK);
      });
      // Redraw the 640 px screen texture only in steps of 1/150 of the scroll (saves a texture upload per frame)
      const q = Math.round(p * 150) / 150;
      if (q !== lastDrawn || (fontsReady && lastDrawn < 0)) drawScreen(q);
    }

    function render() {
      update();
      renderer.render(scene, camera);
      state.frames += 1;
    }

    resize();
    drawScreen(0);

    return {
      renderer, render, resize,
      setProgress(p) { progress = p; },
      jump(p) { progress = p; },
      redrawText() { layout = null; fontsReady = true; lastDrawn = -1; drawScreen(progress); },
      dispose() {
        renderer.dispose();
        [bodyGeo, scrGeo].forEach((x) => x.dispose());
        [scrTex, shadowTex].concat(cards.map((c) => c.tex)).forEach((x) => x.dispose());
      },
    };
  }

  async function initHero() {
    const host = $('[data-st-canvas]');
    if (!host) return;
    if (!hasWebGL()) { setMode('static', 'no-webgl'); return; }
    let THREE;
    try {
      THREE = await import(THREE_URL);
    } catch (e) {
      setMode('static', 'three.js could not load');
      return;
    }
    let api;
    try {
      api = buildScene(THREE, host);
    } catch (e) {
      setMode('static', 'webgl init failed: ' + e.message);
      return;
    }
    heroApi = api;
    const canvas = api.renderer.domElement;
    let raf = 0; let lost = false;
    // On demand: one frame per change of scroll progress, size or fonts. Nothing renders while the page is still.
    requestHeroRender = () => {
      if (raf || lost) return;
      raf = requestAnimationFrame(() => { raf = 0; api.render(); });
    };

    canvas.addEventListener('webglcontextlost', (e) => {
      e.preventDefault(); lost = true; cancelAnimationFrame(raf); setMode('static', 'webgl context lost');
    });

    if (REDUCE) {
      goStillHero();
    } else {
      api.jump(state.progress);
      api.render();
      setMode('webgl', '');
    }

    if ('ResizeObserver' in window) {
      new ResizeObserver(() => { api.resize(); requestHeroRender(); }).observe(host);
    }
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => { api.redrawText(); requestHeroRender(); });
    }
  }

  function goStillHero() {
    if (!heroApi) return;
    heroApi.jump(STILL_PROGRESS);
    setProgress(STILL_PROGRESS);
    heroApi.render();
    setMode('still', 'prefers-reduced-motion: one render, no animation');
  }

  /* ------------------------------------------------------------------ scroll motion */
  function nativeHeroProgress() {
    // Fallback when GSAP cannot load: read the hero position on scroll (passive, one update per frame).
    let ticking = false;
    const read = () => {
      ticking = false;
      if (!hero) return;
      const r = hero.getBoundingClientRect();
      const span = Math.max(1, r.height - window.innerHeight);
      setProgress(-r.top / span);
    };
    window.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(read); } }, { passive: true });
    read();
  }

  let lenisRef = null;
  async function initMotion() {
    if (REDUCE) return;
    let gsap; let ScrollTrigger;
    try {
      gsap = await loadScript(LIBS.gsap);
      ScrollTrigger = await loadScript(LIBS.scrollTrigger);
      gsap.registerPlugin(ScrollTrigger);
    } catch (e) {
      state.notes.push('gsap: ' + e.message);
      nativeHeroProgress();
      return;
    }

    try {
      const Lenis = await loadScript(LIBS.lenis);
      if (REDUCE) return;
      const lenis = new Lenis({
        lerp: 0.12,
        smoothWheel: true,
        syncTouch: false, // touch keeps the phone's own native scrolling
        prevent: (node) => !!(node && node.closest && node.closest('#check, textarea, select, [data-lenis-prevent]')),
      });
      lenis.on('scroll', ScrollTrigger.update);
      const tick = (time) => lenis.raf(time * 1000);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);
      lenisRef = { lenis, tick };
      state.lenis = true;
      window.storyLenis = lenis;
      // The checker gets plain native scrolling (no inertia while a verdict is read): smooth wheel is on only
      // while no part of #check is on screen. Lenis reads options.smoothWheel on every wheel event.
      const checker = document.getElementById('check');
      if (checker && 'IntersectionObserver' in window) {
        new IntersectionObserver((entries) => {
          const onScreen = entries[0].isIntersecting;
          lenis.options.smoothWheel = !onScreen;
          state.lenisWheel = !onScreen;
        }).observe(checker);
      }
      // The "Scroll" hint is a plain anchor: an instant jump, no long programmatic scroll.
    } catch (e) {
      state.notes.push('lenis: ' + e.message);
    }

    if (REDUCE) return;
    // Hero: scroll scrubs the year 2012 -> 2024 (the stage is CSS position: sticky, no pin needed).
    // scrub: true (no extra lag): Lenis already smooths the wheel, so this is the only follow layer.
    const proxy = { p: 0 };
    gsap.to(proxy, {
      p: 1,
      ease: 'none',
      onUpdate: () => setProgress(proxy.p),
      scrollTrigger: {
        trigger: hero,
        start: 'top top',
        end: () => (hero && hero.offsetHeight > window.innerHeight * 1.2 ? 'bottom bottom' : 'bottom top'),
        scrub: true,
        invalidateOnRefresh: true,
      },
    });

    state.scrub = true;
    window.storyMotionOff = () => {
      ScrollTrigger.getAll().forEach((t) => t.kill());
      if (lenisRef) { gsap.ticker.remove(lenisRef.tick); lenisRef.lenis.destroy(); lenisRef = null; window.storyLenis = null; }
      state.lenis = false;
      state.scrub = false;
    };

    const refresh = () => ScrollTrigger.refresh();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(refresh);
    window.addEventListener('load', refresh, { once: true });
    window.storyRefresh = refresh;
  }

  // Reduced motion switched on during the visit: stop smooth scroll and scrub, show the still hero and a static chart.
  const onReduceChange = () => {
    if (!REDUCE_MQ.matches || REDUCE) return;
    REDUCE = true;
    state.reducedMotion = true;
    if (window.storyMotionOff) window.storyMotionOff();
    if (chartSection) { chartSection.classList.remove('is-armed'); chartSection.classList.add('is-in'); state.chart = 'static'; }
    goStillHero();
  };
  if (REDUCE_MQ.addEventListener) REDUCE_MQ.addEventListener('change', onReduceChange);

  /* ------------------------------------------------------------------ start */
  setProgress(REDUCE ? STILL_PROGRESS : 0);
  buildWaffles();
  drawChart();
  const numbersDone = loadNumbers();
  numbersDone.then(initChartMotion);
  initHero();
  initMotion().then(() => numbersDone).then(() => {
    if (window.storyRefresh) window.storyRefresh();
    // The checker sits above the story: a verdict, an error or a long message changes its height, which moves the
    // hero. Re-measure the scroll triggers when that happens (debounced to one refresh per change).
    const checker = document.getElementById('check');
    if (checker && window.storyRefresh && 'ResizeObserver' in window) {
      let lastH = checker.offsetHeight; let t = 0;
      new ResizeObserver(() => {
        const h = checker.offsetHeight;
        if (h === lastH) return;
        lastH = h;
        clearTimeout(t);
        t = setTimeout(() => { if (window.storyRefresh && !REDUCE) window.storyRefresh(); }, 120);
      }).observe(checker);
    }
  });
})();
