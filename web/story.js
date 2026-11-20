// Historical test results drive this scene. The checker is loaded separately.
const root = document.querySelector('#story');
const track = root.querySelector('.flood-track');
const stage = root.querySelector('.flood-stage');
const viewport = root.querySelector('.flood-viewport');
const cover = root.querySelector('.study-intro');
const chapters = [...root.querySelectorAll('[data-chapter]')];
const status = root.querySelector('#flood-status');
const stageRate = stage.querySelector('[data-hero-rate]');
const stageLabel = stage.querySelector('[data-stage-label]');
const stageStep = stage.querySelector('[data-stage-step]');
const stageCaption = stage.querySelector('[data-stage-caption]');
const playhead = stage.querySelector('.flood-playhead');
const captions = chapters.map((chapter) => chapter.querySelector('h3').textContent.trim());
const chapterReadouts = [
  { name: 'Old filter', entrance: 'A delivery text arrives.', before: 'oldRecall', after: 'oldRecall', switchAt: .43 },
  { name: 'Retrained filter', entrance: 'More scams are caught.', before: 'newRecall', after: 'newFalse', switchAt: .46 },
  { name: 'With legitimate texts', entrance: 'The filter learns real texts.', before: 'fixedRecall', after: 'fixedFalse', switchAt: .44 },
];
const reduce = matchMedia('(prefers-reduced-motion: reduce)');
const state = { mode: 'loading', chapter: 0, progress: 0, frames: 0, lenis: false, dpr: 0, calls: 0, triangles: 0, pile: 0, diagram: 0 };
window.storyState = () => ({ ...state });
const percent = new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 });
const ids = {
  oldRecall: 'y2012_late_recall', newRecall: 'naive_fix_late_recall',
  newFalse: 'naive_fix_fa_real_legit', fixedRecall: 'real_ham_fix_late_recall',
  fixedFalse: 'real_ham_fix_fa_real_legit',
};
const title = {
  oldRecall: 'Scam reports caught', newRecall: 'Scam reports caught', fixedRecall: 'Scam reports caught',
  newFalse: 'Legitimate texts flagged', fixedFalse: 'Legitimate texts flagged',
};
const clamp = (v) => Math.max(0, Math.min(1, v));
const mix = (a, b, t) => a + (b - a) * t;
const smooth = (v) => { const t = clamp(v); return t * t * (3 - 2 * t); };

function showComparison(metrics, valid) {
  const comparison = root.querySelector('[data-filter-comparison]');
  const filters = {
    retrained: ['newRecall', 'newFalse', '#retrained-filter'],
    legitimate: ['fixedRecall', 'fixedFalse', '#with-legitimate'],
  };
  if (!comparison || !Object.values(filters).every(([recall, falseAlarm]) =>
    valid(metrics[recall]) && valid(metrics[falseAlarm]))) return;

  const recall = comparison.querySelector('[data-comparison-metric="recall"]');
  const falseAlarm = comparison.querySelector('[data-comparison-metric="false-alarm"]');
  const replay = comparison.querySelector('.compare-replay');
  const announcement = comparison.querySelector('[data-comparison-status]');
  function showRun(value, announce) {
    const [recallKey, falseKey, link] = filters[value];
    for (const [row, key] of [[recall, recallKey], [falseAlarm, falseKey]]) {
      row.style.setProperty('--trial-fraction', metrics[key].value);
      row.querySelector('strong').textContent = percent.format(metrics[key].value);
    }
    replay.href = link;
    if (announce) announcement.textContent = `Scam reports caught ${percent.format(metrics[recallKey].value)}. `
      + `Legitimate texts flagged ${percent.format(metrics[falseKey].value)}.`;
  }
  showRun(comparison.querySelector('input:checked').value, false);
  comparison.addEventListener('change', (event) => {
    if (event.target.name === 'compare-filter') showRun(event.target.value, true);
  });
  comparison.hidden = false;
}

