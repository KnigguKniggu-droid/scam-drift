# Credits

## Datasets
- **SMS Spam Collection v.1** - Tiago A. Almeida and José María Gómez Hidalgo (2011). UCI Machine Learning Repository. https://archive.ics.uci.edu/dataset/228/sms+spam+collection . Licence: CC BY 4.0.
  Paper: Almeida, Gómez Hidalgo, Yamakami. "Contributions to the Study of SMS Spam Filtering: New Collection and Results." DocEng 2011.
- **Fishing for Smishing dataset (IMC 2025)** - Sharad Agarwal, Antonis Papasavva, Guillermo Suarez-Tangil, Marie Vasek. "Fishing for Smishing: Understanding SMS Phishing Infrastructure and Strategies by Mining Public User Reports." ACM IMC 2025. https://doi.org/10.1145/3730567.3764431 . Data: https://github.com/reportsmishing/Smishing-Dataset-IMC25 . Licence: CC BY 4.0. We use `final_dataset_output.csv` unchanged (saved as `data/raw/imc25_smishing.csv`).
- **Benign twins** (`data/benign_twins.csv`) - synthetic messages written with AI assistance for this project. All organisation names are fictional. Test only; never used for training.

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
- **Claude (Anthropic) via Claude Code** - https://claude.com/claude-code - wrote and ran the pipeline, notebook, demo app and drafts of the documentation, and wrote the synthetic benign twins.
- **ChatGPT (OpenAI)** - https://chatgpt.com - idea critique.
- **Gemini (Google)** - https://gemini.google.com - idea critique.
The team reviewed the outputs. All reported numbers come from `results/metrics.json` produced by the code.
