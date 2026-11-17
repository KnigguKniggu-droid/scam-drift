"""Build scam_drift.ipynb from src/scam_drift.py and data/benign_twins.csv (keeps one source of truth).
Run from the project root:  python tools/build_notebook.py
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
lib = (ROOT / "src" / "scam_drift.py").read_text(encoding="utf-8")
lib = lib.split('if __name__ == "__main__":')[0].rstrip() + "\n"
twins_csv = (ROOT / "data" / "benign_twins.csv").read_text(encoding="utf-8")

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = [
    md("""# Scam Drift
**Question.** Does a scam filter trained on 2012-era SMS spam still protect an elderly grandparent from 2020s smishing?
Which scam types slip through? Can we fix it without flooding them with false alarms on genuine modern texts
(bank one-time codes, delivery notices, pharmacy and doctor reminders)?

**User:** an elderly grandparent, or the family member who sets up their phone. **Decision:** warn before tapping a link.

This notebook runs the same code as `src/scam_drift.py`. It works locally and in Google Colab.
This project is a prototype and is not financial advice."""),
    md("## 0. Setup\nInstall packages (Colab only), download both public datasets if missing, and write the synthetic benign-twins test file if missing."),
    code(f'''import os, sys, io, zipfile, urllib.request
from pathlib import Path
if "google.colab" in sys.modules:
    !pip -q install pandas scikit-learn matplotlib joblib
Path("data/raw").mkdir(parents=True, exist_ok=True)
UCI_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
IMC_URL = "https://raw.githubusercontent.com/reportsmishing/Smishing-Dataset-IMC25/main/dataset/final_dataset_output.csv"
if not Path("data/raw/SMSSpamCollection").exists():
    zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(UCI_URL).read())).extract("SMSSpamCollection", "data/raw")
if not Path("data/raw/imc25_smishing.csv").exists():
    urllib.request.urlretrieve(IMC_URL, "data/raw/imc25_smishing.csv")
TWINS_CSV = {twins_csv!r}
if not Path("data/benign_twins.csv").exists():
    Path("data/benign_twins.csv").write_text(TWINS_CSV, encoding="utf-8")
print(sorted(os.listdir("data/raw")))'''),
    md("## 1. Library code\nThis cell is the content of `src/scam_drift.py` (without the command-line entry point). "
       "It defines normalisation, data loading, the time split, the models, the threshold rule and the metrics."),
    code(lib),
    md("## 2. Normalisation\nThe two datasets were anonymised differently. IMC25 replaced links with `<URL>`, names with "
       "`<NAMED_ENTITY>` and so on; UCI kept raw links and numbers. Without one shared vocabulary the model would learn "
       "'contains `<URL>` = modern dataset'. We map every source onto the same tokens, then lowercase."),
    code('''for t in ["WINNER!! Claim your £900 prize: call 09061701461 or visit www.win-now.co.uk before 21st May",
          "Dear customer, your <NAMED_ENTITY> account is locked <URL> call <PHONE_NUMBER> on <DATE_TIME>",
          "I'll be there in &lt;#&gt; mins"]:
    print(repr(t), "\\n ->", normalise(t))'''),
    md("## 3. Load data and split\n* UCI: deduplicated after normalisation, stratified 80/20 split (seed 42).\n"
       "* IMC25: the `time` column is the raw screenshot timestamp (for example 'Today 8:15 AM'). Only rows that show an "
       "explicit year can be dated. Modern scams dated up to 2021 may be used for training the fix; scams dated 2022 or later "
       "are the untouched modern test. Undated rows are never used for training."),
    code('''t0 = time.time(); np.random.seed(SEED)
d = step_load_and_split()
pd.Series(d["info"]).to_frame("value")'''),
    md("## 4. Shortcut check\nCan a classifier tell UCI spam from IMC25 scams after normalisation? If yes, part of any "
       "difference we measure may be dataset artifacts rather than real drift. We list the tokens it relies on."),
    code('''shortcut = step_shortcut_check(d)
print("CV ROC AUC:", shortcut["cv_roc_auc"], " balanced accuracy:", shortcut["cv_balanced_accuracy"])
print("Tokens that say IMC25:", shortcut["top_tokens_say_imc25"])
print("Tokens that say UCI 2012:", shortcut["top_tokens_say_uci2012"])
pd.DataFrame(shortcut["token_presence_rate"]).T'''),
    md("## 5. Train\n* **2012 models:** TF-IDF word 1-2 grams + logistic regression, and a char_wb 2-5 variant, trained on UCI train only.\n"
       "* **Fixed models:** the same, trained on UCI train + English scams dated 2015-2021. Negatives are UCI ham only, "
       "because no real modern genuine texts are available. This is a known limitation.\n"
       "* **Threshold:** chosen on 5-fold out-of-fold predictions of each model's own training data, minimising "
       "5 x missed scams + 1 x false alarms. No test set is used for any choice."),
    code('''models, thresholds = step_train(d)
pd.DataFrame(thresholds).T[["threshold", "fn", "fp", "cost", "validation_n", "validation_scam_n"]]'''),
    md("## 6. Evaluate\nUCI test (2012-era), modern 2022+ test (scams only, so only recall is defined), undated modern scams, "
       "non-English scams (raw text vs English translation), and the synthetic benign twins (test only)."),
    code('''M, P = step_evaluate(d, models, thresholds)
tables = step_tables_and_figures(d, models, thresholds, M, P)
near = step_near_duplicate_check(d)
print("Near-duplicate check:", near)
pd.read_csv(RESULTS / "model_comparison.csv")'''),
    code('''base = M["baselines"]
pd.DataFrame({"always_not_scam": base["always_not_scam"]["uci_test"],
              "rule_url_or_urgency": base["rule_url_or_urgency"]["uci_test"]}).T[["precision", "recall", "f1", "false_alarm_rate"]]'''),
    code('''print("Rule baseline: modern 2022+ recall", base["rule_url_or_urgency"]["modern_late_recall"],
      "| benign twins false-alarm rate", base["rule_url_or_urgency"]["benign_twins_false_alarm_rate"])
pd.DataFrame({k: v for k, v in M["link_gated"].items() if isinstance(v, dict)}).T'''),
    md("## 7. Figures"),
    code('''from IPython.display import Image, display
for f in ["tradeoff_catch_vs_false_alarm", "recall_by_scam_type", "recall_by_year", "confusion_matrices", "pr_curve_uci"]:
    display(Image(filename=str(FIGURES / (f + ".png")), width=760))'''),
    md("## 8. Where it fails\nPer scam type, by message length (a small fairness-style check: we have no age or gender data, "
       "so we cannot check those), non-English messages, benign twins, missed scams and false alarms."),
    code('''display(pd.read_csv(RESULTS / "recall_by_scam_type_late_test.csv"))
display(pd.read_csv(RESULTS / "by_length_bucket.csv"))
display(pd.read_csv(RESULTS / "nonenglish_by_language.csv"))
display(pd.read_csv(RESULTS / "benign_twins_by_category.csv"))'''),
    code('''pd.set_option("display.max_colwidth", 160)
display(pd.read_csv(RESULTS / "fixed_model_missed_scams.csv").head(8))
display(pd.read_csv(RESULTS / "fixed_model_false_alarms.csv").head(8))'''),
    md("## 9. Explanations\nFor any message: the top 5 n-grams pushing toward 'scam' (coefficient x tf-idf value)."),
    code('''for t in ["Your package could not be delivered. Update your address here: http://parcel-help.com",
          "Maple Pharmacy: Your prescription is ready for pickup at our Main Street store."]:
    n = normalise(t)
    for name in ["word_2012", "word_fixed"]:
        p = models[name].predict_proba([n])[0, 1]
        print(f"{name:10s} p={p:.2f}", explain(models[name], n))
    print()'''),
    md("## 10. Save models and metrics\nWrites `models/*.joblib` and `results/metrics.json` (the README copies every number from this file)."),
    code('''save_models(models, thresholds)
metrics = write_metrics(d, shortcut, near, thresholds, M, tables, t0)
print("saved; runtime_seconds =", metrics["runtime_seconds"])'''),
]
nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, ROOT / "scam_drift.ipynb")
print("wrote", ROOT / "scam_drift.ipynb")
