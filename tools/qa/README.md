# Scam Drift Q&A companion

[macOS setup](MAC_SETUP.md) · [Windows download](https://github.com/KnigguKniggu-droid/scam-drift/releases/tag/finals-qa-windows) · [Claude Code setup handoff](CLAUDE_SETUP.md)

The Windows companion listens to default playback using WASAPI loopback. Local Vosk transcription waits for the host’s Q&A cue, then the panel shows a suggested answer. It starts armed. **Start Q&A now** bypasses a missed handoff, and **Test with mic** uses your microphone after you stop playback capture. The app does not change Zoom settings.

With a Gemini key loaded, it uses OpenCluely’s streaming answer service for new questions. The OpenCluely window can stay closed. The panel uses verified notes for a few narrow measured results and as a fallback when the service is unavailable. Audio stays on the PC. Completed question text and the project brief go to Gemini when generation is used. The package contains no API key. Keys entered in the app are kept in memory for the session.

The prebuilt Windows x64 bundle includes the native runtimes, Node, the Vosk model, and OpenCluely’s text-generation service from `v1.8.7`. The source here contains Scam Drift’s panel, bridge and project context. The separate OpenCluely desktop app and its configuration are independent.

The app passed the local 46-case handoff fixture, eight continuous headset clips, and ten fact checks through the combined verified-note and generated-answer paths. The packaged app also transcribed synthetic headset playback with a clean profile. The actual ceremony and a second PC were not tested. Use live AI assistance only if the organizer allows it.
