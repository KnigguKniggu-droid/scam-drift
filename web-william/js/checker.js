import { narrate } from './capsule.js';

const verdicts = new Set(['RED', 'YELLOW', 'GREEN']);
const greenHeadline = 'The sender is unverified.';
const greenNote = 'No warning signs found in the text. Before you sign, share account details or pay, verify the request through your usual app or a number you already trust.';

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

export function init() {
  const section = document.getElementById('try');
  const form = section.querySelector('#ck-form');
  const input = section.querySelector('#ck-text');
  const count = section.querySelector('#ck-count');
  const sampleNote = section.querySelector('#ck-sample');
  const status = section.querySelector('#ck-status');
  const statusText = status.querySelector('.ck__status-t');
  const live = section.querySelector('#ck-live');
  const card = section.querySelector('#ck-card');
  const empty = section.querySelector('[data-empty]');
  const picker = section.querySelector('.ck__list');
  const field = selector => card.querySelector(selector);
  const headlineField = field('[data-say-line]');
  const note = element('p', '', 'ck__advice');
  note.hidden = true;
  headlineField.after(note);
  let pending;
  let exampleRequest;
  let samplePosition = 0;
  let options = [];
  let selected;
  let revision = 0;

  narrate(section.querySelector('#ck-cap'), {
    sections: '[data-cap-place]',
    controls: matchMedia('(hover: hover) and (pointer: fine)').matches
      ? [...form.querySelectorAll('.ck__actions [data-say]')] : [],
  });

  function setStatus(state, text) {
    status.dataset.state = state;
    statusText.textContent = text;
  }

  function reset(example) {
    revision++;
    pending?.abort();
    pending = undefined;
    selected = example;
    card.hidden = true;
    empty.hidden = false;
    live.textContent = '';
    count.textContent = `${input.value.length.toLocaleString()} characters`;
    sampleNote.hidden = !example;
    sampleNote.textContent = example ? `${example.kind} · ${example.label}` : '';
    options.forEach((option, index) => {
      const active = option.example === selected;
      option.node.setAttribute('aria-selected', String(active));
      const hasSelectedOption = selected?.kind === 'REAL';
      option.node.tabIndex = active || (!hasSelectedOption && index === 0) ? 0 : -1;
    });
    setStatus('idle', 'Ready to check a text.');
  }

  function render(data, text) {
    const { tier } = data;
    card.dataset.tier = tier;
    const verdict = field('[data-v]');
    verdict.className = `verdict verdict--${tier.toLowerCase()}`;
    verdict.textContent = tier;
    const isGreen = tier === 'GREEN';
    const headline = isGreen ? greenHeadline : data.headline;
    note.hidden = !isGreen;
    note.textContent = isGreen ? greenNote : '';
    headlineField.textContent = headline;
    field('[data-more]').replaceChildren(...data.actions.map(action => element('li', action)));
    const truth = field('[data-truth]');
    truth.hidden = !selected;
    truth.textContent = selected ? `${selected.kind} · ${selected.source}` : '';
    field('[data-meta]').textContent = 'Message checked';
    field('[data-bubble]').textContent = text;
    field('[data-words-h]').textContent = [data.reason, data.translation_note, data.translation_detail].filter(Boolean).join(' ');
    const signals = data.signals.map(signal => signal.phrase ? `${signal.label} · “${signal.phrase}”` : signal.label);
    field('[data-words]').replaceChildren(...[...new Set([...signals, ...data.top_words])].map(word => element('li', word, 'ck__w')));
    field('[data-engine]').textContent = data.context_model === 'bert-tiny-sms-v1'
      ? 'Checked with the fine-tuned model and scam-pattern checks.'
      : 'Checked with word and scam-pattern checks.';
    empty.hidden = true;
    card.hidden = false;
    card.classList.remove('is-in');
    requestAnimationFrame(() => { if (!card.hidden) card.classList.add('is-in'); });
    setStatus('ready', 'Check complete.');
    live.textContent = `${tier}. ${headline} ${isGreen ? greenNote : data.actions[0] ?? ''}`;
    const rect = card.getBoundingClientRect();
    if (rect.top > innerHeight - 120 || rect.bottom < 80) {
      card.scrollIntoView({ block: 'start', behavior: document.documentElement.dataset.motion === 'paused' ? 'instant' : 'smooth' });
    }
  }

  async function check() {
    const text = input.value.trim();
    if (!text) {
      setStatus('note', 'Paste or type a message first.');
      live.textContent = statusText.textContent;
      input.focus();
      return;
    }
    pending?.abort();
    const request = new AbortController();
    pending = request;
    empty.hidden = false;
    card.hidden = true;
    live.textContent = 'Checking your message.';
    setStatus('loading', 'Checking your message…');
    const timeout = setTimeout(() => request.abort(), 12000);
    try {
      const response = await fetch('/api/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: request.signal,
      });
      if (!response.ok) throw new Error(`Checker returned ${response.status}`);
      const data = await response.json();
      if (!verdicts.has(data.tier)) throw new Error('Invalid verdict');
      if (pending === request) render(data, text);
    } catch {
      if (pending === request) {
        setStatus('error', 'The check did not finish. Try again. Verify urgent requests through a number or app you already trust.');
        live.textContent = statusText.textContent;
      }
    } finally {
      clearTimeout(timeout);
      if (pending === request) pending = undefined;
    }
  }

  function choose(example) {
    input.value = example.text;
    reset(example);
    return check();
  }

  function loadExamples() {
    exampleRequest ??= fetch('/api/examples').then(async response => {
      if (!response.ok) throw new Error(`Examples returned ${response.status}`);
      const examples = await response.json();
      options = examples.filter(example => example.kind === 'REAL').map((example, index) => {
        const node = element('li', '', 'ck__opt');
        node.setAttribute('role', 'option');
        node.setAttribute('aria-selected', 'false');
        node.tabIndex = index ? -1 : 0;
        node.append(element('span', example.label, 'ck__opt-meta'), element('span', example.text, 'ck__opt-text'));
        node.addEventListener('click', () => void choose(example));
        return { node, example };
      });
      picker.replaceChildren(...options.map(option => option.node));
      picker.closest('.ck__picker').hidden = !options.length;
      return examples;
    }).catch(error => {
      exampleRequest = undefined;
      throw error;
    });
    return exampleRequest;
  }

  picker.addEventListener('keydown', event => {
    const index = options.findIndex(option => option.node === event.target);
    if (index < 0) return;
    const next = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: options.length - 1 }[event.key];
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void choose(options[index].example);
    } else if (next !== undefined) {
      event.preventDefault();
      options[Math.max(0, Math.min(options.length - 1, next))].node.focus();
    }
  });
  input.addEventListener('input', () => reset());
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener('submit', event => { event.preventDefault(); void check(); });
  form.addEventListener('click', async event => {
    const action = event.target.closest('[data-act]')?.dataset.act;
    const current = ++revision;
    if (action === 'clear') {
      input.value = '';
      reset();
      input.focus();
    } else if (action === 'sample') {
      try {
        const examples = await loadExamples();
        if (revision === current && examples.length) await choose(examples[samplePosition++ % examples.length]);
      } catch {
        if (revision === current) setStatus('error', 'Samples could not load. You can still paste a text.');
      }
    } else if (action === 'paste') {
      try {
        const text = await navigator.clipboard.readText();
        if (revision !== current) return;
        if (text.trim()) { input.value = text.slice(0, input.maxLength); reset(); }
        input.focus();
        setStatus('note', text.trim() ? 'Pasted. Press Check a text.' : 'Your clipboard is empty. Copy a message first.');
      } catch {
        if (revision !== current) return;
        input.focus();
        setStatus('note', 'Paste with Ctrl+V, ⌘V or the Paste option on your phone.');
      }
    }
  });
  void loadExamples().catch(() => { picker.closest('.ck__picker').hidden = true; });
  window.dispatchEvent(new Event('sd:dom'));
}
