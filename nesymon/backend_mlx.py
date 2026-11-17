"""MLX labeler backend with reuse of the shared conversation prefix across steps and propositions.

Each prompt is split into a head (chat-template opening plus the conversation so far) and a tail (the
question about one proposition plus the template closing). The cache for the head is kept and extended as
the conversation grows; every question runs on a deep copy of it. This works for every cache type,
including the non-trimmable linear-attention caches of hybrid models such as Qwen3.5, for which trimming
a reused cache silently leaves state from the previous prompt behind.
"""
import copy

import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache


class MLXBackend:
    def __init__(self, model_name, use_chat_template=True):
        self.model, self.tokenizer = load(model_name)
        self.use_chat_template = use_chat_template
        self.yes_ids = self._single_token_ids(["Yes", " Yes"])
        self.no_ids = self._single_token_ids(["No", " No"])
        self.reset()
        self.encoded_tokens = 0      # tokens actually run through the model
        self.prompt_tokens = 0       # tokens a cache-free run would have encoded

    def _single_token_ids(self, words):
        ids = [self.tokenizer.encode(w, add_special_tokens=False) for w in words]
        ids = [i[0] for i in ids if len(i) == 1]
        if not ids:
            raise ValueError(f"none of {words} is a single token for this tokenizer")
        return ids

    def reset(self):
        """Forget the stored conversation prefix (call between trajectories)."""
        self.base_cache, self.base_tokens = make_prompt_cache(self.model), []

    def _split(self, prefix, suffix):
        """Token ids of the shared head and the proposition-specific tail."""
        if self.use_chat_template and self.tokenizer.chat_template:
            text = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prefix + suffix}], add_generation_prompt=True, tokenize=False,
                enable_thinking=False)
            cut = text.rfind(suffix)
            head_text, tail_text = text[:cut], text[cut:]
            head = self.tokenizer.encode(head_text, add_special_tokens=False)
        else:
            head_text, tail_text = prefix, suffix
            head = self.tokenizer.encode(head_text)
        return list(head), list(self.tokenizer.encode(tail_text, add_special_tokens=False))

    def _run(self, tokens, cache):
        logits = self.model(mx.array(tokens)[None], cache=cache)
        mx.eval(logits, [c.state for c in cache])
        return logits[0, -1]

    def answer_logits(self, prefix, suffix):
        head, tail = self._split(prefix, suffix)
        n = len(self.base_tokens)
        if n > len(head) or head[:n] != self.base_tokens:
            self.reset()
            n = 0
        if len(head) > n:
            self._run(head[n:], self.base_cache)
            self.base_tokens = head
            self.encoded_tokens += len(head) - n
        work = copy.deepcopy(self.base_cache)
        logits = self._run(tail, work)
        self.encoded_tokens += len(tail)
        self.prompt_tokens += len(head) + len(tail)
        yes = mx.logsumexp(logits[mx.array(self.yes_ids)]).item()
        no = mx.logsumexp(logits[mx.array(self.no_ids)]).item()
        return yes, no
