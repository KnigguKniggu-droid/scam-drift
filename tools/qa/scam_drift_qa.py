"""Local desktop playback transcription and project answer lookup for Scam Drift."""

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import wave
from pathlib import Path
from tkinter import simpledialog, ttk

ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "OpenCluely Q&A edition" / "resources" / "app" / "scam-drift-bridge.cjs"
if sys.platform == "darwin":
    BRIDGE = ROOT / ".mac-runtime" / "opencluely" / "scam-drift-bridge.cjs"
sys.path.insert(0, str(ROOT / "qa-audio-deps"))

import numpy as np
if sys.platform == "darwin":
    import sounddevice as mac_audio
else:
    import pyaudiowpatch as audio
import soxr
from vosk import KaldiRecognizer, Model, SetLogLevel

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    BRIDGE = ROOT / "OpenCluely Q&A edition" / "resources" / "app" / "scam-drift-bridge.cjs"

ANSWERS = (
    ("Alert fatigue", r"false positive|false alarm|ignore|tune out|cry wolf|alert fatigue", "That’s the risk. If your phone warns you about almost every real message, you’ll start tuning it out. Adding modern legitimate texts helped in our test, but the filter still flagged 427 out of 600. I’d want that much lower before people rely on it."),
    ("Main finding", r"main result|main finding|key result|headline|how many|how well|how accurate|compare|percent|accuracy|recall", "The old filter caught about three out of four real scam reports. Retraining caught about 97 percent, but it also flagged 597 of 600 legitimate texts in one inbox. That was the surprise. Teaching it what a normal text looks like today helped cut those false alarms."),
    ("Drift and causality", r"cause|causal|drift|source classifier|cross.era|changed over time|collection method|over time|auc", "We measured a gap across eras and data sources. We could not isolate the effect of time. A classifier could distinguish the source datasets with an AUC of 0.9893, so differences in how the texts were collected could explain part of the gap."),
    ("Deployment", r"deploy|ready|older adult|elderly|user test|real world|pilot|grandparent", "I’d start with a supervised pilot. The one thing I’d want to see is whether someone who gets a GREEN result still knows to check an unexpected request through their bank app or a number they already trust."),
    ("Missed scams", r"slip|miss|blind spot|wrong number|friendly|sign.off|portfolio|sophisticated|green", "The checker only sees the pasted message. A friendly opener can look ordinary before a later request for money. We also reproduced a miss on a portfolio sign-off message without a visible URL. A GREEN result leaves the sender unverified."),
    ("Data and leakage", r"training data|test data|dataset|duplicate|leak|split|benchmark|generaliz|representative|campaign|brands", "We used UCI SMS and modern reported scams, split dated reports by year, and removed exact duplicates after normalization. We checked near-template overlap. For a stronger benchmark, we’d hold out entire campaigns and use legitimate texts from many consented inboxes."),
    ("Model and explanation", r"what model|why.*model|how.*model|model work|logistic|tf.idf|explainability|highlight|explain.*warning|neural|bert|fine.tun", "The submitted study used word TF-IDF and logistic regression. The current demo adds character-level scoring, an English BERT-Tiny model, and request checks. It can show the phrase that matched a rule. A BERT-only warning does not identify an exact triggering phrase."),
    ("Language support", r"language|translate|spanish|portuguese|multilingual|english", "The current checker works best in English. In the submitted diagnostic, the 2012 filter flagged about 51% of non-English reports as written and about 70% on the dataset’s English translations. That comparison does not establish performance for any specific language."),
    ("Privacy", r"privacy|retain|store|share.*data|personal data|server|external|credential", "The demo sends the pasted text to the Scam Drift server for an in-memory check. The site never opens links or contacts the sender. We ask users to remove verification codes and account numbers before pasting."),
    ("Next steps", r"next|improve|future|more time|another week|expand|scale", "I’d collect recent, consented legitimate texts from more people and pair them with labeled scam reports. I’d hold out whole senders and campaigns, measure missed scams and false alarms separately, and test whether older adults act on the warnings."),
    ("Versions", r"after submission|deadline|submitted|live demo|latest version|built when", "The research results are from our submitted study. The website on screen is the version we are presenting today. The fine-tuned model was added after submission, and its evaluation uses a separate set of numbers."),
    ("Team and AI tools", r"team|william|did you use ai|chatgpt|claude|tools did|who built|contribution", "William and I built Scam Drift together. The repository credits Claude Code for implementation and documentation assistance, and credits ChatGPT, Gemini and Claude for feedback. We can walk through what we each worked on and explain our evaluation choices."),
    ("User experience", r"user|ux|interface|helps|accessib|why.*project|financial|act|what.*do", "A person can paste a suspicious text and see a warning, a reason, and one action to take. For example, if a message asks for a code, the checker directs the user to open their usual bank app independently."),
    ("Threshold and baselines", r"threshold|cost ratio|five to one|5 to 1|cutoff|baseline|heuristic|link.or.urgency", "We chose the cutoff on training folds. We treated a missed scam as five times as costly as a false alarm. That was a design choice. On the 1,080 newer scam reports, a link-or-urgency rule caught about 62 percent and the 2012 filter caught about 76 percent."),
    ("Precision and prevalence", r"precision|prevalence|positive predictive|how many warnings are right|how often.*warnings.*correct", "We didn’t measure real-world precision. The modern scam test contained only reported scams. To know how often a warning is right, we’d need a representative set of both genuine messages and scams, with their actual frequency."),
    ("Current checker evaluation", r"how.*(?:current|live).*perform|(?:current|live|web).*(?:accuracy|recall|precision|results|metric|benchmark|test)|how.*(?:bert|fine.tuned).*perform", "The current web checker warned on 611 of 927 English scam reports from unseen templates. It also warned on 173 of 608 legitimate texts in a separate held-out set. Those are test results for this version, and they show why we’re still cautious."),
    ("Synthetic examples", r"synthetic|benign twins|ai.written cases|made.up examples", "We used synthetic scam and legitimate look-alikes to test specific situations. They’re useful for finding failure modes, but they can’t tell us how often those cases happen in a real inbox. That’s why we also tested real scam reports and legitimate messages."),
    ("Three verdicts", r"red and yellow|red or yellow|red yellow|yellow and green|tiers|three colors|three colours|what does green mean|does green mean", "RED means stop and verify before you act. YELLOW means pause and double-check with someone you trust. GREEN means the checker saw no clear warning signs in that text. It still can’t verify who sent it."),
    ("The one-inbox study", r"one person.?s inbox|one inbox|india inbox|trust.*(?:sample|inbox)|held.out brands|606 legitimate|why.*(?:india|mozambique)", "We held out 600 texts by brand, so the model hadn’t seen those brands in that training sample. They still came from one person’s inbox. That’s enough to show what happened in this test, and we’d need many more inboxes to see how common it is."),
    ("Prototype and competitors", r"competitor|different from|spam filter already|google messages|why another|existing scam|what makes.*different", "Our focus is the decision after a suspicious text arrives. We show the request that raised concern and an action the person can take. The research also measures false alarms when training data changes. We haven’t benchmarked against commercial blockers."),
    ("Live demo performance", r"latency|how fast|scalab|throughput|concurrent|performance under load|load test|512 requests", "A local load test completed all 512 requests with eight workers. One rehearsal measured a 95th-percentile response time of 280 milliseconds. That’s the result on this machine, and we haven’t tested production-scale traffic."),
    ("Portfolio sign-off test", r"sign.off|portfolio|financial impersonation|finance suite|formal finance", "In that test, the portfolio sign-off text came back GREEN once we removed the visible link. With the link it came back RED. That example shows why GREEN can’t establish who sent a message."),
)


