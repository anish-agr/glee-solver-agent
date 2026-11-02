"""Optional Gemini layer that rewrites outbound messages."""

from __future__ import annotations

import logging
import threading
import time

import requests

logger = logging.getLogger("glee_agent.llm")

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You write ONE short chat message for a player in an economic game.

Situation facts (the only truth; do not invent numbers or promises beyond them):
{facts}

Voice: {voice}

Draft to improve:
{draft}

Rewrite the draft into the most persuasive possible message for this situation:
concrete, confident, hard to say no to. Keep every number from the draft EXACTLY
as written. No preamble, no quotes, no markdown — output only the message text,
under 500 characters."""

VOICES = {
    "warm": ("Warm, reasonable dealmaker. Fairness language, mutual gain, "
             "urgency from shared loss, end with an invitation to agree."),
    "pressure": ("Implacable, procedural, intimidating but professional. "
                 "State consequences as policy, reference your own track record "
                 "of doing exactly what you said, put the burden of avoiding "
                 "mutual loss entirely on them."),
}


class MessageLLM:
    def __init__(self, api_key: str | None, model: str = "gemini-flash-latest",
                 process_budget: int = 700, timeout: float = 10.0):
        self.api_key = api_key or None
        self.model = model
        self.timeout = timeout
        self.process_budget = process_budget
        self._lock = threading.Lock()
        self._day = time.strftime("%Y-%m-%d")
        self._used = 0
        self._fails = 0
        self._open_until = 0.0

    def _budget_ok(self) -> bool:
        with self._lock:
            today = time.strftime("%Y-%m-%d")
            if today != self._day:
                self._day, self._used = today, 0
            if self._used >= self.process_budget:
                return False
            self._used += 1
            return True

    def rewrite(self, draft: str, facts: dict, style: str,
                must_keep: tuple[str, ...] = ()) -> str:
        """Rewrite `draft` in the given voice; return the draft on any failure or if a protected amount is lost."""
        if not self.api_key or time.monotonic() < self._open_until or not self._budget_ok():
            return draft
        must_keep = tuple(m for m in must_keep if m and m in draft)
        facts_txt = "\n".join(f"- {k}: {v}" for k, v in facts.items())
        try:
            r = requests.post(
                URL.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},
                json={"contents": [{"parts": [{"text": PROMPT.format(
                        facts=facts_txt, voice=VOICES.get(style, VOICES["warm"]),
                        draft=draft)}]}],
                      "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.8}},
                timeout=self.timeout)
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            with self._lock:
                self._fails = 0
            if not text or len(text) > 1900:
                return draft
            if any(m not in text for m in must_keep):
                return draft
            return text
        except Exception as e:
            with self._lock:
                self._fails += 1
                if self._fails >= 5:
                    self._open_until = time.monotonic() + 600
                    self._fails = 0
                    logger.warning("LLM circuit breaker open for 10min (%s)", e)
                else:
                    logger.info("LLM rewrite failed (%s); using template", e)
            return draft