async function loadRates() {
  const response = await fetch('/api/story', { cache: 'no-store' });
  if (!response.ok) throw new Error(`Story API returned ${response.status}`);
  const { numbers } = await response.json();
  const metrics = Object.fromEntries(Object.entries(ids).map(([key, id]) => [key, numbers?.[id]]));
  const valid = (item) => Number.isFinite(item?.value) && item.value >= 0 && item.value <= 1;
  showComparison(metrics, valid);
  const old = metrics.oldRecall;
  stageRate.textContent = valid(old) ? percent.format(old.value) : '—';
  stageLabel.textContent = valid(old) ? title.oldRecall : 'Research results unavailable';
  if (old?.label) root.querySelector('[data-study-cohort]').textContent = old.label;
  const summary = (key) => {
    const item = metrics[key];
    if (!valid(item)) return `${title[key]} · unavailable`;
    const counts = Number.isInteger(item.k) && Number.isInteger(item.n) ? ` (${item.k} / ${item.n})` : '';
    return `${title[key]} · ${percent.format(item.value)}${counts}`;
  };
  const findings = root.querySelector('.flood-findings');
  if (!reduce.matches) {
    findings.setAttribute('data-awaiting-entry', '');
    const entry = new IntersectionObserver(([item]) => {
      if (!item.isIntersecting) return;
      findings.removeAttribute('data-awaiting-entry');
      findings.setAttribute('data-entered', '');
      entry.disconnect();
    }, { threshold: .15 });
    entry.observe(findings);
  }
  findings.querySelectorAll('[data-rate]').forEach((node) => {
    const key = node.dataset.rate;
    const item = metrics[key];
    node.style.setProperty('--portion', valid(item) ? item.value : 0);
    node.querySelector('strong').textContent = valid(item) ? percent.format(item.value) : '—';
    node.querySelector('span').textContent = valid(item) ? title[key] : title[key] + ' unavailable';
    node.querySelector('small').textContent = valid(item) && Number.isInteger(item.k) && Number.isInteger(item.n)
      ? item.k + ' / ' + item.n : '';
  });
  root.querySelectorAll('[data-frame]').forEach((figure) => {
    for (const key of figure.dataset.frame.split(' ')) {
      const line = document.createElement('p');
      const label = document.createElement('strong');
      label.textContent = summary(key);
      line.append(label);
      if (valid(metrics[key])) {
        const meter = document.createElement('meter');
        meter.min = 0;
        meter.max = 1;
        meter.value = metrics[key].value;
        meter.setAttribute('aria-hidden', 'true');
        line.append(meter);
      }
      figure.append(line);
    }
  });
  if (!Object.values(metrics).every(valid)) {
    state.mode = 'missing-data';
    status.textContent = 'Some research results are unavailable. You can still check a text.';
    return null;
  }
  return Object.fromEntries(Object.entries(metrics).map(([key, item]) => [key, item.value]));
}