PATTERNS = [re.compile(rf"\b(?:{pattern})\w*\b") for _, pattern, _ in ANSWERS]
QUESTION = re.compile(r"^(?:(?:and|so|okay|ok|well|first|then|yeah|right)[\s,:]+)*(?:how|what|why|when|where|which|who|did|do|does|is|are|would|could|can|have|has|will|should|tell|explain|walk|compare|describe|define|give)\b", re.I)
QUESTION_CONTEXT = re.compile(r"^(?:(?:my|our|the first|the next) question is|i have (?:a|one) (?:quick |short )?question|(?:i|we) (?:wonder|want to know|would like to know))\s*[:,]?\s*(?:about\s+)?", re.I)
QA = r"(?:q\s*(?:and|n|&)?\s*a|questions?(?:\s+and\s+answers?)?|judge\w*'?\s+questions?)"
HANDOFF = re.compile(
    rf"\b(?:(?:start|begin|open(?: for)?|move (?:on )?to|go (?:ahead )?(?:to|with)|get to|turn (?:it )?over (?:to|for)|take|hear|switch to)"
    rf"\s+(?:(?:the|our|some|your|a few|judging|the judges|judges for|the judges for)\s+)*{QA}"
    rf"|{QA}\s+(?:can\s+(?:start|begin)|(?:is\s+)?(?:starting|begins?|starts?)\s+now|(?:starts?|begins?))"
    rf"|open (?:up )?(?:the )?floor (?:for|to)\s+{QA}|(?:time|ready|now|the floor is open) for (?:the )?{QA}"
    rf"|judges[, ]+(?:over to you|the floor is yours)|(?:over to|turn it over to) (?:our |the )?judges"
    rf"|hear from (?:our |the )?judges|do (?:our |the )?judges have any questions|(?:first|next) question from (?:a|the) judges?"
    rf"|you (?:can|may) ask (?:your|the) (?:first )?question|judges[, ]+(?:please )?go ahead(?: with (?:your|the) (?:first )?question)?"
    rf"|(?:judges|judging panel)[, ]+(?:(?:you can|can|may|please|go ahead and)\s+)+(?:ask|start|begin)(?:\s+(?:your|the)\s+(?:first\s+)?questions?)?)\b",
    re.I,
)
DEFERRED = re.compile(r"\b(?:after|before|once|when|later|tomorrow|next week|yet|seconds left|minutes left|followed by|in (?:a |[a-z0-9]+ )?(?:minutes?|seconds?)|practice|rehears\w*)\b", re.I)
NEGATED_CUE = re.compile(r"\b(?:won't|don't|cannot|can't|not|never)\b", re.I)
FUTURE_CUE = re.compile(r"\b(?:we will|we'll|you will|you'll|going to|plan to)\b", re.I)
LEADING_QUESTION = re.compile(r"\b(?:how|what|why|when|where|which|who|would you|could you|can you|did you|do you|does it|is it|are you|tell us)\b", re.I)


