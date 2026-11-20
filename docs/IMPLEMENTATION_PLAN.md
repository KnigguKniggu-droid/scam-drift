# Scam Drift implementation plan

## Current release

The FastAPI checker combines the existing character n-gram classifier, a fine-tuned English BERT-Tiny model, and the request and safety rules. The BERT model runs locally through ONNX Runtime. The public demo sends the request to this server over HTTPS for in-memory processing. The live checker can add a **YELLOW** warning from BERT alone. A **RED** warning still requires the existing corroborating signal or safety condition. Named warning phrases come from matched rules or the lexical model.

The existing 3D study still reads its historical numbers from `/api/story`. The new live checker has a separate aggregate evaluation in [context_v1.json](../results/context_v1.json). The two experiments use different configurations and cohorts.

## Frontend implementation

Three reviewers walked 51 reference routes. The audit recorded visible screen checkpoints and which controls could be tested. The Oryzo walkthrough covered its desktop and mobile story, product selector, and local interactions. [Reference inventory](FRONTEND_REFERENCES.md) · [Frontend component references](FRONTEND_COMPONENT_REFERENCES.md)

Scam Drift now has a **Run the filter** action that moves through the live scan. A close camera and light pulse mark the message crossing the gate. The checker stays reachable from the scene controls. The study comparison keeps the same two measures on screen as a reader switches filter versions. **Watch this run** returns to the corresponding 3D chapter.

## Release verification

The general checker suite passed 150 targeted cases and 19 request and edge checks. The latest local test completed 512 requests at a p95 of 219.6 ms with eight concurrent workers. The finance regression suite found seven misses in 13 warning cases and one false alarm in 12 legitimate controls. The public HTTPS demo returned a verdict from `bert-tiny-sms-v1`. Chrome checks covered the run cue, keyboard comparison, WebGL replay, and the checker link at 1440, 390, and 320 px. The demo uses a temporary tunnel to the running local server. [Finance regression report](../results/finance_regression.json) · [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

## Model and evidence

| Cohort and measure | Existing lexical flag | Combined lexical and BERT flag |
| --- | --- | --- |
| 2022–24 English scams with unseen template clusters | 564 / 927 (60.84%) | 598 / 927 (64.51%) |
| All dated 2022–24 English scams | 704 / 1080 (65.19%) | 741 / 1080 (68.61%) |
| Legitimate modern business texts in held-out groups | 124 / 608 (20.39% false alarms) | 142 / 608 (23.36% false alarms) |
| Held-out synthetic legitimate examples | 5 / 30 (16.67% false alarms) | 8 / 30 (26.67% false alarms) |

The scorer was fine-tuned for four epochs on 5,385 examples, including 1,605 positive labels. The training pool uses UCI SMS, English scam reports through 2020, and part of the legitimate business SMS cohort. Threshold selection uses 668 English scam examples dated 2021 and 364 legitimate messages from separate brand and template groups. It allows up to 3 percentage points of additional false alarms on its validation cohort. The tests reuse previously studied sources. The numbers describe model flags on these cohorts and exclude the separate rule layer. Current field performance and performance in other languages are unknown. [Google BERT-Tiny model card](https://huggingface.co/google/bert_uncased_L-2_H-128_A-2)

### Run and reproduce

In the project Python environment, install the inference requirements and start the web server. The bundle in `models/context-v1/` consists of the exported weights, WordPiece tokenizer, and release metadata. The server keeps the lexical checker available if that bundle cannot load. Set `SCAM_DRIFT_CONTEXT=0` and restart the server to roll back the neural signal.

```powershell
python -m pip install -r requirements.txt -r requirements-neural.txt
python server.py
```

For training, install CPU PyTorch and the export packages. The script downloads the pinned public base model or accepts it from a local directory with `--base`. Choose a new output directory when the existing bundle is present. Keep raw training data local and store aggregate results.

```powershell
python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install transformers==5.23.0 onnx==1.20.1
python tools/train_context_model.py --output models/context-candidate --report results/context_candidate.json
python tools/checker_stress.py --corpus
```

## Next releases

| Order | Work | Release evidence |
| --- | --- | --- |
| 1. Independent benchmark | Collect recent consented or properly licensed scam reports and representative legitimate messages. Reserve the most recent slice for final testing and group sender or campaign templates across splits. Redact names, contacts, credentials, and account references. | A de-identified dataset manifest. A locked test partition. A confusion matrix and interval per cohort, language, and scam type. |
| 2. Better warning calibration | Compare the character model, BERT, and blends at a common legitimate false-alarm rate. Test hard negatives like delivery notices, bank codes, and genuine support messages. Evaluate perturbations to spelling, spacing, and URL spelling. | A released configuration improves recall at the agreed false-alarm budget. Clean-text and perturbation scores are reported separately. |
| 3. Better explanations and language support | Check whether a proposed highlight is a real substring that materially changes the model score. Build separate validation cohorts before enabling a multilingual encoder or local translation. Keep the immediate-action advice short. | Blind reviewers can identify the request and the recommended next action. Unsupported-language and insufficient-context states return safely. |
| 4. Demo and frontend | Keep the 3D scene and measured comparison controllable by scroll and discrete actions. Test that an older adult can reach the checker, run the sample, and understand the result. Test focus restoration, Back and Forward, and motion preferences. | Mobile and desktop recordings. Task completion with target users. A profiler trace and a verified static fallback. |
| 5. Durable hosting | Reproduce the demo from pinned dependencies and a reviewed model bundle. Publish the inference server with a stable frontend origin, rate limits, request-size bounds, and no text in application logs. Test provider cold starts and restore the baseline on failure. | A stable URL, verified public API, fresh mobile run, warm and cold latency measurements, and a tested rollback. |
