"""Local inference for the fine-tuned English SMS model."""
from __future__ import annotations

import json
import logging
import math
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

ARTIFACT = Path(__file__).resolve().parents[1] / "models" / "context-v1"
BASE_MODEL = "google/bert_uncased_L-2_H-128_A-2"
BASE_REVISION = "30b0a37ccaaa32f332884b96992754e246e48c5f"
MODEL_ID = "bert-tiny-sms-v1"
TOKENS = 128
STRIDE = 24
BATCH = 32
LOG = logging.getLogger(__name__)

_PLACEHOLDERS = {
    "tok_url": "web link", "tok_phone": "phone number", "tok_email": "email address",
    "tok_money": "money amount", "tok_date": "date", "tok_num": "number",
}
_TOKEN_RE = re.compile(r"\btok_\w+\b")


def model_text(normalized: str) -> str:
    """Turn the shared redaction markers into normal WordPiece vocabulary."""
    return _TOKEN_RE.sub(lambda item: _PLACEHOLDERS.get(item[0], " "), normalized)


class ContextModel:
    def __init__(self, directory: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        self.threshold = float(metadata["threshold_logit"])
        self.enabled = metadata["enabled"] is True
        if metadata["model"] != MODEL_ID or not math.isfinite(self.threshold):
            raise ValueError("Invalid contextual model metadata")
        tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        tokenizer.enable_truncation(max_length=TOKENS, stride=STRIDE)
        tokenizer.enable_padding(length=TOKENS, pad_id=0, pad_token="[PAD]")
        self.tokenizer = tokenizer
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / "model.onnx"), options, providers=["CPUExecutionProvider"])

    def scores(self, messages: list[str]) -> np.ndarray:
        """Score overlapping windows and return the maximum logit for each message."""
        encodings = self.tokenizer.encode_batch([model_text(text) for text in messages])
        indexed = [(index, part) for index, sample in enumerate(encodings)
                   for part in (sample, *sample.overflowing)]
        result = np.full(len(messages), -np.inf)
        for offset in range(0, len(indexed), BATCH):
            batch = indexed[offset:offset + BATCH]
            inputs = {
                "input_ids": np.asarray([part.ids for _, part in batch], dtype=np.int64),
                "attention_mask": np.asarray([part.attention_mask for _, part in batch], dtype=np.int64),
            }
            scores = self.session.run(["logits"], inputs)[0].reshape(-1)
            np.maximum.at(result, [index for index, _ in batch], scores)
        if not np.isfinite(result).all():
            raise ValueError("Invalid contextual model output")
        return result


@lru_cache(maxsize=1)
def load_context_model() -> ContextModel | None:
    if os.environ.get("SCAM_DRIFT_CONTEXT") == "0" or not (ARTIFACT / "metadata.json").is_file():
        return None
    try:
        model = ContextModel(ARTIFACT)
        return model if model.enabled else None
    except Exception as error:
        LOG.warning("Contextual model could not load (%s)", type(error).__name__)
        return None