def looks_like_question(text):
    text = QUESTION_CONTEXT.sub("", text.strip())
    return len(text.split()) >= 2 and (text.endswith("?") or bool(QUESTION.search(text)))


def handoff(text):
    """Return the optional first question after a clear host cue, or None."""
    clean = re.sub(r"\bq\s*&\s*a\b", "q and a", text.replace("’", "'"), flags=re.I)
    cue = HANDOFF.search(clean)
    if cue is None:
        return None
    before, after = clean[:cue.start()], clean[cue.end():]
    if re.search(r"\b(?:what we will say|what we should say|the cue is|example cue)\b", before, re.I):
        return None
    start = LEADING_QUESTION.search(after)
    if start and start.group().lower() in {"when", "where"} and not re.match(r"\s*(?:did|do|does|would|could|can|will|is|are)\b", after[start.end():], re.I):
        start = None
    before = re.split(r"[.!;:]\s+|,\s+(?=let's|let us)", before)[-1]
    cue_context = before + " " + (after[:start.start()] if start else after)
    if (DEFERRED.search(cue_context) or NEGATED_CUE.search(cue_context)
            or re.search(r"\b(?:let's wait|hold off|as soon as|still running|said|what we will say)\b", cue_context, re.I)
            or re.search(r"\b(?:are we|are you|can we|can you|should we|could we|could you|will we)\b", before, re.I)
            or FUTURE_CUE.search(before) and not re.search(r"\bnow\b", cue_context, re.I)
            and not re.search(r"\bturn (?:it )?over\b", cue.group(), re.I)):
        return None
    return after[start.start():].strip() if start else ""


class QuestionGate:
    def __init__(self):
        self.active = False
        self.previous = ""
        self.previous_at = 0.0

    def consume(self, kind, text):
        activated = False
        if not self.active:
            if kind != "final":
                return False, None
            tail = handoff(text)
            if tail is None:
                return False, None
            self.active = activated = True
            text = tail
        if not looks_like_question(text):
            return activated, None
        if kind == "final":
            normalized = re.sub(r"[^a-z0-9 ]", "", text.lower())
            now = time.monotonic()
            if normalized == self.previous and now - self.previous_at < 5:
                return activated, None
            self.previous, self.previous_at = normalized, now
        return activated, text


def match_answer(transcript):
    normalized = transcript.lower()
    for title, words in (
        ("Precision and prevalence", r"\b(?:precision|prevalence|population|base rate)\b"),
        ("Current checker evaluation", r"\b(?:current|live|web|bert|fine.tuned)\b.*\b(?:perform\w*|accuracy|recall|scores?|benchmark|results?)\b|\b(?:perform\w*|accuracy|recall|scores?|benchmark|results?)\b.*\b(?:current|live|web|bert|fine.tuned)\b"),
        ("Threshold and baselines", r"\b(?:threshold|cutoff|5 to 1|five to one|link.or.urgency)\b"),
        ("Three verdicts", r"\bgreen\b.*\b(?:mean|safe|trust|sender|verify)|\b(?:mean|safe|trust|sender|verify)\b.*\bgreen\b"),
        ("The one-inbox study", r"\b(?:one person|one inbox|india inbox)\b"),
        ("Synthetic examples", r"\b(?:synthetic|benign twins)\b"),
    ):
        if re.search(words, normalized):
            return next(i for i, (name, _, _) in enumerate(ANSWERS) if name == title)
    ranked = sorted(
        ((sum(len(x.group().split()) for x in pattern.finditer(normalized)), index)
         for index, pattern in enumerate(PATTERNS)),
        key=lambda pair: (-pair[0], pair[1]),
    )
    score, index = ranked[0]
    return index if score else None


def prepared_answer(index, question):
    text = question.lower()
    if index == 1 and re.search(r"how many.*scam", text) and not re.search(r"legitimate|genuine|false alarm|false positive", text):
        if re.search(r"\b(?:2012|old|older|legacy|original)\s+(?:filter|model)\b", text) or "old filter" in text:
            return "The old filter caught 817 of the 1,080 newer scam reports. That’s about three out of four."
        if re.search(r"after.*(?:legitimate|genuine)", text):
            return "With modern legitimate messages added to training, the filter caught 1,036 of the 1,080 newer scam reports. That’s 95.93 percent."
        if "retrain" in text:
            return "Retraining on modern scams caught 1,043 of the 1,080 newer scam reports. That’s 96.57 percent."
    if (index in (0, 1) or ANSWERS[index][0] == "The one-inbox study") and re.search(r"false alarm|false positive|legitimate|genuine", text) and re.search(r"how many|what (?:was|were) the false alarm", text):
        if re.search(r"\b(?:2012|old|older|legacy|original) (?:filter|model)\b", text):
            return "The 2012 filter flagged 546 out of 600 legitimate messages from the held-out brands in that inbox. That’s 91 percent."
        if "synthetic" in text:
            return "The filter retrained on modern scams flagged 59 of the 60 synthetic legitimate examples. We tested real inbox messages separately."
        if re.search(r"\bafter\b|(?:adding|added)(?: modern)? legitimate", text) and not re.search(r"\bbefore\b", text):
            return "After we added modern legitimate texts to training, it flagged 427 out of 600 legitimate messages from that inbox. That’s about 71 percent."
        return "Retraining on modern scams flagged 597 out of 600 legitimate messages from that inbox. That’s 99.5 percent."
    if ANSWERS[index][0] == "Synthetic examples" and re.search(r"how many|what (?:was|were) the false alarm", text):
        if re.search(r"\b(?:2012|old|older|legacy|original)\b", text):
            return "The 2012 filter flagged 31 of 60 synthetic legitimate messages in the submitted study."
        if re.search(r"\bafter\b.*(?:legitimate|genuine)", text):
            return "The filter trained with modern legitimate texts flagged 53 of 60 synthetic legitimate messages in the submitted study."
        return "The filter retrained on modern scams flagged 59 of the 60 synthetic legitimate examples. We tested real inbox messages separately."
    return ANSWERS[index][2]