function createScene(THREE, rates) {
  const canvas = viewport.querySelector('canvas');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'default' });
  renderer.setClearColor('#e9eef1', 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, .1, 70);
  camera.position.set(7, 4, 15);
  camera.lookAt(0, -.65, 0);

  // The upper scan head, inset feed bed and collection trays share one chassis.
  const rig = [
    [-.1, -4.1, 0, 14.4, .43, 6.1, '#12273d'],
    [-.1, -3.81, 0, 14.25, .62, 5.95, '#274c73'],
    [-.1, -3.43, 0, 13.9, .26, 5.64, '#3b638a'],
    [-.1, -3.26, -2.34, 13.7, .18, .27, '#8299ae'],
    [-.1, -3.22, 2.31, 13.78, .24, .28, '#7c96af'],
    [-.1, -3.18, 0, 13.36, .10, 3.95, '#1b3652'],
    [0, 2.74, 0, 1.92, .84, 5.78, '#203e62'],
    [0, 3.18, 0, 1.84, .19, 5.56, '#6186a9'],
    [0, 2.25, 0, 1.5, .17, 5.48, '#213853'],
    [0, 2.14, 0, .15, .13, 4.78, '#c4e1f5'],
    [0, -.56, -2.65, 1.48, 6.14, .61, '#263f5c'],
    [0, -.55, -2.31, .56, 5.75, .09, '#4f769b'],
    [0, 2.78, 2.96, .3, .18, .11, '#ff885f'],
    [.04, -3.13, 0, .37, .15, 4.8, '#a1c5e4'],
    [-1.26, -2.96, -.05, .11, .53, 3.65, '#7eacb4'],
    [1.37, -2.96, -.05, .11, .53, 3.65, '#7eacb4'],
    [.05, -3.11, -1.86, 2.65, .21, .13, '#7eacb4'],
    [3.17, -3.08, .3, 2.65, .11, 2.5, '#763e32'],
    [4.39, -2.99, .3, .12, .28, 2.5, '#bf6850'],
    [-5.15, -3.06, 2.32, .82, .11, .22, '#e0af76'],
  ];
  const outline = new THREE.Shape();
  outline.moveTo(-.43, -.5);
  outline.lineTo(.43, -.5);
  outline.quadraticCurveTo(.5, -.5, .5, -.43);
  outline.lineTo(.5, .43);
  outline.quadraticCurveTo(.5, .5, .43, .5);
  outline.lineTo(-.43, .5);
  outline.quadraticCurveTo(-.5, .5, -.5, .43);
  outline.lineTo(-.5, -.43);
  outline.quadraticCurveTo(-.5, -.5, -.43, -.5);
  const rigGeometry = new THREE.ExtrudeGeometry(outline, {
    depth: .95, bevelEnabled: true, bevelSize: .023, bevelThickness: .025, bevelSegments: 1, curveSegments: 2,
  });
  rigGeometry.center();
  const grainPixels = new Uint8Array(64 * 64 * 4);
  for (let y = 0; y < 64; y += 1) {
    for (let x = 0; x < 64; x += 1) {
      const offset = (y * 64 + x) * 4;
      const grain = 189 + (Math.imul(y + 19, 113) % 37) - 18
        + (Math.imul(x + 1, y + 17) % 13) - 6;
      grainPixels.set([grain, grain, grain, 255], offset);
    }
  }
  const grain = new THREE.DataTexture(grainPixels, 64, 64);
  grain.wrapS = grain.wrapT = THREE.RepeatWrapping;
  grain.repeat.set(2, 2);
  grain.magFilter = THREE.LinearFilter;
  grain.minFilter = THREE.LinearFilter;
  grain.needsUpdate = true;
  const rigMaterial = new THREE.MeshStandardMaterial({
    roughness: .36, metalness: .23, roughnessMap: grain, bumpMap: grain, bumpScale: .018,
  });
  const chamber = new THREE.InstancedMesh(rigGeometry, rigMaterial, rig.length);
  const segmentGeometry = new THREE.EdgesGeometry(rigGeometry, 31);
  const segmentVertices = segmentGeometry.getAttribute('position');
  const diagramVertices = new Float32Array(rig.length * segmentVertices.count * 3);
  const vertex = new THREE.Vector3();
  const fixture = new THREE.Object3D();
  const finish = new THREE.Color();
  rig.forEach(([x, y, z, sx, sy, sz, shade], index) => {
    fixture.position.set(x, y, z);
    fixture.scale.set(sx, sy, sz);
    fixture.updateMatrix();
    chamber.setMatrixAt(index, fixture.matrix);
    chamber.setColorAt(index, finish.set(shade));
    for (let i = 0; i < segmentVertices.count; i += 1) {
      vertex.fromBufferAttribute(segmentVertices, i).applyMatrix4(fixture.matrix);
      vertex.toArray(diagramVertices, (index * segmentVertices.count + i) * 3);
    }
  });
  segmentGeometry.dispose();
  chamber.computeBoundingSphere();
  scene.add(chamber);
  const diagramGeometry = new THREE.BufferGeometry();
  diagramGeometry.setAttribute('position', new THREE.BufferAttribute(diagramVertices, 3));
  const diagramMaterial = new THREE.LineBasicMaterial({
    color: '#365d80', transparent: true, opacity: 0, depthTest: false, depthWrite: false,
  });
  const diagram = new THREE.LineSegments(diagramGeometry, diagramMaterial);
  diagram.visible = false;
  diagram.renderOrder = 5;
  scene.add(diagram);
  const sky = new THREE.HemisphereLight('#e8f3ff', '#35465f', 1.28);
  const key = new THREE.DirectionalLight('#fff0df', 2.45);
  key.position.set(-3, 7, 7);
  const rim = new THREE.DirectionalLight('#b2d9ff', 2.3);
  rim.position.set(5, 3, -6);
  scene.add(sky, key, rim);
  const planPosition = [0, 24.5, .32];
  const planTarget = [0, -3, 0];

  const shadowImage = document.createElement('canvas');
  shadowImage.width = shadowImage.height = 128;
  const shadowContext = shadowImage.getContext('2d');
  const gradient = shadowContext.createRadialGradient(64, 64, 15, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(16,33,60,.39)');
  gradient.addColorStop(.55, 'rgba(20,40,63,.22)');
  gradient.addColorStop(1, 'rgba(30,53,87,0)');
  shadowContext.fillStyle = gradient;
  shadowContext.fillRect(0, 0, 128, 128);
  const shadowTexture = new THREE.CanvasTexture(shadowImage);
  shadowTexture.colorSpace = THREE.SRGBColorSpace;
  const shadowGeometry = new THREE.PlaneGeometry(22, 10);
  const shadowMaterial = new THREE.MeshBasicMaterial({ map: shadowTexture, transparent: true, depthWrite: false });
  const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial);
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.set(.5, -4.34, .85);
  scene.add(shadow);

  const gateNote = viewport.querySelector('[data-scene-note="gate"]');
  const outcomeNote = viewport.querySelector('[data-scene-note="outcome"]');
  const projected = new THREE.Vector3();
  const views = [
    { position: [9.1, 6.6, 18.1], target: [-.45, -1.05, .2] },
    { position: [2.8, 4.1, 14.8], target: [1.15, -.65, 0] },
    { position: [2.7, 4.3, 11.35], target: [.2, -1.62, 0] },
    { position: [4.0, 4.8, 12.6], target: [1.12, -1.65, 0] },
  ];
  let viewWidth = 0, viewHeight = 0, coverOverScene = true, lens = 40;
  function annotate(note, x, y, z, enabled = true) {
    if (!enabled) { note.hidden = true; return; }
    projected.set(x, y, z).project(camera);
    const px = (projected.x * .5 + .5) * viewWidth;
    const py = (.5 - projected.y * .5) * viewHeight;
    const fits = px > 12 && px < viewWidth - 112 && py > 16 && py < viewHeight - 16;
    note.hidden = !fits;
    if (fits) note.style.transform = 'translate3d(' + Math.round(px) + 'px,' + Math.round(py) + 'px,0)';
  }


  const bubble = new THREE.Shape();
  bubble.moveTo(-.48, -.15);
  bubble.lineTo(-.38, -.15); bubble.lineTo(-.47, -.28); bubble.lineTo(-.13, -.15);
  bubble.lineTo(.43, -.15); bubble.quadraticCurveTo(.56, -.15, .56, -.03);
  bubble.lineTo(.56, .15); bubble.quadraticCurveTo(.56, .27, .43, .27);
  bubble.lineTo(-.44, .27); bubble.quadraticCurveTo(-.57, .27, -.57, .15);
  bubble.lineTo(-.57, -.03); bubble.quadraticCurveTo(-.57, -.15, -.48, -.15);
  const geometry = new THREE.ExtrudeGeometry(bubble, { depth: .07, bevelEnabled: false, curveSegments: 3 });
  const ink = new THREE.Color('#fbf5e8');
  const red = new THREE.Color('#e97956');
  const ion = new THREE.Color('#b4dcff');
  const green = new THREE.Color('#61c2ac');
  const color = new THREE.Color();
  const material = new THREE.MeshBasicMaterial();
  const scamCount = 176, legitCount = 200;
  const instances = new THREE.InstancedMesh(geometry, material, scamCount + legitCount);
  instances.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  instances.setColorAt(0, ink); // Allocate instanceColor before setting the usage hint.
  instances.instanceColor.setUsage(THREE.DynamicDrawUsage);
  instances.frustumCulled = false;
  scene.add(instances);

  function messageLine(x, y, width) {
    const line = new THREE.Shape();
    line.moveTo(x, y); line.lineTo(x + width, y); line.lineTo(x + width, y + .032);
    line.lineTo(x, y + .032); line.closePath();
    return line;
  }
  const markGeometry = new THREE.ShapeGeometry([messageLine(-.31, .1, .56), messageLine(-.31, .018, .32)]);
  markGeometry.translate(0, 0, .075);
  const markMat = new THREE.MeshBasicMaterial({ color: '#263746' });
  const marks = new THREE.InstancedMesh(markGeometry, markMat, instances.count);
  marks.instanceMatrix = instances.instanceMatrix;
  marks.frustumCulled = false;
  scene.add(marks);

  const plane = new THREE.PlaneGeometry(5.2, 6.2);
  const filterMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    forceSinglePass: true,
    side: THREE.DoubleSide,
    uniforms: { tint: { value: ion }, strength: { value: .35 }, beam: { value: .12 } },
    vertexShader: [
      'varying vec2 vUv;',
      'void main() {',
      '  vUv = uv;',
      '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
      '}',
    ].join('\n'),
    fragmentShader: [
      'varying vec2 vUv;',
      'uniform vec3 tint;',
      'uniform float strength;',
      'uniform float beam;',
      'void main() {',
      '  vec2 centered = 2.0 * vUv - 1.0;',
      '  float border = smoothstep(0.0, 0.12, min(vUv.x, 1.0 - vUv.x));',
      '  float core = exp(-2.8 * dot(centered, centered));',
      '  float delta = abs(vUv.y - beam);',
      '  float scanLine = exp(-108.0 * delta);',
      '  float wake = exp(-19.0 * delta);',
      '  vec2 grid = abs(fract(vUv * vec2(12.0, 24.0)) - 0.5);',
      '  float hatch = 1.0 - smoothstep(0.0, 0.045, min(grid.x, grid.y));',
      '  gl_FragColor = vec4(tint, border * (core * strength + wake * 0.17 + scanLine * 0.61 + hatch * 0.075));',
      '  #include <colorspace_fragment>',
      '}',
    ].join('\n'),
  });
  const filter = new THREE.Mesh(plane, filterMat);
  filter.rotation.y = Math.PI / 2;
  const edges = new THREE.EdgesGeometry(plane);
  const rimMat = new THREE.LineBasicMaterial({ color: ion, transparent: true, opacity: .68 });
  filter.add(new THREE.LineSegments(edges, rimMat));
  scene.add(filter);
  const guideGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-8, .18, 0), new THREE.Vector3(8, .18, 0),
    new THREE.Vector3(-8, -3.4, 0), new THREE.Vector3(8, -3.4, 0),
    new THREE.Vector3(6.5, .18, 0), new THREE.Vector3(6, .38, 0),
    new THREE.Vector3(6.5, .18, 0), new THREE.Vector3(6, -.02, 0)
  ]);
  const guideMat = new THREE.LineBasicMaterial({ color: '#466a8b', transparent: true, opacity: .49 });
  scene.add(new THREE.LineSegments(guideGeometry, guideMat));

  // A public, redacted example is drawn once. User-entered text stays in the checker.
  const label = document.createElement('canvas');
  label.width = 768;
  label.height = 392;
  const face = label.getContext('2d');
  face.fillStyle = '#f6f1e4';
  face.fillRect(0, 0, label.width, label.height);
  face.fillStyle = '#405a72';
  face.font = '600 29px system-ui';
  face.fillText('TEXT MESSAGE', 44, 61);
  face.fillRect(44, 81, 680, 2);
  face.fillStyle = '#e9aa98';
  face.fillRect(40, 179, 474, 64);
  face.fillStyle = '#172d48';
  face.font = '650 55px system-ui';
  face.fillText('Confirm your', 44, 160);
  face.fillText('shipment details', 44, 228);
  face.fillStyle = '#744e40';
  face.font = '32px system-ui';
  face.fillText('[link removed]', 44, 316);
  const messageTexture = new THREE.CanvasTexture(label);
  messageTexture.colorSpace = THREE.SRGBColorSpace;
  const messageShape = new THREE.PlaneGeometry(4.6, 2.35);
  const messageFace = new THREE.MeshBasicMaterial({ map: messageTexture, transparent: true });
  const specimen = new THREE.Mesh(messageShape, messageFace);
  scene.add(specimen);

  // The rank fixes the selection. A separate hash scatters messages without changing it.
  function noise(index, salt) {
    let value = Math.imul(index + 1, 374761393) ^ Math.imul(salt, 668265263);
    value = Math.imul(value ^ (value >>> 13), 1274126177);
    return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
  }
  const particles = Array.from({ length: instances.count }, (_, i) => {
    const legit = i >= scamCount;
    const index = legit ? i - scamCount : i;
    const count = legit ? legitCount : scamCount;
    return { legit, rank: (index * 73 + 11) % count, delay: .41 * noise(i, 1),
      y: (noise(i, 2) - .5) * 1.65 + (legit ? -1.16 : 1.32),
      z: (noise(i, 3) - .5) * 4.8, angle: (noise(i, 4) - .5) * .32 };
  });
  const pose = new THREE.Object3D();
  const caughtScams = [rates.oldRecall, rates.newRecall, rates.fixedRecall]
    .map((rate) => Math.round(rate * scamCount));
  const bigPile = Math.round(rates.newFalse * legitCount);
  const smallPile = Math.round(rates.fixedFalse * legitCount);

  let lastChapter = -1;
  let lastProgress = -1;
  function poseMessages(chapter, t, diagramBlend) {
    let pile = 0;
    for (let i = 0; i < particles.length; i += 1) {
      const p = particles[i];
      const flight = clamp((Math.min(1, t * .92 + .08) - p.delay) / .58);
      const after = clamp(2 * flight - 1);
      let x = mix(-8, 8, flight), y = p.y, z = p.z;
      let size = flight > .01 && flight < .995 ? (chapter === 0 ? .56 : .66) : 0;
      let tilt = 0;
      color.copy(p.legit ? green : ink);

      if (!p.legit && p.rank < caughtScams[chapter] && after > 0) {
        x = mix(0, 3.1, smooth(after * 1.5)); y -= 7 * after * after;
        z = mix(z, .95, after);
        tilt = -.7 * after;
        color.lerp(red, smooth(after * 6));
      } else if (p.legit) {
        const pileX = -.95 + (p.rank % 10) * .21;
        const pileY = -3.15 + Math.floor(p.rank / 50) * .26;
        const pileZ = -1.35 + (Math.floor(p.rank / 10) % 5) * .66;
        if (chapter === 0) {
          size = 0;
        } else if (chapter === 1 && after > 0 && p.rank < bigPile) {
          const settle = smooth(after * 3);
          x = mix(0, pileX, settle); y = mix(y, pileY, settle); z = mix(z, pileZ, settle);
          size = mix(.66, .41, settle);
          if (settle > .95) pile += 1;
        } else if (chapter === 2 && p.rank < bigPile) {
          const release = p.rank < smallPile ? 0 : smooth((t - p.delay * .5) / .7);
          x = mix(pileX, 8, release); y = mix(pileY, p.y, release); z = mix(pileZ, p.z, release);
          size = release < .995 ? .41 : 0;
          if (release === 0 && p.rank < smallPile) pile += 1;
        } else if (chapter === 2) {
          size = 0;
        }
      }
      pose.position.set(x, y, z);
      pose.rotation.set(mix(p.angle * .4, -Math.PI / 2, diagramBlend),
        mix(-.22 + p.angle, 0, diagramBlend), mix(tilt + p.angle * .3, 0, diagramBlend));
      pose.scale.setScalar(Math.max(size, .00001));
      pose.updateMatrix();
      instances.setMatrixAt(i, pose.matrix);
      instances.setColorAt(i, color);
    }
    instances.instanceMatrix.needsUpdate = true;
    instances.instanceColor.needsUpdate = true;
    state.pile = pile;
  }

  function draw(chapter, t, seconds) {
    // Before the visitor scrolls, show incoming messages without crossing the filter.
    const preview = chapter === 0 ? clamp(1 - t / .115) * (.061 + .023 * Math.sin(seconds * 2.4)) : 0;
    t += preview;
    const gateFocus = chapter === 0 ? smooth(1 - Math.abs(t - .4) / .16) : 0;
    filterMat.uniforms.strength.value = chapter === 0 ? .32 + .48 * gateFocus : .50;
    filterMat.uniforms.beam.value = mix(.5 - .38 * Math.cos(seconds * 1.42), .69, gateFocus);
    if (lastChapter !== chapter || Math.abs(t - lastProgress) > .0001) {
      lastChapter = chapter;
      lastProgress = t;
      const from = views[chapter], to = views[chapter + 1];
      const movement = smooth(t);
      const opening = chapter === 0 ? 1 - smooth(t / .45) : 0;
      const tight = viewWidth < 751;
      const plan = chapter === 2 ? smooth((t - .27) / .65) : 0;
      camera.position.set(...from.position.map((value, axis) => mix(mix(value, to.position[axis], movement), planPosition[axis], plan)));
      camera.up.set(tight ? -plan : 0, 1, (tight ? -.04 : -.37) * plan);
      camera.lookAt(...from.target.map((value, axis) => mix(mix(value, to.target[axis], movement), planTarget[axis], plan)));
      camera.fov = mix(lens * (1 - .09 * gateFocus), tight ? 34.5 : 19, plan);
      camera.setViewOffset(viewWidth || 1, viewHeight || 1, tight ? 0 : -viewWidth * .187 * opening,
        tight && coverOverScene ? -viewHeight * .215 * opening : 0, viewWidth || 1, viewHeight || 1);
      const route = smooth((t - .11) / .73);
      specimen.visible = chapter === 0 && t < .94;
      specimen.position.set(mix(-2.55, 4.7, route), mix(.42, .86, route) + .12 * Math.sin(seconds * 1.8) * (1 - route), 1.68);
      specimen.rotation.set(-.13, mix(.21, .31, route), mix(-.09, .045, route));
      specimen.scale.setScalar(mix(1, .52, route));
      messageFace.opacity = 1 - smooth((t - .81) / .13);
      const tracing = smooth((plan - .18) / .7);
      poseMessages(chapter, t, tracing);
      const seeThrough = tracing > .01;
      if (rigMaterial.transparent !== seeThrough) {
        rigMaterial.transparent = seeThrough;
        rigMaterial.depthWrite = !seeThrough;
        rigMaterial.needsUpdate = true;
      }
      rigMaterial.opacity = mix(1, .075, tracing);
      diagram.visible = seeThrough;
      diagramMaterial.opacity = .69 * tracing;
      shadowMaterial.opacity = 1 - tracing;
      viewport.style.setProperty('--diagram', tracing.toFixed(3));
      viewport.toggleAttribute('data-diagram', tracing > .42);
      state.diagram = tracing;
    }
    renderer.render(scene, camera);
    const overhead = state.diagram > .6;
    annotate(gateNote, 0, overhead ? 2.9 : 2.23, overhead ? -1.1 : 2.06, chapter !== 0 || t > .26);
    const nextLabel = chapter === 0 ? 'Passed through' : overhead ? 'Still flagged' : 'False alarms';
    if (outcomeNote.textContent !== nextLabel) outcomeNote.textContent = nextLabel;
    if (chapter === 0) annotate(outcomeNote, 4.8, 1.6, 1.72, t > .43);
    else if (overhead) annotate(outcomeNote, -.98, -1.7, 2.18);
    else annotate(outcomeNote, .75, -2.12, 1.73, t > .38);
    state.calls = renderer.info.render.calls;
    state.triangles = renderer.info.render.triangles;
  }
  return {
    draw,
    resize() {
      const w = viewWidth = viewport.clientWidth, h = viewHeight = viewport.clientHeight;
      coverOverScene = getComputedStyle(cover).position === 'absolute';
      camera.aspect = w / Math.max(1, h);
      lens = camera.aspect < 1.15 ? 52 : camera.aspect > 1.85 ? 38 : 44;
      camera.fov = lens;
      camera.updateProjectionMatrix();
      lastProgress = -1;
      state.dpr = Math.min(devicePixelRatio || 1, 1.5);
      renderer.setPixelRatio(state.dpr);
      renderer.setSize(w, h, false);
    },
    dispose() {
      for (const asset of [instances, marks, geometry, material, markGeometry, markMat, rigGeometry, rigMaterial, chamber, plane, filterMat, edges, rimMat, guideGeometry, guideMat]) asset.dispose();
      messageTexture.dispose();
      messageShape.dispose();
      messageFace.dispose();
      shadowTexture.dispose();
      shadowGeometry.dispose();
      shadowMaterial.dispose();
      grain.dispose();
      diagramGeometry.dispose();
      diagramMaterial.dispose();
      renderer.dispose();
    },
  };
}

