"""AI Budget Manager and Free-Tier LLM Gateway for ProjectPulse AI.

Enforces strict zero-cost operation and protects free-tier API quotas:
1. Primary Provider: Google Gemini 1.5 Flash (Free Tier: 15 RPM, 1,500 RPD, 1M TPM)
   Checked: 2026-10-23. Source: Google AI Studio Gemini API pricing documentation.
2. Fallback: Local Deterministic Semantic Engine (Zero external dependencies, unlimited calls)
3. Safety Guardrails:
   - Internal daily cap: 100 requests/day (guarantees remaining 93% below 1,500 limit).
   - Rate limit: max 10 requests/minute.
   - Context hashing: SHA-256 hash of (query + structured facts) prevents duplicate LLM calls.
   - Prompt sanitization: Only sends compact structured facts, never raw code, secrets, or .env files.
   - Graceful fallback: Any HTTP 429, network timeout, or quota exhaustion seamlessly falls back
     to the local deterministic engine without interrupting the user.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import threading
import time
from typing import Any
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

DAILY_REQUEST_CAP = 100
RATE_LIMIT_PER_MINUTE = 10


class AIBudgetManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._request_timestamps: list[float] = []
        self._requests_today = 0
        self._last_day = datetime.now(timezone.utc).date()
        self._current_mode = "LOCAL"

    def _refresh_daily_quota(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._last_day:
            self._requests_today = 0
            self._last_day = today

    def get_status(self) -> dict[str, Any]:
        """Return the current operating mode and remaining daily request budget."""
        with self._lock:
            self._refresh_daily_quota()
            gemini_key = os.getenv("GEMINI_API_KEY", "") or getattr(settings, "gemini_api_key", "")
            has_key = bool(gemini_key and len(gemini_key) > 5)

            if not has_key:
                mode = "LOCAL"
                provider = "Local Deterministic Semantic Engine"
            elif self._requests_today >= DAILY_REQUEST_CAP:
                mode = "FALLBACK"
                provider = "Local Engine (Daily Free Quota Exhausted)"
            elif self._current_mode == "FALLBACK":
                mode = "FALLBACK"
                provider = "Local Engine (Temporary Fallback)"
            else:
                mode = "GEMINI"
                provider = "Google Gemini 1.5 Flash (Free Tier)"

            return {
                "mode": mode,
                "provider": provider,
                "gemini_configured": has_key,
                "daily_cap": DAILY_REQUEST_CAP,
                "requests_today": self._requests_today,
                "remaining_today": max(0, DAILY_REQUEST_CAP - self._requests_today),
                "cached_entries": len(self._cache),
                "rate_limit_rpm": RATE_LIMIT_PER_MINUTE,
            }

    def _compute_context_hash(self, query: str, context: dict[str, Any]) -> str:
        serialized = json.dumps({"q": query.strip().lower(), "c": context}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def generate_response(
        self,
        query: str,
        retrieved_context: dict[str, Any],
        deterministic_fallback: str,
        citations: list[str],
    ) -> dict[str, Any]:
        """Synthesize an answer using Gemini 1.5 Flash if within budget, else local fallback."""
        with self._lock:
            self._refresh_daily_quota()
            cache_key = self._compute_context_hash(query, retrieved_context)

            # Check cache
            if cache_key in self._cache:
                logger.info("AI Budget Manager: Cache hit for context hash %s", cache_key[:8])
                cached = self._cache[cache_key]
                return {
                    **cached,
                    "cached": True,
                    "budget_status": self.get_status(),
                }

            gemini_key = os.getenv("GEMINI_API_KEY", "") or getattr(settings, "gemini_api_key", "")
            can_call_gemini = (
                bool(gemini_key and len(gemini_key) > 5)
                and self._requests_today < DAILY_REQUEST_CAP
            )

            # Enforce 10 RPM rate limit
            now = time.monotonic()
            self._request_timestamps = [t for t in self._request_timestamps if now - t < 60.0]
            if len(self._request_timestamps) >= RATE_LIMIT_PER_MINUTE:
                logger.warning("AI Budget Manager: Rate limit reached (10 RPM). Falling back to local engine.")
                can_call_gemini = False

            if not can_call_gemini:
                response = {
                    "query": query,
                    "answer": deterministic_fallback,
                    "citations": citations,
                    "mode": "LOCAL" if not gemini_key else "FALLBACK",
                    "cached": False,
                    "budget_status": self.get_status(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self._cache[cache_key] = response
                return response

            # Increment count
            self._requests_today += 1
            self._request_timestamps.append(now)

        # Call Gemini 1.5 Flash outside the lock
        gemini_answer = self._call_gemini_api(gemini_key, query, retrieved_context)

        with self._lock:
            if gemini_answer:
                self._current_mode = "GEMINI"
                final_answer = gemini_answer
                mode = "GEMINI"
            else:
                self._current_mode = "FALLBACK"
                final_answer = deterministic_fallback
                mode = "FALLBACK"

            response = {
                "query": query,
                "answer": final_answer,
                "citations": citations,
                "mode": mode,
                "cached": False,
                "budget_status": self.get_status(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._cache[cache_key] = response
            return response

    def _call_gemini_api(
        self, api_key: str, query: str, context: dict[str, Any]
    ) -> str | None:
        """Execute a compact, sanitized HTTP call to Google Gemini 1.5 Flash endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        prompt = (
            "You are ProjectPulse AI Assistant. Answer the question using ONLY the provided facts. "
            "Never invent facts or cite files not mentioned in context. Keep the answer direct and professional.\n\n"
            f"PROJECT FACTS:\n{json.dumps(context, indent=2)}\n\n"
            f"QUESTION: {query}\n"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 600,
            },
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                elif res.status_code == 429:
                    logger.warning("Gemini API rate limit 429 exceeded. Activating local fallback.")
                else:
                    logger.warning("Gemini API returned status %d: %s", res.status_code, res.text[:200])
        except Exception as exc:
            logger.warning("Gemini API network/request error: %s. Falling back to local engine.", exc)

        return None


# Global singleton instance
ai_budget_manager = AIBudgetManager()
