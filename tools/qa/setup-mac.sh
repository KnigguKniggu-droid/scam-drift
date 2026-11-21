#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ "$(uname -s)" == Darwin ]] || { echo 'Run this script on macOS.' >&2; exit 1; }

if ! command -v brew >/dev/null 2>&1; then
  for path in /opt/homebrew/bin /usr/local/bin; do
    export PATH="$path:$PATH"
    command -v brew >/dev/null 2>&1 && break
  done
fi
command -v brew >/dev/null 2>&1 || { echo 'Install Homebrew from https://brew.sh/ and rerun.' >&2; exit 1; }
for package in python@3.12 python-tk@3.12 node; do
  brew list --versions "$package" >/dev/null 2>&1 || brew install "$package"
done
python="$(brew --prefix python@3.12)/bin/python3.12"
runtime="$PWD/.mac-runtime"
mkdir -p "$runtime"
"$python" -m venv "$runtime/venv"
"$runtime/venv/bin/python" -m pip install --only-binary=:all: 'vosk==0.3.44' 'sounddevice==0.5.6' 'soxr==1.1.0' 'numpy==2.5.5'

model=vosk-model-small-en-us-0.15
if [[ ! -f "$model/am/final.mdl" ]]; then
  curl -fLsS --retry 2 --max-time 90 "https://alphacephei.com/vosk/models/$model.zip" -o "$runtime/model.zip"
  printf '%s  %s\n' '30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498' "$runtime/model.zip" | shasum -a 256 -c -
  unzip -oq "$runtime/model.zip"
fi

revision=258fd644bf00030708ca6a694c0d1ca18c73efa0
provider="$runtime/opencluely"
if [[ ! -f "$provider/package-lock.json" ]]; then
  curl -fLsS --retry 2 --max-time 90 "https://codeload.github.com/TechyCSR/OpenCluely/tar.gz/$revision" -o "$runtime/opencluely.tgz"
  mkdir -p "$provider"
  tar -xzf "$runtime/opencluely.tgz" -C "$provider" --strip-components=1
fi
cp scam-drift-bridge.cjs "$provider/"
cp PROJECT_CONTEXT.md "$provider/prompts/scam-drift.md"
if [[ ! -d "$provider/node_modules/@google/genai" ]]; then
  npm --prefix "$provider" ci --omit=dev --ignore-scripts --no-audit --no-fund
fi
"$runtime/venv/bin/python" -c 'import tkinter, vosk, numpy, soxr, sounddevice; print("Python and macOS audio imports passed.")'
node --check "$provider/scam-drift-bridge.cjs"
"$runtime/venv/bin/python" scam_drift_qa.py --help >/dev/null
echo 'Ready to open with: bash tools/qa/run-mac.sh'
echo 'For Zoom audio, finish the BlackHole and Multi-Output Device steps in tools/qa/MAC_SETUP.md.'