const libs = [
  ['gsap', './vendor/gsap-3.12.5.min.js'],
  ['ScrollTrigger', './vendor/ScrollTrigger-3.12.5.min.js'],
  ['Lenis', './vendor/lenis-1.1.13.min.js'],
];
function loadScript([name, src]) {
  if (window[name]) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`${name} failed to load`));
    document.head.append(script);
  });
}
let libraryPromise;
const getLibraries = () => libraryPromise ??= (async () => {
  await loadScript(libs[0]);
  const [THREE] = await Promise.all([
    import('./vendor/three-r160.module.js'),
    ...libs.slice(1).map(loadScript),
  ]);
  return THREE;
})();

function mount(THREE, rates, restoreInitialLocation) {
  const { gsap, ScrollTrigger, Lenis } = window;
  gsap.registerPlugin(ScrollTrigger);
  root.classList.add('flood-live');
  let world;
  try { world = createScene(THREE, rates); }
  catch (error) { root.classList.remove('flood-live'); throw error; }

  const lenis = new Lenis({ lerp: .08, smoothWheel: true, syncTouch: false });
  const experiment = document.getElementById('inbox-flood');
  const experimentLinks = [...document.querySelectorAll('a[href="#inbox-flood"]')];
  function seekExperiment(immediate = false) {
    const destination = scrollY + experiment.getBoundingClientRect().top;
    lenis.scrollTo(destination, { immediate, duration: .75 });
  }
  function jumpToExperiment(event) {
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    event.preventDefault();
    if (location.hash !== '#inbox-flood') history.pushState(null, '', '#inbox-flood');
    seekExperiment();
  }
  experimentLinks.forEach((link) => link.addEventListener('click', jumpToExperiment));
  const boundaryLinks = [...document.querySelectorAll('a[href="#check-title"], a[href="#msg"], a[href="#findings"]')];
  function releaseScroll(event) {
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    // The checker and keyboard skip link use normal anchor navigation.
    lenis.scrollTo(scrollY, { immediate: true });
  }
  boundaryLinks.forEach((link) => link.addEventListener('click', releaseScroll));
  lenis.on('scroll', ScrollTrigger.update);
  state.mode = 'webgl';
  state.lenis = true;
  const clock = { p: 0 };
  const phaseControls = [...stage.querySelectorAll('.flood-controls a')];
  const phaseLinks = [...phaseControls, ...root.querySelectorAll('[data-story-jump]')];
  let scrubTrigger;
  function seekPhase(index, immediate = false) {
    const fraction = mix(breaks[index], breaks[index + 1], index === 0 ? .58 : .89);
    lenis.scrollTo(mix(scrubTrigger.start, scrubTrigger.end, fraction), { immediate, duration: .75 });
  }
  function jumpToPhase(event) {
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey || !scrubTrigger) return;
    const anchor = event.currentTarget;
    const index = phaseControls.findIndex((link) => link.hash === anchor.hash);
    if (index < 0) return;
    event.preventDefault();
    if (location.hash !== anchor.hash) history.pushState(null, '', anchor.hash);
    seekPhase(index);
  }
  phaseLinks.forEach((link) => link.addEventListener('click', jumpToPhase));

  let seekFrame = 0;
  function restoreHash() {
    const index = phaseControls.findIndex((link) => link.hash === location.hash);
    if (index >= 0) seekPhase(index, true);
    else if (location.hash === '#inbox-flood') seekExperiment(true);
    else return false;
    return true;
  }
  function handleHistory() {
    if (seekFrame) return;
    seekFrame = requestAnimationFrame(() => {
      seekFrame = 0;
      restoreHash();
    });
  }
  window.addEventListener('popstate', handleHistory);
  window.addEventListener('hashchange', handleHistory);

  let breaks = [0, 1 / 3, 2 / 3, 1];
  let visible = true;
  let dirty = true;
  let frame = 0;
  let time = 0;
  let lastIdleFrame = 0;
  let lastReadout = -1;
  let lastBeat = -1;
  let lastRate;
  let captionAnimation;
  let rateAnimation;
  let lastTick;
  let idlePaused = false;
  const pause = stage.querySelector('.flood-motion');
  pause.hidden = false;
  function toggleIdle() {
    idlePaused = !idlePaused;
    pause.setAttribute('aria-pressed', String(idlePaused));
    state.idlePaused = idlePaused;
    dirty = true;
    queueDraw();
  }
  pause.addEventListener('click', toggleIdle);
  const tick = (seconds) => {
    lenis.raf(seconds * 1000);
    if (!idlePaused) time += Math.min(.08, seconds - (lastTick ?? seconds));
    lastTick = seconds;
    if (!idlePaused && seconds - lastIdleFrame >= .024) {
      lastIdleFrame = seconds;
      dirty = true;
      queueDraw();
    }
  };
  gsap.ticker.add(tick);
  function measure(self) {
    const top = chapters[0].getBoundingClientRect().top;
    const span = Math.max(1, self.end - self.start);
    const at = (chapter) => clamp((chapter.getBoundingClientRect().top - top) / span);
    breaks = [0, at(chapters[1]), at(chapters[2]), 1];
    dirty = true;
    queueDraw();
  }
  function queueDraw() {
    if (!visible || !dirty || frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (!visible || !dirty) return;
      dirty = false;
      const chapter = clock.p < breaks[1] ? 0 : clock.p < breaks[2] ? 1 : 2;
      const t = clamp((clock.p - breaks[chapter]) / Math.max(.001, breaks[chapter + 1] - breaks[chapter]));
      const opacity = chapter === 0 ? 1 - smooth((t - .045) / .16) : 0;
      cover.style.setProperty('--intro-opacity', opacity.toFixed(3));
      cover.style.setProperty('--first-line-out', chapter === 0 ? smooth(t / .18).toFixed(3) : '1');
      cover.style.setProperty('--second-line-out', chapter === 0 ? smooth((t - .04) / .18).toFixed(3) : '1');
      cover.toggleAttribute('data-past-cover', opacity < .15 && !cover.contains(document.activeElement));
      playhead.style.transform = 'scaleX(' + clock.p.toFixed(4) + ')';
      const readout = chapterReadouts[chapter];
      if (lastReadout !== chapter) {
        lastReadout = chapter;
        stageStep.textContent = readout.name;
        phaseControls.forEach((link, index) => {
          if (index === chapter) link.setAttribute('aria-current', 'step');
          else link.removeAttribute('aria-current');
        });
      }
      const showOutcome = t >= readout.switchAt;
      const beat = chapter * 2 + Number(showOutcome);
      if (lastBeat !== beat) {
        const firstDraw = lastBeat === -1;
        lastBeat = beat;
        stageCaption.textContent = showOutcome ? captions[chapter] : readout.entrance;
        captionAnimation?.cancel();
        if (!firstDraw) {
          captionAnimation = stageCaption.animate(
            [{ opacity: 0, clipPath: 'inset(88% 0 -20%)', transform: 'translateY(9px)' },
              { opacity: 1, clipPath: 'inset(-20% 0 -20%)', transform: 'none' }],
            { duration: 300, easing: 'cubic-bezier(.23,1,.32,1)' }
          );
        }
        const metric = showOutcome ? readout.after : readout.before;
        if (metric !== lastRate) {
          lastRate = metric;
          stage.dataset.phase = metric;
          stageLabel.textContent = title[metric];
          stageRate.textContent = percent.format(rates[metric]);
          rateAnimation?.cancel();
          if (!firstDraw) {
            rateAnimation = stageRate.parentElement.animate(
              [{ opacity: .25, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }],
              { duration: 250, easing: 'cubic-bezier(.23,1,.32,1)' }
            );
          }
        }
      }
      state.chapter = chapter + 1;
      state.progress = t;
      state.frames += 1;
      world.draw(chapter, t, time);
    });
  }

  const inView = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) { dirty = true; queueDraw(); }
  });
  inView.observe(stage);
  const sizing = new ResizeObserver(() => {
    world.resize();
    dirty = true;
    queueDraw();
  });
  sizing.observe(viewport);
  world.resize();

  const effects = gsap.context(() => {
    const timeline = gsap.timeline({
      defaults: { ease: 'none' },
      scrollTrigger: { trigger: chapters[0], endTrigger: track, start: 'top top', end: 'bottom bottom', scrub: 1, onRefresh: measure },
      onUpdate: () => { dirty = true; queueDraw(); },
    }).to(clock, { p: 1, duration: 1 });
    scrubTrigger = timeline.scrollTrigger;
  }, root);
  ScrollTrigger.refresh();
  if (restoreInitialLocation && location.hash && !restoreHash()) {
    document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: 'instant' });
  }
  queueDraw();
  return () => {
    cancelAnimationFrame(frame);
    cancelAnimationFrame(seekFrame);
    inView.disconnect(); sizing.disconnect();
    effects.revert();
    gsap.ticker.remove(tick); lenis.destroy(); world.dispose();
    experimentLinks.forEach((link) => link.removeEventListener('click', jumpToExperiment));
    boundaryLinks.forEach((link) => link.removeEventListener('click', releaseScroll));
    phaseLinks.forEach((link) => link.removeEventListener('click', jumpToPhase));
    window.removeEventListener('popstate', handleHistory);
    window.removeEventListener('hashchange', handleHistory);
    captionAnimation?.cancel();
    rateAnimation?.cancel();
    cover.style.removeProperty('--intro-opacity');
    cover.style.removeProperty('--first-line-out');
    cover.style.removeProperty('--second-line-out');
    cover.removeAttribute('data-past-cover');
    playhead.style.removeProperty('transform');
    viewport.style.removeProperty('--diagram');
    viewport.removeAttribute('data-diagram');
    state.diagram = 0;
    pause.removeEventListener('click', toggleIdle);
    pause.hidden = true;
    pause.setAttribute('aria-pressed', 'false');
    state.idlePaused = false;
    root.classList.remove('flood-live');
    state.lenis = false;
  };
}