def checked_fact(question):
    text = question.lower()
    if re.search(r"portfolio|sign.off|signature language", text) and re.search(r"no (?:visible )?(?:link|url)|without|redact|remove|missing", text):
        return "The portfolio sign-off example came back GREEN when we removed its visible URL. With the original visible URL, it came back RED. A GREEN result leaves the sender unverified."
    if re.search(r"finance (?:suite|test|regression)|financial (?:tests|cases)", text) and re.search(r"miss|flag|catch|caught|how many|false positive|false alarm", text):
        return "In that targeted finance suite, we flagged 6 of the 13 warning cases and missed 7. We also falsely flagged 1 of 12 legitimate controls. Those are targeted test cases."
    if re.search(r"\buci\b", text) and re.search(r"\b(?:2012|old|legacy|original)\b", text) and re.search(r"false alarm|false positive|falsely flag", text):
        return "The 2012 word model falsely flagged 8 of 903 legitimate UCI test messages, about 0.89 percent. The separate modern inbox test had a much higher false-alarm rate."
    if re.search(r"how many|how much|rate|percent|count|before and after", text) and re.search(r"false alarm|false positive|falsely flag", text) and re.search(r"inbox|\b600\b|adding (?:modern )?(?:legitimate|genuine)|modern.scam.only", text) and not re.search(r"synthetic|mozambique|portuguese|current|live|bert|web|uci|population|prevalence|threshold", text):
        if "before and after" in text:
            return "The modern-scam-only model flagged 597 out of 600 genuine texts. After adding modern legitimate examples to training, it flagged 427 out of 600. That dropped from 99.5 to 71.17 percent."
        if re.search(r"\b(?:2012|old|older|legacy|original)\b", text):
            return "The 2012 filter falsely flagged 546 of 600 held-out legitimate texts from that inbox. That’s 91 percent."
        if re.search(r"\bafter\b|(?:adding|added)(?: modern)? (?:legitimate|genuine)", text) and "before" not in text:
            return "After adding modern legitimate training texts, we falsely flagged 427 of 600 test messages from that inbox. That’s 71.17 percent."
        return "The modern-scam-only model falsely flagged 597 of 600 held-out legitimate messages from that inbox. That’s 99.5 percent."
    return None


