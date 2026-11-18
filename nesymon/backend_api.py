"""OpenAI-compatible chat backend for the LLM-judge baseline (B1).

The API key is read from the environment variable NESYMON_API_KEY or, if unset, from the file
~/.config/nesymon/api_key (one line, permissions 600). It is never written anywhere else.

P(violation) comes from token log-probabilities of a one-word Yes/No answer when the endpoint returns them;
otherwise the judge is asked for a probability from 0 to 100 (verbalised confidence).
"""
import json
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.request

KEY_FILE = os.path.expanduser("~/.config/nesymon/api_key")


def _ssl_context():
    """Verified TLS; uses the certifi bundle when available (python.org builds on macOS lack system roots)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def load_key():
    key = os.environ.get("NESYMON_API_KEY", "").strip()
    if not key and os.path.exists(KEY_FILE):
        key = open(KEY_FILE).read().strip()
    if not key:
        raise SystemExit(f"No API key: set NESYMON_API_KEY or write it to {KEY_FILE}")
    return key


class ChatBackend:
    def __init__(self, url, model, key=None, timeout=300, retries=6):
        self.url, self.model, self.key = url, model, key or load_key()
        self.timeout, self.retries = timeout, retries
        self.ssl = _ssl_context()

    def chat(self, messages, session=None, **params):
        """session: a stable id per conversation (sent as x-opencode-session for routing and prompt caching)."""
        body = json.dumps({"model": self.model, "messages": messages, **params}).encode()
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.key}",
                   "User-Agent": "nesymon/0.1", "Accept": "application/json"}
        if session:
            headers["x-opencode-session"] = session
        req = urllib.request.Request(self.url, data=body, method="POST", headers=headers)
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 504) and attempt < self.retries - 1:
                    time.sleep(min(60, 2 ** attempt * 3))
                    continue
                raise RuntimeError(f"HTTP {e.code}: {detail}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == self.retries - 1:
                    raise
                time.sleep(min(60, 2 ** attempt * 3))


def _logprob_yes(choice):
    """P(Yes) from the top log-probabilities of the first answer token, or None if not available."""
    content = (choice.get("logprobs") or {}).get("content") or []
    for tok in content:
        word = tok.get("token", "").strip().lower()
        if word not in ("yes", "no"):
            continue
        p = {"yes": 0.0, "no": 0.0}
        for alt in tok.get("top_logprobs") or [tok]:
            w = alt.get("token", "").strip().lower()
            if w in p:
                p[w] += math.exp(alt["logprob"])
        if p["yes"] + p["no"] > 0:
            return p["yes"] / (p["yes"] + p["no"])
    return None


def parse_probability(text):
    """Last 'probability: N' (0-100) in the answer, as a fraction; None if absent."""
    found = re.findall(r"probability\D{0,20}?(\d{1,3}(?:\.\d+)?)\s*%?", text, flags=re.I)
    if not found:
        return None
    return min(max(float(found[-1]) / 100, 0.0), 1.0)
