# Credits

## Datasets
- **SMS Spam Collection v.1** - Tiago A. Almeida and José María Gómez Hidalgo (2011). UCI Machine Learning Repository. https://archive.ics.uci.edu/dataset/228/sms+spam+collection . Licence: CC BY 4.0.
  Paper: Almeida, Gómez Hidalgo, Yamakami. "Contributions to the Study of SMS Spam Filtering: New Collection and Results." DocEng 2011.
- **Fishing for Smishing dataset (IMC 2025)** - Sharad Agarwal, Antonis Papasavva, Guillermo Suarez-Tangil, Marie Vasek. "Fishing for Smishing: Understanding SMS Phishing Infrastructure and Strategies by Mining Public User Reports." ACM IMC 2025. https://doi.org/10.1145/3730567.3764431 . Data: https://github.com/reportsmishing/Smishing-Dataset-IMC25 . Licence: CC BY 4.0. We use `final_dataset_output.csv` unchanged (saved as `data/raw/imc25_smishing.csv`).
- **Real modern legitimate SMS** (used in the main pipeline since post-deadline v2 (Nov 18); raw texts are not redistributed because they contain first names; `src/scam_drift.py` downloads them from pinned Hugging Face revisions into the git-ignored `data/raw/extra/`):
  - **India SMS inbox sample** - gandharvbakshi/SMS-dataset-sample-10k (real inbox rows; we keep non-synthetic rows from registered Indian business sender headers: 1,206 after deduplication). Hugging Face: https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-sample-10k (revision `2b6de4910ab9337a92f1b672d2de8ed11c6a3805`). Licence: MIT (dataset card). Use: one half (split by brand or template group) is training data for the `*_plus_real_ham` models; the other half is test only.
  - **MOZ-Smishing** (MOZNLP), Mozambique, Portuguese: legitimate SMS rows only (1,608). Hugging Face: https://huggingface.co/datasets/MOZNLP/MOZ-Smishing (revision `1092f9d9a545b29ae6be030ee9713b615fc2d987`), paper https://aclanthology.org/2025.africanlp-1.23.pdf . Licence: CreativeML OpenRAIL-M (dataset card). Use: test only; never trained on.
  - Details and checks: `docs/EXTRA_DATA.md`.
- **Benign twins** (`data/benign_twins.csv`) - synthetic messages written with AI assistance for this project (synthetic stress test). All organisation names are fictional. v1: test only. Post-deadline v2 (Nov 18): the `fix_plus_benign` variants train on 30 legitimate twins from three categories; the other 30 (other categories) and the 40 scam twins stay test only.

## Starting point
- Hackathon suggested project 4.2.1 "Scam text filter" (TF-IDF + logistic regression on SMS spam).

## Libraries
- scikit-learn - https://scikit-learn.org (BSD-3)
- pandas - https://pandas.pydata.org (BSD-3)
- NumPy - https://numpy.org (BSD-3)
- matplotlib - https://matplotlib.org (PSF-based)
- Gradio - https://gradio.app (Apache-2.0)
- joblib - https://joblib.readthedocs.io (BSD-3)
- Jupyter, nbformat, nbconvert, ipykernel - https://jupyter.org (BSD-3)

## AI tools
- **Claude (Anthropic) via Claude Code** - https://claude.com/claude-code - wrote much of the code (pipeline, notebook, demo app, triage) under the team's direction, helped plan and audit the method, drafted the documentation, and wrote the synthetic benign twins.
- **ChatGPT (OpenAI)** - https://chatgpt.com - critic of the idea, method and results.
- **Gemini (Google)** - https://gemini.google.com - critic of the idea, method and results.
- **Claude chat (Anthropic)** - https://claude.ai - critic of the idea, method and results.

What each critic said and what we did with it: `docs/CONSULT_LOG.md`. The team reviewed the code, re-ran every result and can explain every part. All reported numbers come from `results/metrics.json` produced by the code.
