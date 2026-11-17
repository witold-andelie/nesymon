"""M1 grounding: prompt construction, logit-to-probability conversion, and the probability cache.

The model backend (MLX or llama.cpp with prefix caching) is plugged in through `Backend`;
none is bundled yet. Every probability is cached so experiments never call a model.
"""
import json
import math
import os
from typing import Protocol

# The prefix must grow append-only with the conversation, so the turn number lives in the suffix.
PROMPT_PREFIX = "You are annotating a customer-service conversation.\n\nConversation:\n{history}\n"
PROMPT_QUESTION = (
    "\nJudge ONLY whether the following proposition holds at turn {t}, the last turn shown.\n"
    "Proposition: {definition}\n"
    "Positive example: {pos_example}\n"
    "Negative example: {neg_example}\n"
    "Answer with exactly one word, Yes or No.\n"
    "Answer:"
)


def build_prompt(history, t, definition, pos_example, neg_example):
    """Returns (shared prefix, per-proposition suffix); the prefix is reusable across props and steps."""
    prefix = PROMPT_PREFIX.format(history=history)
    suffix = PROMPT_QUESTION.format(t=t, definition=definition, pos_example=pos_example, neg_example=neg_example)
    return prefix, suffix


def yes_no_probability(logit_yes, logit_no):
    """Softmax over the two answer-token logits."""
    m = max(logit_yes, logit_no)
    ey, en = math.exp(logit_yes - m), math.exp(logit_no - m)
    return ey / (ey + en)


def agreement_probability(samples):
    """Fallback when logits are unavailable: fraction of sampled answers equal to Yes."""
    return sum(1 for s in samples if s.strip().lower().startswith("yes")) / len(samples)


class Backend(Protocol):
    def answer_logits(self, prefix: str, suffix: str) -> tuple:
        """Return (logit_yes, logit_no) for the next token after prefix + suffix."""


class ProbCache:
    """Append-only JSON-lines cache keyed by (traj_id, step, prop); one file per labeler model."""

    def __init__(self, path):
        self.path, self.data = path, {}
        if os.path.exists(path):
            with open(path) as fh:
                for line in fh:
                    rec = json.loads(line)
                    self.data[(rec["traj_id"], rec["step"], rec["prop"])] = rec["p"]

    def get(self, traj_id, step, prop):
        return self.data.get((traj_id, step, prop))

    def put(self, traj_id, step, prop, p):
        self.data[(traj_id, step, prop)] = p
        with open(self.path, "a") as fh:
            fh.write(json.dumps({"traj_id": traj_id, "step": step, "prop": prop, "p": p}) + "\n")
