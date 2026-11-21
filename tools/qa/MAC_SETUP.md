# Scam Drift Q&A on William’s Mac

From this repo’s `post-deadline` branch, run `bash tools/qa/setup-mac.sh`. This installs the user-space runtimes through Homebrew, makes a local Python environment, verifies the Vosk model download, and installs the pinned OpenCluely answer service. Then run `bash tools/qa/run-mac.sh --paused`. Type a practice question and press **Ask**. Enter a personal Gemini key through **Add Gemini key** when needed. The separate OpenCluely desktop window is optional.

## Hearing Zoom and still hearing the judges

1. Check whether **BlackHole 2ch** is already installed. If needed, run `brew install --cask blackhole-2ch`, or use the [official installer](https://existential.audio/blackhole/). William completes any macOS installer or permission prompt. Use the existing device if present.
2. Open **Audio MIDI Setup**. Create a **Multi-Output Device** with the speakers or headphones you can hear and **BlackHole 2ch**. Use the physical output as primary and enable drift correction for BlackHole when offered. Follow the [BlackHole Multi-Output instructions](https://github.com/ExistentialAudio/BlackHole/wiki/Getting-Started%3A-Creating-a-Multi-Output-Device).
3. Set Zoom’s **Speaker** to that Multi-Output Device. Keep Zoom’s **Microphone** set to the normal microphone. The Q&A panel looks for **BlackHole 2ch** by name. Allow audio input access for the terminal or Python if macOS asks.
4. Click **Arm for Q&A**. In a synthetic test call, confirm an early announcement leaves it armed, then say “Let’s start the questions now” over the call. Confirm it becomes active and answers two different questions. If the host skips the cue, use **Start Q&A now**. Verify **Stop listening**. To rehearse using your own voice, stop playback capture and click **Test with mic**.

## If the call starts before audio setup is ready

Keep the panel paused and type questions, or open the [cue card](CUE_CARD.txt). The official [Windows ZIP](https://github.com/KnigguKniggu-droid/scam-drift/releases/tag/finals-qa-windows) is for Windows x64. The macOS source path has not been run on William’s Mac. Report which checks actually pass before calling the Mac ready.

Use live AI assistance only if the event organizer allows it. The app processes audio locally. For generated answers it sends completed question text and the project brief to Google Gemini.
