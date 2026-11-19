"""UI regression check for app.py (frontend-ship-guard steps 1 and 3).

Usage: python tools/ui_check.py <label>   (app must be running on 127.0.0.1:7860)
Writes qa/ui/<label>/state.json (predict() outputs for every example + empty input, element ids present in the
served page) and headless-Chrome screenshots at 1440x900, 390x844 and 320x700.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://127.0.0.1:7860/"


def strip(h):
    return re.sub(r"<[^>]+>", "", h or "").strip()


def main(label):
    out = ROOT / "qa" / "ui" / label
    out.mkdir(parents=True, exist_ok=True)
    state = {"examples": {}}
    for name, text, _ in app.EXAMPLES + [("empty", "", "")]:
        res = app.predict(text)
        tier = re.search(r'data-tier="(\w+)"', res[0] or "")
        state["examples"][name] = {"tier": tier.group(1) if tier else None,
                                   "n_outputs": len(res),
                                   "texts": [strip(x)[:160] for x in res]}
    page = urllib.request.urlopen(URL, timeout=10).read().decode("utf-8", "replace")
    state["served_ok"] = len(page) > 0
    (out / "state.json").write_text(json.dumps(state, indent=1), encoding="utf-8")
    for w, h in [(1440, 900), (390, 844), (320, 700)]:
        subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", f"--window-size={w},{h}",
                        "--virtual-time-budget=6000", f"--screenshot={out / f'shot_{w}x{h}.png'}", URL],
                       capture_output=True, timeout=60)
    print(json.dumps({k: v["tier"] for k, v in state["examples"].items()}))
    print("shots:", sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "baseline")