class OpenCluelyBridge:
    def __init__(self, emit):
        self.emit = emit
        self.process = None
        self.session_key = ""

    def has_key(self):
        if self.session_key or os.environ.get("GEMINI_API_KEY"):
            return True
        path = (Path.home() / "Library" / "Application Support" / "opencluely" / ".env"
                if sys.platform == "darwin" else Path(os.environ.get("APPDATA", ROOT)) / "opencluely" / ".env")
        try:
            match = re.search(r"^\s*GEMINI_API_KEY\s*=\s*([^\r\n]+)", path.read_text(encoding="utf-8-sig"), re.M)
            value = match.group(1).strip().strip("'\"") if match else ""
            return bool(value and value != "your-api-key-here" and not value.startswith("#"))
        except (OSError, UnicodeError):
            return False

    def node_runtime(self):
        bundled = ROOT / "node.exe"
        return str(bundled) if bundled.is_file() else shutil.which("node")

    def ask(self, request_id, question):
        if self.process is None or self.process.poll() is not None:
            node = self.node_runtime()
            if not node or not BRIDGE.is_file():
                raise RuntimeError("Node.js or the answer service is missing.")
            if not self.has_key():
                raise RuntimeError("Add a Gemini key to generate answers.")
            env = os.environ.copy()
            if self.session_key:
                env["GEMINI_API_KEY"] = self.session_key
            self.process = subprocess.Popen(
                [node, str(BRIDGE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=env,
            )
            threading.Thread(target=self.read, args=(self.process,), daemon=True).start()
        self.process.stdin.write(json.dumps({"id": request_id, "question": question}) + "\n")
        self.process.stdin.flush()

    def read(self, process):
        for line in process.stdout:
            if line.startswith('{"id":'):
                try:
                    self.emit("cloud", json.loads(line))
                except ValueError:
                    continue
        self.emit("cloud_closed", process)

    def close(self):
        if self.process is not None:
            process, self.process = self.process, None
            if process.poll() is None:
                process.terminate()


def listen(model, stop, emit, ready=None, microphone=False):
    if sys.platform == "darwin":
        return listen_mac(model, stop, emit, ready, microphone)
    with audio.PyAudio() as device:
        endpoint = device.get_default_wasapi_device(d_out=False) if microphone else device.get_default_wasapi_loopback()
        rate = round(endpoint["defaultSampleRate"])
        channels = int(endpoint["maxInputChannels"])
        resampler = soxr.ResampleStream(rate, 16000, 1, dtype="int16")
        recognizer = KaldiRecognizer(model, 16000)
        chunks = queue.Queue(maxsize=20)

        def capture(raw, _frames, _time, _status):
            try:
                chunks.put_nowait(raw)
            except queue.Full:
                pass
            return None, audio.paContinue

        with device.open(format=audio.paInt16, channels=channels, rate=rate, input=True,
                         input_device_index=endpoint["index"], frames_per_buffer=rate // 10,
                         stream_callback=capture):
            emit("status", f"{'Mic rehearsal' if microphone else 'Listening to'} {endpoint['name']}")
            if ready:
                ready.set()
            while not stop.is_set():
                try:
                    raw = chunks.get(timeout=0.2)
                except queue.Empty:
                    continue
                samples = np.frombuffer(raw, np.int16).reshape(-1, channels)
                mono = samples.astype(np.int32).mean(axis=1).astype(np.int16)
                packet = resampler.resample_chunk(mono).tobytes()
                if not packet:
                    continue
                if recognizer.AcceptWaveform(packet):
                    text = json.loads(recognizer.Result()).get("text", "")
                    if text:
                        emit("final", text)
                else:
                    text = json.loads(recognizer.PartialResult()).get("partial", "")
                    if text:
                        emit("partial", text)


def listen_mac(model, stop, emit, ready, microphone):
    devices = mac_audio.query_devices()
    if microphone:
        index = int(mac_audio.default.device[0])
    else:
        index = next((i for i, device in enumerate(devices)
                      if device["max_input_channels"] >= 2 and "blackhole 2ch" in device["name"].lower()), -1)
    if index < 0:
        raise RuntimeError("No microphone found." if microphone else
                           "BlackHole 2ch is missing. Follow MAC_SETUP.md or type a question.")
    endpoint = devices[index]
    rate = round(endpoint["default_samplerate"])
    channels = 1 if microphone else 2
    resampler = soxr.ResampleStream(rate, 16000, 1, dtype="int16")
    recognizer = KaldiRecognizer(model, 16000)
    chunks = queue.Queue(maxsize=20)

    def capture(raw, _frames, _time, _status):
        try:
            chunks.put_nowait(bytes(raw))
        except queue.Full:
            return

    with mac_audio.RawInputStream(device=index, samplerate=rate, channels=channels,
                                  dtype="int16", blocksize=rate // 10, callback=capture):
        emit("status", f"{'Mic rehearsal' if microphone else 'Listening to'} {endpoint['name']}")
        if ready:
            ready.set()
        while not stop.is_set():
            try:
                raw = chunks.get(timeout=0.2)
            except queue.Empty:
                continue
            samples = np.frombuffer(raw, np.int16).reshape(-1, channels)
            mono = samples.astype(np.int32).mean(axis=1).astype(np.int16)
            packet = resampler.resample_chunk(mono).tobytes()
            if not packet:
                continue
            final = recognizer.AcceptWaveform(packet)
            result = json.loads(recognizer.Result() if final else recognizer.PartialResult())
            if text := result.get("text" if final else "partial"):
                emit("final" if final else "partial", text)


def test_loopback(model, wav_path, expected):
    import time
    import winsound

    stop, ready = threading.Event(), threading.Event()
    observed = queue.Queue()
    with wave.open(str(wav_path)) as fixture:
        duration = fixture.getnframes() / fixture.getframerate()
    worker = threading.Thread(target=listen, args=(model, stop, lambda k, v: observed.put((k, v)), ready), daemon=True)
    worker.start()
    first_match = None
    try:
        if not ready.wait(5):
            raise RuntimeError("Windows did not open a WASAPI loopback stream")
        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        started = time.perf_counter()
        while time.perf_counter() - started < 15:
            try:
                kind, value = observed.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "status":
                print(value, flush=True)
            index = match_answer(value) if kind in {"partial", "final"} else None
            if first_match is None and index == expected and (kind == "final" or len(value.split()) >= 4):
                first_match = time.perf_counter() - started
            if kind == "final" and index == expected:
                print(f"Transcribed: {value}")
                print(f"First answer {first_match:.2f}s from start; final {time.perf_counter() - started:.2f}s; audio {duration:.2f}s; topic {ANSWERS[index][0]}")
                return
        raise RuntimeError(f"Playback did not produce the expected topic {ANSWERS[expected][0]}. Check the default playback device and try again.")
    finally:
        stop.set()
        winsound.PlaySound(None, 0)
        worker.join(2)
        if worker.is_alive():
            raise RuntimeError("Loopback capture did not stop")


def test_handoff_audio(model, paths):
    import winsound

    stop, ready = threading.Event(), threading.Event()
    observed = queue.Queue()
    worker = threading.Thread(target=listen, args=(model, stop, lambda k, v: observed.put((k, v)), ready), daemon=True)
    worker.start()
    gate = QuestionGate()
    expected = (None, None, "handoff", 0, 2, 3, None, 9)
    try:
        if not ready.wait(5):
            raise RuntimeError("Windows did not open a playback stream")
        for index, (file, wanted) in enumerate(zip(paths, expected)):
            winsound.PlaySound(str(file), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            deadline = time.monotonic() + 12
            first_answer = None
            started = time.monotonic()
            while time.monotonic() < deadline:
                try:
                    kind, heard = observed.get(timeout=0.5)
                except queue.Empty:
                    continue
                if kind == "status":
                    print(heard, flush=True)
                if kind not in {"partial", "final"}:
                    continue
                activated, question = gate.consume(kind, heard)
                topic = match_answer(question) if question else None
                if topic is not None and first_answer is None:
                    first_answer = time.monotonic() - started
                if kind == "final":
                    result = "handoff" if activated else topic
                    if result is None and wanted is not None:
                        continue
                    assert result == wanted, (index, wanted, result, heard)
                    assert index >= 2 or not gate.active, heard
                    print(json.dumps({"case": index, "heard": heard, "matched": result,
                                      "first_answer_s": round(first_answer, 2) if first_answer else None}), flush=True)
                    break
            else:
                raise RuntimeError(f"Playback case {index} did not produce a final transcript")
    finally:
        stop.set()
        winsound.PlaySound(None, 0)
        worker.join(2)
        if worker.is_alive():
            raise RuntimeError("Loopback capture did not stop")


def open_window(auto_arm=True):
    window = tk.Tk()
    window.title("Scam Drift | Audio Q&A")
    window.geometry("736x510")
    window.minsize(540, 365)
    paper, ink, muted, green = "#efeee8", "#152420", "#4b5f57", "#1b5345"
    window.configure(background=paper)
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure("TFrame", background=paper)
    style.configure("TLabel", background=paper, foreground=ink, font=("Segoe UI", 10))
    style.configure("Muted.TLabel", foreground=muted)
    style.configure("TButton", padding=(12, 7), font=("Segoe UI", 10))
    style.configure("Primary.TButton", background=green, foreground="#ffffff", bordercolor=green)
    style.map("Primary.TButton", background=[("disabled", "#6f8178"), ("active", "#256653")],
              foreground=[("disabled", "#ffffff"), ("active", "#ffffff")])
    for name, bg, fg in (("Paused", "#e1e2da", ink), ("Armed", "#f0e3c7", "#5d441c"), ("Active", "#dcebe1", "#16423b")):
        style.configure(f"{name}.TLabel", background=bg, foreground=fg, padding=(9, 5), font=("Segoe UI", 10, "bold"))
    style.configure("TCheckbutton", background=paper, foreground=ink, font=("Segoe UI", 10))
    style.map("TCheckbutton", background=[("active", paper)])
    panel = ttk.Frame(window, padding=(22, 16))
    panel.pack(fill="both", expand=True)
    header = ttk.Frame(panel)
    header.pack(fill="x", pady=(0, 10))
    ttk.Label(header, text="Scam Drift Q&A", font=("Georgia", 23)).pack(side="left")
    status = tk.StringVar(value="Listening is off.")
    phase = tk.StringVar(value="Paused")
    phase_badge = ttk.Label(header, textvariable=phase, style="Paused.TLabel")
    phase_badge.pack(side="right", padx=(8, 0))

    def stage(label, appearance):
        phase.set(label)
        phase_badge.configure(style=f"{appearance}.TLabel")

    caption = tk.StringVar(value="Waiting for a question")
    answer = tk.StringVar(value="Arm before presenting. Answers will start when the host opens Q&A.")
    shown_answer = tk.StringVar(value=answer.get())
    entry_value = tk.StringVar()
    connection = tk.StringVar()
    cloud_answer = tk.StringVar()
    answer_state = tk.StringVar(value="")
    controls = ttk.Frame(panel)
    controls.pack(fill="x", pady=(0, 4))
    events = queue.Queue()
    stop = threading.Event()
    worker = None
    pending = None
    newest = None
    sequence = 0
    gate = QuestionGate()
    draft_hidden = False
    microphone_mode = False

    def emit(kind, value):
        events.put((kind, value))

    bridge = OpenCluelyBridge(emit)

    def update_connection():
        if bridge.has_key():
            connection.set("Question text and the project brief go to Google Gemini. Audio stays on this PC.")
            key_button.configure(text="Change Gemini key")
        else:
            connection.set("Add a Gemini key for generated answers. Project notes are available now.")
            key_button.configure(text="Add Gemini key")

    def set_key():
        nonlocal pending, newest
        value = simpledialog.askstring("Gemini connection", "Enter your own Gemini API key. It stays in memory for this session.",
                                       show="*", parent=window)
        if value and value.strip():
            pending = newest = None
            bridge.close()
            bridge.session_key = value.strip()
            update_connection()

    def show_answer(*_):
        draft = cloud_answer.get().strip()
        shown_answer.set(draft or answer.get())

    answer.trace_add("write", show_answer)
    cloud_answer.trace_add("write", show_answer)

    def show_no_ai(message):
        cloud_answer.set("")
        if answer.get() == "Waiting for an answer to this question.":
            answer.set("No matching project note. You can retry or select a topic below.")
        answer_state.set(message)

    def select(index, text=""):
        if index is not None:
            topics.current(index)
            answer.set(prepared_answer(index, text))

    def ask(text):
        nonlocal pending, newest, sequence, draft_hidden
        if fact := checked_fact(text):
            pending = newest = None
            bridge.close()
            draft_hidden = False
            cloud_answer.set("")
            answer.set(fact)
            answer_state.set("Verified project result")
            return
        if pending is not None:
            newest = text
            cloud_answer.set("")
            answer_state.set("Preparing an answer…")
            return
        sequence += 1
        pending = sequence
        draft_hidden = False
        cloud_answer.set("")
        answer_state.set("Preparing an answer…")
        try:
            bridge.ask(sequence, text)
        except (OSError, RuntimeError) as error:
            pending = None
            show_no_ai(str(error) if isinstance(error, RuntimeError) else "AI unavailable")
        else:
            window.after(8500, lambda current=sequence: expire(current))

    def expire(request_id):
        nonlocal pending, newest
        if pending == request_id:
            next_question = newest
            pending = None
            newest = None
            bridge.close()
            show_no_ai("AI timed out")
            if next_question:
                ask(next_question)

    def run():
        try:
            if not hasattr(run, "model"):
                run.model = Model(str(ROOT / "vosk-model-small-en-us-0.15"))
            if not stop.is_set():
                listen(run.model, stop, emit, microphone=microphone_mode)
        except Exception as error:
            emit("status", f"Audio unavailable: {error}")
        finally:
            emit("stopped", "")

    def toggle(microphone=False):
        nonlocal worker, pending, newest, microphone_mode
        if worker and worker.is_alive():
            stop.set()
            pending = newest = None
            bridge.close()
            cloud_answer.set("")
            answer_state.set("")
            button.configure(text="Stopping…", state="disabled")
            return
        stop.clear()
        microphone_mode = microphone
        gate.active, gate.previous = microphone, ""
        stage("Mic rehearsal", "Active") if microphone else stage("Armed · waiting for Q&A", "Armed")
        caption.set("Ask a question out loud" if microphone else "Waiting for the host’s handoff")
        answer.set("Say a practice judge question." if microphone else "Listening to headset playback. Answers start after the host’s Q&A cue.")
        cloud_answer.set("")
        answer_state.set("")
        status.set("Opening microphone…" if microphone else "Opening playback audio…")
        button.configure(text="Stop listening")
        rehearsal_button.configure(state="disabled")
        worker = threading.Thread(target=run, daemon=True)
        worker.start()

    def activate():
        nonlocal pending, newest
        if worker and worker.is_alive() and stop.is_set():
            return
        if not worker or not worker.is_alive():
            toggle()
        gate.active = True
        pending = newest = None
        bridge.close()
        stage("Q&A active", "Active")
        caption.set("Waiting for a judge’s question")
        answer.set("The next question will appear here.")
        cloud_answer.set("")
        answer_state.set("")

    def process():
        nonlocal pending, newest, draft_hidden
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "stopped":
                button.configure(text="Arm for Q&A", state="normal")
                rehearsal_button.configure(state="normal")
                stage("Paused", "Paused")
                if stop.is_set():
                    status.set("Paused.")
            elif kind == "status":
                status.set(value)
            elif kind == "cloud":
                if value["id"] != pending:
                    continue
                if "delta" in value:
                    if newest is None and not draft_hidden:
                        cloud_answer.set(cloud_answer.get() + value["delta"])
                else:
                    if newest is not None:
                        pending = None
                        text, newest = newest, None
                        ask(text)
                        continue
                    if draft_hidden:
                        pending = None
                        continue
                    if "response" in value and value["response"].strip():
                        cloud_answer.set(value["response"].strip())
                        answer_state.set("AI answer · check the facts before speaking")
                    else:
                        show_no_ai("AI unavailable")
                    pending = None
            elif kind == "cloud_closed":
                if value is bridge.process and pending is not None:
                    pending = None
                    newest = None
                    show_no_ai("AI unavailable")
            else:
                if stop.is_set():
                    continue
                activated, question = gate.consume(kind, value)
                if activated:
                    stage("Q&A active · host cue heard", "Active")
                    caption.set("Waiting for a judge’s question")
                    answer.set("The next question will appear here.")
                if not gate.active:
                    continue
                if question is None:
                    continue
                caption.set(question)
                if kind == "partial" and not draft_hidden:
                    draft_hidden = True
                    cloud_answer.set("")
                    answer_state.set("Listening to the question…")
                index = match_answer(question)
                if index is not None:
                    select(index, question)
                elif kind == "final":
                    answer.set("Waiting for an answer to this question.")
                if kind == "final":
                    ask(question)
        window.after(70, process)

    def typed(_event=None):
        question = entry_value.get().strip()
        if question:
            caption.set(question)
            cloud_answer.set("")
            index = match_answer(question)
            if index is None:
                answer.set("Waiting for an answer to this question.")
            else:
                select(index, question)
            ask(question)

    button = ttk.Button(controls, text="Arm for Q&A", command=toggle, style="Primary.TButton")
    button.pack(side="left")
    ttk.Button(controls, text="Start Q&A now", command=activate).pack(side="left", padx=(8, 0))
    rehearsal_button = ttk.Button(controls, text="Test with mic", command=lambda: toggle(microphone=True))
    rehearsal_button.pack(side="left", padx=(8, 0))
    ttk.Label(panel, textvariable=status, style="Muted.TLabel").pack(fill="x", pady=(1, 11))

    fallback = ttk.Frame(panel)
    fallback.pack(side="bottom", fill="x", pady=(10, 0))
    ttk.Label(fallback, text="Quick topic", style="Muted.TLabel").pack(side="left", padx=(0, 7))
    topics = ttk.Combobox(fallback, values=[name for name, _, _ in ANSWERS], state="readonly", width=18)
    topics.pack(side="left", padx=(0, 12))
    def quick_topic(_event):
        nonlocal pending, newest
        pending = newest = None
        bridge.close()
        cloud_answer.set("")
        answer_state.set("From project notes")
        select(topics.current())

    topics.bind("<<ComboboxSelected>>", quick_topic)
    ttk.Label(fallback, text="Type a question", style="Muted.TLabel").pack(side="left", padx=(0, 7))
    entry = ttk.Entry(fallback, textvariable=entry_value)
    entry.pack(side="left", fill="x", expand=True)
    entry.bind("<Return>", typed)
    ttk.Button(fallback, text="Ask", command=typed).pack(side="left", padx=(7, 0))

    content = ttk.Frame(panel)
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(3, weight=1, minsize=110)
    ttk.Label(content, text="Question heard", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
    heard = ttk.Label(content, textvariable=caption, style="Muted.TLabel", justify="left")
    heard.grid(row=1, column=0, sticky="ew", pady=(3, 10))
    answer_header = ttk.Frame(content)
    answer_header.grid(row=2, column=0, sticky="ew", pady=(0, 5))
    ttk.Label(answer_header, text="Suggested answer", font=("Segoe UI", 10, "bold")).pack(side="left")
    ttk.Label(answer_header, textvariable=answer_state, style="Muted.TLabel").pack(side="right")

    def answer_box(row, variable, background, font):
        border = tk.Frame(content, background=background, highlightbackground="#d5ded1", highlightthickness=1)
        border.grid(row=row, column=0, sticky="nsew")
        body = tk.Text(border, wrap="word", height=1, borderwidth=0, highlightthickness=0, font=font,
                       padx=13, pady=9, background=background, foreground=ink, cursor="arrow", state="disabled")
        scroll = ttk.Scrollbar(border, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        body.pack(side="left", fill="both", expand=True)

        def update(*_):
            body.configure(state="normal")
            body.delete("1.0", "end")
            body.insert("1.0", variable.get())
            body.configure(state="disabled")

        variable.trace_add("write", update)
        update()

    answer_box(3, shown_answer, "#fbfaf5", ("Segoe UI", 16, "bold"))
    connection_row = ttk.Frame(content)
    connection_row.grid(row=4, column=0, sticky="ew", pady=(10, 0))
    connection_row.columnconfigure(0, weight=1)
    connection_label = ttk.Label(connection_row, textvariable=connection, style="Muted.TLabel", justify="left")
    connection_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
    key_button = ttk.Button(connection_row, command=set_key)
    key_button.grid(row=0, column=1, sticky="e")
    update_connection()

    def resize(event):
        if event.widget == window:
            width = max(460, event.width - 48)
            heard.configure(wraplength=width)
            connection_label.configure(wraplength=width - 145)

    window.bind("<Configure>", resize)
    window.protocol("WM_DELETE_WINDOW", lambda: (stop.set(), bridge.close(), window.destroy()))
    window.after(70, process)
    if auto_arm:
        window.after(250, lambda: toggle() if worker is None else None)
    window.mainloop()


def main():
    SetLogLevel(-1)
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-playback", type=Path)
    parser.add_argument("--test-handoff", type=Path, nargs=8)
    parser.add_argument("--test-log", type=Path)
    parser.add_argument("--paused", action="store_true", help="Open the panel without listening")
    parser.add_argument("--expected-topic", type=int, choices=range(len(ANSWERS)), default=0)
    args = parser.parse_args()
    if args.test_handoff or args.test_playback:
        from contextlib import redirect_stdout
        output = args.test_log.open("w", encoding="utf-8") if args.test_log else sys.stdout
        try:
            with redirect_stdout(output):
                try:
                    model = Model(str(ROOT / "vosk-model-small-en-us-0.15"))
                    if args.test_handoff:
                        test_handoff_audio(model, args.test_handoff)
                    else:
                        test_loopback(model, args.test_playback, args.expected_topic)
                except (OSError, RuntimeError, AssertionError, wave.Error) as error:
                    print(f"Playback check failed: {error}", flush=True)
                    return 1
        finally:
            if args.test_log:
                output.close()
    else:
        open_window(auto_arm=not args.paused)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