let rates, unmount, generation = 0, contextLost = false, mountedOnce = false;
async function syncMotion() {
  const request = ++generation;
  unmount?.();
  unmount = undefined;
  if (!rates || reduce.matches || contextLost) {
    if (reduce.matches) state.mode = 'reduced';
    else if (contextLost) state.mode = 'fallback';
    return;
  }
  try {
    const THREE = await getLibraries();
    if (request !== generation) return;
    unmount = mount(THREE, rates, !mountedOnce);
    mountedOnce = true;
  } catch (error) {
    state.mode = 'fallback';
    status.textContent = 'The animated view is unavailable. The test results are below.';
    console.warn('Inbox flood:', error);
  }
}
viewport.querySelector('canvas').addEventListener('webglcontextlost', (event) => {
  event.preventDefault();
  contextLost = true;
  void syncMotion();
  status.textContent = 'The animated view is unavailable. The test results are below.';
});
viewport.querySelector('canvas').addEventListener('webglcontextrestored', () => {
  contextLost = false;
  status.textContent = '';
  void syncMotion();
});
reduce.addEventListener('change', syncMotion);
loadRates().then((values) => { rates = values; return syncMotion(); }).catch((error) => {
  state.mode = 'api-error';
  stageRate.textContent = '—';
  stageLabel.textContent = 'Research results unavailable';
  status.textContent = 'The story results are unavailable. You can still check a text.';
  console.warn('Inbox flood:', error);
});
