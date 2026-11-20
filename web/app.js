/* Scam Drift checker (post-deadline). No build step, no libraries.
   Talks to server.py: POST /api/check, GET /api/examples. Builds every node with the DOM API (no innerHTML with
   message text). Sends focus to the verdict after an explicit check.
   This project is a prototype and is not financial advice. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var form = $("check-form"), msg = $("msg"), countN = $("count-n"), pasteBtn = $("paste-btn"),
      pasteStatus = $("paste-status"), checkBtn = $("check-btn"), checkBtnText = $("check-btn-text"),
      clearBtn = $("clear-btn"), result = $("result"), announce = $("announce"), exList = $("ex-list"),
      sampleButtons = [$("sample-btn")].concat(Array.from(document.querySelectorAll("[data-run-sample]")));

  var recovery = $('recovery');
  var recoverySummary = recovery.querySelector('summary');
  var recoveryStatus = $('recovery-status');
  recovery.addEventListener('change', function (event) {
    if (event.target.name !== 'recovery-step') return;
    var selected = event.target.value;
    for (var panel of recovery.querySelectorAll('[data-recovery-panel]')) {
      panel.hidden = panel.dataset.recoveryPanel !== selected;
      if (!panel.hidden) recoveryStatus.textContent = panel.querySelector('li').textContent;
    }
  });

  function openRecovery(event) {
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    event.preventDefault();
    recovery.open = true;
    recoverySummary.focus({ preventScroll: true });
    recovery.scrollIntoView({ block: 'nearest' });
  }

  var canSpeak = "speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function";
  var requestId = 0;
  var activeCheck = null;
  var announcementTimer;

  /* ---------- tiny DOM helper ---------- */
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") el.className = v;
        else if (k === "text") el.textContent = v;
        else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? "" : v);
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  var SVG_NS = "http://www.w3.org/2000/svg";
  var ICONS = {
    RED: '<path d="M7.9 2h8.2L22 7.9v8.2L16.1 22H7.9L2 16.1V7.9z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    YELLOW: '<path d="M12 3 2 21h20z"/><path d="M12 10v4"/><path d="M12 17.5h.01"/>',
    GREEN: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    speak: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16h.01"/>'
  };
  function icon(name) {
    var s = document.createElementNS(SVG_NS, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("class", "icon");
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("focusable", "false");
    s.innerHTML = ICONS[name]; // static markup only
    return s;
  }

  /* ---------- input: count, Enter, paste, clear ---------- */
  function updateCount() {
    var n = msg.value.length;
    countN.textContent = n.toLocaleString();
    clearBtn.hidden = n === 0;
  }
  msg.addEventListener("input", function () {
    cancelCheck();
    clearResult();
    updateCount();
    pasteStatus.textContent = "";
    markExample(null);
  });
  // Touch screens have no Shift key: there, Enter makes a new line and the Check button checks.
  var coarse = window.matchMedia ? window.matchMedia("(pointer: coarse)") : { matches: false };
  var msgHint = $("msg-hint");
  function updateHint() {
    msgHint.textContent = coarse.matches
      ? "Tap Check this text when ready."
      : "Press Enter to check. Press Shift and Enter for a new line.";
  }
  updateHint();
  if (coarse.addEventListener) coarse.addEventListener("change", updateHint);
  msg.addEventListener("keydown", function (e) {
    if (coarse.matches) return;
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      if (!busyNow) runCheck();
    }
  });
  var MAX = 20000;
  var CUT_NOTE = "Only the first 20,000 characters were kept.";
  msg.addEventListener("paste", function (e) {
    var t = e.clipboardData && e.clipboardData.getData("text");
    if (!t) return;
    var room = MAX - (msg.value.length - (msg.selectionEnd - msg.selectionStart));
    if (t.length > room) setTimeout(function () { pasteStatus.textContent = CUT_NOTE; }, 0);
  });

  if (!(navigator.clipboard && typeof navigator.clipboard.readText === "function")) {
    pasteBtn.hidden = true;
  }
  pasteBtn.addEventListener("click", function () {
    pasteStatus.textContent = "";
    navigator.clipboard.readText().then(function (t) {
      if (!t || !t.trim()) {
        pasteStatus.textContent = "The clipboard is empty. Copy the text message first, then try again.";
        return;
      }
      cancelCheck();
      clearResult();
      msg.value = t.length > MAX ? t.slice(0, MAX).replace(/[\uD800-\uDBFF]$/, "") : t;
      updateCount();
      markExample(null);
      msg.focus();
      pasteStatus.textContent = t.length > MAX ? CUT_NOTE + " Press “Check this text”." : "Pasted. Press “Check this text”.";
    }).catch(function () {
      pasteStatus.textContent = "Your browser did not allow pasting. Click in the box and press Ctrl+V (Cmd+V on a Mac).";
      msg.focus();
    });
  });

  clearBtn.addEventListener("click", function () {
    cancelCheck();
    msg.value = "";
    updateCount();
    clearResult();
    markExample(null);
    pasteStatus.textContent = "";
    msg.focus();
  });

  form.addEventListener("submit", function (e) { e.preventDefault(); if (!busyNow) runCheck(); });

  /* ---------- check ---------- */
  // aria-disabled, not the disabled attribute: a disabled button loses keyboard focus (WCAG 2.4.3).
  var busyNow = false;
  function setBusy(busy) {
    busyNow = busy;
    if (busy) checkBtn.setAttribute("aria-disabled", "true");
    else checkBtn.removeAttribute("aria-disabled");
    form.setAttribute("aria-busy", busy ? "true" : "false");
    if (!busy) { checkBtnText.textContent = "Check this text"; }
  }

  function cancelCheck() {
    requestId++;
    if (activeCheck) activeCheck.abort();
    activeCheck = null;
    setBusy(false);
  }

  function runCheck() {
    var text = msg.value;
    cancelCheck();
    clearResult();
    if (!text.trim()) {
      pasteStatus.textContent = "Paste or type a text message first.";
      msg.focus();
      return;
    }
    var id = requestId;
    var controller = new AbortController();
    activeCheck = controller;
    setBusy(true);
    var slow = setTimeout(function () { if (id === requestId) checkBtnText.textContent = "Checking…"; }, 150);
    var timeout = setTimeout(function () { controller.abort(); }, 12000);
    fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ text: text })
    }).then(function (response) {
      if (!response.ok) {
        var error = new Error("HTTP " + response.status);
        error.status = response.status;
        throw error;
      }
      return response.json();
    }).then(function (data) {
      if (id === requestId) render(data, text);
    }).catch(function (error) {
      if (id === requestId) renderError(error.status, error.name === "AbortError");
    }).finally(function () {
      clearTimeout(slow);
      clearTimeout(timeout);
      if (id === requestId) {
        activeCheck = null;
        setBusy(false);
      }
    });
  }

  function clearResult() {
    stopSpeaking();
    result.textContent = "";
    clearTimeout(announcementTimer);
    announce.textContent = "";
  }

  function say(text) {
    announce.textContent = "";
    clearTimeout(announcementTimer);
    announcementTimer = setTimeout(function () { announce.textContent = text; }, 60);
  }

  function renderError(status, timedOut) {
    clearResult();
    var text = "The checker could not connect. Your text is still here. Try again.";
    if (timedOut) text = "The check took too long. Your text is still here. Try again.";
    if (status === 422 || status === 413) text = "The checker could not read the text. Paste just the message and try again.";
    if (status === 503) text = "The checker is temporarily unavailable. Try again in a moment.";
    result.appendChild(h("div", { class: "error-box" }, [h("p", { text: text })]));
    say(text);
  }

  /* ---------- highlight trigger words inside the original message ---------- */
  var TOKEN_PATTERNS = {
    "[a web link]": /<URL>|\bhttps?:\/\/[^\s<>"]+|\bwww\.[^\s<>"]+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|info|co|uk|us|io|ly|me|xyz|top|site|online|link|app|biz|cc)\b(?:\/[^\s<>"]*)?/gi,
    "[a phone number]": /<PHONE_NUMBER>|\+?\d[\d ().-]{5,}\d/g,
    "[an email address]": /<EMAIL_ADDRESS>|[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}/gi,
    "[a money amount]": /[$£€₹]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:USD|EUR|GBP|dollars?|pounds?|euros?)\b/gi,
    "[a date or time]": /<DATE_TIME>|\b\d{1,2}[\/.:-]\d{1,2}(?:[\/.:-]\d{2,4})?\b/g,
    "[a number]": /\b\d+\b/g
  };
  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  function wordPattern(w) {
    try {
      return new RegExp("(?<![\\p{L}\\p{N}_])" + escapeRe(w) + "(?![\\p{L}\\p{N}_])", "giu");
    } catch (err) {
      return new RegExp("\\b" + escapeRe(w) + "\\b", "gi");
    }
  }

  var MAX_MARKS_PER_WORD = 20;
  function findRanges(text, words) {
    var ranges = [];
    words.forEach(function (w) {
      var re = Object.hasOwn(TOKEN_PATTERNS, w) ? new RegExp(TOKEN_PATTERNS[w].source, TOKEN_PATTERNS[w].flags) : wordPattern(w);
      var m, n = 0;
      while (n < MAX_MARKS_PER_WORD && (m = re.exec(text)) !== null) {
        if (m[0].length === 0) { re.lastIndex++; continue; }
        ranges.push([m.index, m.index + m[0].length]);
        n++;
      }
    });
    ranges.sort(function (a, b) { return a[0] - b[0] || b[1] - a[1]; });
    var merged = [];
    ranges.forEach(function (r) {
      var last = merged[merged.length - 1];
      if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
      else merged.push([r[0], r[1]]);
    });
    return merged;
  }

  /* Dataset tags such as <URL> are shown as plain tokens ("[link removed]"), never as raw markup. */
  var PLACEHOLDERS = {
    URL: "link removed", NAMED_ENTITY: "name removed", LOCATION: "place removed", PHONE_NUMBER: "phone number removed",
    EMAIL_ADDRESS: "email removed", DATE_TIME: "date removed"
  };
  function appendText(parent, str) {
    var re = /<([A-Z_]+)>/g, pos = 0, m;
    while ((m = re.exec(str)) !== null) {
      if (!PLACEHOLDERS[m[1]]) continue;
      if (m.index > pos) parent.appendChild(document.createTextNode(str.slice(pos, m.index)));
      parent.appendChild(h("span", { class: "ph", text: "[" + PLACEHOLDERS[m[1]] + "]" }));
      pos = m.index + m[0].length;
    }
    if (pos < str.length) parent.appendChild(document.createTextNode(str.slice(pos)));
    return parent;
  }
  function plainText(str) {
    return str.replace(/<([A-Z_]+)>/g, function (all, k) { return PLACEHOLDERS[k] ? "[" + PLACEHOLDERS[k] + "]" : all; });
  }

  function markedMessage(text, words) {
    var box = h("blockquote", { class: "msg-view", dir: "auto", tabindex: "0", role: "region", "aria-label": "Your message" });
    var pos = 0;
    findRanges(text, words).forEach(function (r) {
      if (r[0] > pos) appendText(box, text.slice(pos, r[0]));
      box.appendChild(appendText(h("mark"), text.slice(r[0], r[1])));
      pos = r[1];
    });
    if (pos < text.length) appendText(box, text.slice(pos));
    return box;
  }

  /* ---------- read aloud (Web Speech API: speech is made in the browser) ---------- */
  var speakBtn = null;
  function stopSpeaking() {
    if (canSpeak) window.speechSynthesis.cancel();
    setSpeakButton(false);
  }
  function setSpeakButton(on) {
    if (!speakBtn) return;
    speakBtn.setAttribute("aria-pressed", on ? "true" : "false");
    speakBtn.replaceChildren(icon(on ? "stop" : "speak"), h("span", { text: on ? "Stop reading" : "Read aloud" }));
  }
  function speak(text) {
    if (!canSpeak) return;
    var synth = window.speechSynthesis;
    if (synth.speaking || synth.pending) { stopSpeaking(); return; }
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.9;
    u.onend = u.onerror = function () { setSpeakButton(false); };
    setSpeakButton(true);
    synth.speak(u);
  }

  /* ---------- render ---------- */
  // Page-layer wording (app.py is not changed): every "What to do now" item starts with a verb.
  function render(d, text) {
    clearResult();
    if (!d || !d.tier) {
      pasteStatus.textContent = (d && d.headline) || "Paste or type a text message first.";
      return;
    }
    var tier = d.tier;
    var unsure = d.uncertain === true;
    var tierClass = unsure ? "verdict-unsure" : "verdict-" + tier.toLowerCase();
    var label = d.label;
    var green = tier === "GREEN";
    var headline = green ? "The sender is unverified." : d.headline || "";
    var greenNote = green ? "No warning signs found in the text. Before you sign, share account details or pay, verify the request through your usual app or a number you already trust." : "";
    var acts = d.actions || [];

    var actions = h("ol", null, acts.map(function (a) { return h("li", { text: a }); }));
    var spoken = (green ? "" : label + ". ") + headline + " " + (greenNote ? greenNote + " " : "") + (d.translation_note ? d.translation_note + " " : "") +
      "What to do now. " + acts.join(" ");

    speakBtn = null;
    var tools = null;
    if (canSpeak) {
      speakBtn = h("button", { type: "button", class: "btn btn-on-card", "aria-pressed": "false",
        onclick: function () { speak(spoken); } });
      setSpeakButton(false);
      tools = h("div", { class: "verdict-tools" }, [speakBtn]);
    }

    // The language / readability warning sits inside the verdict, right under the headline, so it is read first.
    var callout = d.translation_note ? h("div", { class: "callout" }, [icon("globe"), h("div", null, [
      h("p", { class: "callout-warn", text: d.translation_note }),
      d.translation_detail ? h("p", { class: "callout-detail", text: d.translation_detail }) : null
    ])]) : null;

    var showLabel = !green;
    var verdictHeading = h("h2", { id: "verdict-headline", class: "verdict-headline", tabindex: "-1",
      "aria-describedby": showLabel ? "verdict-context" : null, text: headline });
    var verdict = h("article", { class: "verdict " + tierClass, "data-tier": tier, "data-display": unsure ? "UNSURE" : null,
      "aria-labelledby": "verdict-headline" }, [
      h("div", { class: "verdict-head" }, [
        h("span", { class: "verdict-icon", "aria-hidden": "true" }, [icon(tier)]),
        h("div", null, [
          showLabel ? h("p", { id: "verdict-context", class: "verdict-label", text: label }) : null,
          verdictHeading
        ])
      ]),
      green ? h("div", { class: "callout" }, [h("p", { class: "callout-warn", text: greenNote })]) : null,
      callout,
      h("div", { class: "verdict-actions" }, [h("h3", { text: "What to do now" }), actions]),
      tools,
      h("div", { class: "verdict-links" }, [
        h("a", { href: "#msg", text: "Edit text", onclick: function (event) {
          if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
          event.preventDefault();
          msg.focus();
        } }),
        h("a", { href: "#recovery", onclick: openRecovery, text: "Already acted? Get recovery steps" })
      ])
    ]);
    result.appendChild(verdict);

    var words = d.top_words || [];
    var found = d.signals || [];
    var evidence = found.map(function (signal) { return signal.phrase; }).filter(Boolean);
    var marked = evidence.concat(words);
    var why = h("section", { class: "panel why" + (tier === "GREEN" ? " why-calm" : ""), "aria-labelledby": "why-title" }, [
      h("h3", { id: "why-title", text: "Why this result?" }),
      found.length ? null : h("p", { class: "why-reason", text: d.reason }),
      found.length ? h("div", { class: "why-signals" }, [
        h("ul", null, found.map(function (s) { return h("li", { text: s.label }); }))
      ]) : null,
      (marked.length || d.compare_2012) ? h("details", { class: "helpers" }, [
        h("summary", { text: "See the highlighted text" }),
        marked.length ? markedMessage(text, marked) : null,
        words.length ? h("p", { class: "why-legend", text: "Highlighted phrases include detected requests and words that influenced the model. Judge the full message and verify the sender separately." }) : null,
        d.compare_2012 ? h("p", { class: "why-legend" }, [h("strong", { text: "For comparison: " }), d.compare_2012]) : null
      ]) : null,
      d.note ? h("div", { class: "why-meta" }, [h("p", null, [h("strong", { text: "About this example: " }), plainText(d.note)])]) : null
    ]);
    result.appendChild(why);

    verdictHeading.focus({ preventScroll: true });
    verdict.scrollIntoView({ block: "start" });
  }

  /* ---------- examples ---------- */
  function markExample(id) {
    Array.prototype.forEach.call(exList.querySelectorAll(".ex-card"), function (b) {
      if (b.getAttribute("data-id") === id) b.setAttribute("aria-current", "true");
      else b.removeAttribute("aria-current");
    });
  }

  function runExample(example) {
    msg.value = example.text;
    updateCount();
    pasteStatus.textContent = "";
    markExample(example.id);
    runCheck();
  }

  function renderExamples(list) {
    var primary = list.find(function (example) { return example.id === "ex1"; });
    if (primary) {
      sampleButtons.forEach(function (button) {
        button.hidden = false;
        button.onclick = function () { runExample(primary); };
      });
    }
    exList.textContent = "";
    list.forEach(function (ex) {
      var kind = ex.kind === "REAL" ? "REAL" : "SYNTHETIC";
      var btn = h("button", { type: "button", class: "ex-card", "data-id": ex.id,
        "aria-label": kind + " example: " + ex.label + ". " + plainText(ex.source) + " Check this example.",
        onclick: function () { runExample(ex); } }, [
        h("span", { class: "ex-top" }, [
          h("span", { class: "tag " + (kind === "REAL" ? "tag-real" : "tag-synthetic"), text: kind }),
          h("span", { class: "ex-title", text: ex.label })
        ])
      ]);
      exList.appendChild(h("li", null, [btn]));
    });
  }

  fetch("/api/examples").then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }).then(function (list) {
    renderExamples(list);
  }).catch(function () {
    exList.appendChild(h("li", { class: "section-note", text: "Examples could not load. Check that server.py is running." }));
  });

  updateCount();
  window.addEventListener("pagehide", function () { cancelCheck(); stopSpeaking(); });

  // Small read-only hook for the browser checks (frontend-ship-guard step 3).
  window.scamDrift = {
    state: function () {
      var v = result.querySelector(".verdict");
      return { examples: exList.querySelectorAll(".ex-card").length, tier: v ? v.getAttribute("data-tier") : null,
               marks: result.querySelectorAll("mark").length, speech: canSpeak,
               chars: msg.value.length, revealDone: v ? !result.hasAttribute("data-enter") : null,
               display: v ? (v.getAttribute("data-display") || v.getAttribute("data-tier")) : null };
    }
  };
})();
