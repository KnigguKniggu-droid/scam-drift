"""Fine-tune a small English BERT model and evaluate its extra warning signal."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.nn import functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from context_model import (ARTIFACT, BASE_MODEL, BASE_REVISION, MODEL_ID, TOKENS, ContextModel, model_text)  # noqa: E402
from scam_drift import SEED, rate_ci, step_load_and_split, step_v2_data  # noqa: E402
from triage import _bundle  # noqa: E402

EXTRA_VALIDATION_FA = 0.03
MAX_EXTRA_TEST_FA = 0.05


def split_data():
    history = step_load_and_split()
    grouped, _ = step_v2_data(history)
    early = grouped["dated"].query("year < 2021")
    validation_scams = grouped["dated"].query("year == 2021")
    validation_scams = validation_scams[~validation_scams["cluster"].isin(early["cluster"])]
    validation_ham = grouped["ind_a2"]
    training = pd.concat([history["uci_tr"], early.assign(label=1), grouped["ind_a1"]], ignore_index=True)
    holdouts = [validation_scams, validation_ham, grouped["late_safe"], grouped["ind_te"], history["uci_te"]]
    held_norms = {norm for cohort in holdouts for norm in cohort["norm"]}
    # Dedupe in the representation the neural network actually receives.
    held_text = {model_text(norm) for norm in held_norms}
    training["bert_text"] = training["norm"].map(model_text)
    conflicts = training.groupby("bert_text")["label"].nunique()
    training = training[~training["bert_text"].isin(held_text | set(conflicts[conflicts > 1].index))]
    training = training.drop_duplicates("bert_text")
    return training, validation_scams, validation_ham, {
        "late_english_unseen_templates": grouped["late_safe"].assign(label=1),
        "late_english_all": history["late"].assign(label=1),
        "modern_legitimate_heldout_groups": grouped["ind_te"],
        "historical_uci_test": history["uci_te"],
        "synthetic_legitimate_test": grouped["syn_te"],
        "synthetic_scam_test": grouped["syn_scam"],
    }


def fine_tune(training, base: str, epochs: int, batch_size: int):
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    options = {"revision": BASE_REVISION} if base == BASE_MODEL else {"local_files_only": True}
    tokenizer = AutoTokenizer.from_pretrained(base, **options)
    model = AutoModelForSequenceClassification.from_pretrained(
        base, **options, num_labels=1, use_safetensors=True, attn_implementation="eager"
    )
    features = tokenizer(training["bert_text"].tolist(), truncation=True, max_length=TOKENS)
    examples = [{"input_ids": ids, "attention_mask": mask}
                for ids, mask in zip(features["input_ids"], features["attention_mask"], strict=True)]
    labels = training["label"].to_numpy(dtype=np.float32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5, weight_decay=.01)
    model.train()
    for epoch in range(epochs):
        indices = rng.permutation(len(examples))
        total_loss = 0.0
        for left in range(0, len(indices), batch_size):
            batch = indices[left:left + batch_size]
            tokens = tokenizer.pad([examples[index] for index in batch], return_tensors="pt")
            logits = model(**tokens).logits.flatten()
            loss = F.binary_cross_entropy_with_logits(logits, torch.from_numpy(labels[batch]))
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item() * len(batch)
        print(f"Epoch {epoch + 1}/{epochs}: train loss {total_loss / len(examples):.4f}", flush=True)
    return model.eval(), tokenizer


def export(model, tokenizer, destination: Path) -> None:
    class Logits(torch.nn.Module):
        def __init__(self, encoder):
            super().__init__()
            self.encoder = encoder

        def forward(self, input_ids, attention_mask):
            return self.encoder(input_ids=input_ids, attention_mask=attention_mask).logits

    wrapper = Logits(model).eval()
    tokens = tokenizer(["a message", "please verify this text"], padding="max_length", max_length=TOKENS,
                       truncation=True, return_tensors="pt")
    with torch.inference_mode():
        torch.onnx.export(wrapper, (tokens["input_ids"], tokens["attention_mask"]),
                          str(destination / "model.onnx"), input_names=["input_ids", "attention_mask"],
                          output_names=["logits"], dynamic_axes={key: {0: "batch"} for key in
                          ("input_ids", "attention_mask", "logits")}, opset_version=17, dynamo=False)
    tokenizer.backend_tokenizer.save(str(destination / "tokenizer.json"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def flags(bundle, cohort) -> np.ndarray:
    return bundle["pipeline"].predict_proba(cohort["norm"].tolist())[:, 1] >= bundle["threshold"]


def choose_threshold(scam_scores, ham_scores, scam_flags, ham_flags) -> float:
    """Maximize extra validation recall under a fixed false-alarm budget."""
    candidates = np.unique(np.concatenate([scam_scores, ham_scores]))
    thresholds = np.r_[candidates, np.nextafter(candidates[-1], np.inf)]
    valid = [t for t in thresholds if ((ham_scores >= t) & ~ham_flags).mean() <= EXTRA_VALIDATION_FA]
    return float(max(valid, key=lambda t: (((scam_scores >= t) & ~scam_flags).sum(),
                                           -((ham_scores >= t) & ~ham_flags).sum(), t)))


def evaluate(bundle, model, cohorts, threshold) -> dict:
    results = {}
    for name, cohort in cohorts.items():
        lexical = flags(bundle, cohort)
        neural = model.scores(cohort["norm"].tolist()) >= threshold
        labels = cohort["label"].to_numpy() == 1
        results[name] = {}
        for mask, metric in [(labels, "recall"), (~labels, "false_alarm_rate")]:
            if mask.any():
                results[name][metric] = {
                    "lexical": rate_ci(lexical[mask]),
                    "neural": rate_ci(neural[mask]),
                    "combined": rate_ci((lexical | neural)[mask]),
                    "additional_flags": int((neural[mask] & ~lexical[mask]).sum()),
                }
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE_MODEL)
    parser.add_argument("--output", type=Path, default=ARTIFACT)
    parser.add_argument("--report", type=Path, default=ROOT / "results" / "context_v1.json")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}. Choose a new directory.")
    if args.epochs < 1 or args.threads < 1:
        parser.error("Epochs and threads must be positive.")
    torch.set_num_threads(args.threads)
    training, validation_scams, validation_ham, tests = split_data()
    print(f"Training rows {len(training)}. Validation scams {len(validation_scams)}. "
          f"Validation legitimate texts {len(validation_ham)}.", flush=True)
    model, tokenizer = fine_tune(training, args.base, args.epochs, batch_size=48)
    bundle = _bundle()
    with tempfile.TemporaryDirectory(dir=args.output.parent) as workspace:
        candidate = Path(workspace) / "candidate"
        candidate.mkdir()
        export(model, tokenizer, candidate)
        config = {"model": MODEL_ID, "base": BASE_MODEL, "revision": BASE_REVISION,
                  "threshold_logit": 0.0, "enabled": False}
        write_json(candidate / "metadata.json", config)
        context = ContextModel(candidate)
        threshold = choose_threshold(context.scores(validation_scams["norm"].tolist()),
                                     context.scores(validation_ham["norm"].tolist()),
                                     flags(bundle, validation_scams), flags(bundle, validation_ham))
        results = evaluate(bundle, context, {
            "validation_scam_2021": validation_scams.assign(label=1),
            "validation_legitimate_groups": validation_ham,
            **tests,
        }, threshold)
        recall = results["late_english_unseen_templates"]["recall"]
        alarms = results["modern_legitimate_heldout_groups"]["false_alarm_rate"]
        enabled = recall["additional_flags"] > 0 and alarms["additional_flags"] / alarms["combined"]["n"] <= MAX_EXTRA_TEST_FA
        config.update(threshold_logit=threshold, enabled=enabled)
        report = {**config, "seed": SEED, "epochs": args.epochs, "training_rows": len(training),
                  "training_positive": int(training["label"].sum()), "extra_validation_fa_budget": EXTRA_VALIDATION_FA,
                  "max_extra_test_fa": MAX_EXTRA_TEST_FA, "cohorts": results}
        write_json(candidate / "metadata.json", config)
        candidate.rename(args.output)
        write_json(args.report, report)
    print(f"Additional unseen-template scam warnings: {recall['additional_flags']}. "
          f"Additional legitimate warnings: {alarms['additional_flags']}. Enabled: {enabled}.", flush=True)


if __name__ == "__main__":
    main()
