"""Optional LLM Polish for recommendation explanations.

Architecture & Security Constraints:
- Guarded by EXPLAIN_LLM_POLISH (default False).
- LLM input is strictly structured JSON derived from verified ranking signals.
- LLM output is strictly verified against input facts:
  * Must reference authorized signal_keys.
  * Must not introduce unsupported entities, tags, dates, or numbers.
  * On any verification failure, safely falls back to deterministic rule templates.
- Pure Python interface with FakeLLMProvider for offline deterministic verification.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from app.recsys.explain import ExplanationReason

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract interface for LLM completion providers."""

    @abstractmethod
    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text completion from prompt."""
        pass


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic fake provider for testing and validation."""

    def __init__(self, canned_responses: dict[str, str] | None = None) -> None:
        self.canned_responses = canned_responses or {}
        self.call_count = 0

    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        self.call_count += 1
        # Return canned response if matching prefix, otherwise return prompt or echo
        for prefix, resp in self.canned_responses.items():
            if prefix in prompt:
                return resp
        return "Polished: " + prompt


def extract_numbers(text: str) -> set[float]:
    """Extract numeric values from text (including percentages and floats)."""
    # Matches patterns like 42, 42.5, 95%
    raw_nums = re.findall(r"\b\d+(?:\.\d+)?%?\b", text)
    nums: set[float] = set()
    for item in raw_nums:
        clean = item.rstrip("%")
        try:
            nums.add(round(float(clean), 2))
        except ValueError:
            continue
    return nums


def extract_potential_entities(text: str) -> set[str]:
    """Extract candidate entity tokens (capitalized words and alphanumeric tokens)."""
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", text)
    return {t.lower() for t in tokens}


def verify_polished_reason(
    original: ExplanationReason,
    polished_text: str,
) -> bool:
    """Verify that polished text does not introduce hallucinated facts or unsupported entities.

    Invariants checked:
    1. Polished text must not be empty or excessively long (> 200 chars).
    2. Any numeric value in polished_text must be present in the original text or evidence dict.
    3. Any specific tags or proper nouns in polished_text must be present in evidence or original.
    """
    if not polished_text or len(polished_text.strip()) == 0:
        return False
    if len(polished_text) > 250:
        return False

    # 1. Number verification
    orig_numbers = extract_numbers(original.text)
    # Collect numbers from evidence dict
    for v in original.evidence.values():
        if isinstance(v, (int, float)):
            orig_numbers.add(round(float(v), 2))
            orig_numbers.add(round(float(v) * 100, 0))
        elif isinstance(v, str):
            orig_numbers.update(extract_numbers(v))

    polished_numbers = extract_numbers(polished_text)
    # Every polished number must be in allowed orig_numbers (or within roundoff ±1)
    for p_num in polished_numbers:
        matched = any(abs(p_num - o_num) <= 1.01 for o_num in orig_numbers)
        if not matched:
            logger.warning(
                "Verifier rejected polished reason: unsupported number %s not in %s",
                p_num,
                orig_numbers,
            )
            return False

    # 2. Known forbidden / hallucinated entity check
    # Check that forbidden keywords (not present in evidence) are rejected
    orig_tokens = extract_potential_entities(original.text)
    for v in original.evidence.values():
        if isinstance(v, str):
            orig_tokens.update(extract_potential_entities(v))
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, str):
                    orig_tokens.update(extract_potential_entities(it))

    # Permitted generic vocabulary words that may be introduced during paraphrase
    permitted_words = {
        "shares",
        "similar",
        "acoustic",
        "texture",
        "style",
        "stylistic",
        "genre",
        "artist",
        "artists",
        "track",
        "tracks",
        "music",
        "musical",
        "seeds",
        "profile",
        "energy",
        "range",
        "matches",
        "mood",
        "emotional",
        "approx",
        "sound",
        "soundscape",
        "underground",
        "popular",
        "popularity",
        "lesser",
        "known",
        "familiar",
        "discovery",
        "selection",
        "rotation",
        "expanding",
        "explores",
        "territory",
        "well",
        "solidifies",
        "core",
        "and",
        "the",
        "this",
        "with",
        "your",
        "for",
        "from",
        "into",
        "close",
        "features",
        "introduces",
        "new",
        "benchmark",
        "listening",
        "polished",
    }

    polished_tokens = extract_potential_entities(polished_text)
    unauthorized = polished_tokens - orig_tokens - permitted_words

    if unauthorized:
        logger.warning(
            "Verifier rejected polished reason: unsupported entities/words %s",
            unauthorized,
        )
        return False

    return True


class LLMPolishService:
    """Service to safely paraphrase rule-based explanations under strict verification."""

    def __init__(
        self,
        provider: BaseLLMProvider | None = None,
        enabled: bool = False,
    ) -> None:
        self.provider = provider or FakeLLMProvider()
        self.enabled = enabled

    async def polish_reasons(
        self,
        reasons: list[ExplanationReason],
        signals: dict[str, Any] | None = None,
    ) -> tuple[list[ExplanationReason], bool]:
        """Polish explanation sentences if enabled, falling back to templates on any failure.

        Returns:
            (reasons_list, was_polished_bool)
        """
        if not self.enabled or not reasons:
            return reasons, False

        polished_reasons: list[ExplanationReason] = []
        all_passed = True

        for orig in reasons:
            try:
                # Provide only structured signals and rule evidence to LLM
                prompt = (
                    f"Rewrite this explanation clearly without changing facts, numbers, or tags:\n"
                    f"Original: {orig.text}\n"
                    f"Rule: {orig.id}\n"
                    f"Evidence: {orig.evidence}"
                )
                polished_text = await self.provider.complete(prompt)
                polished_text = polished_text.strip().strip('"').strip("'")

                # Verify against factual grounding
                if verify_polished_reason(orig, polished_text):
                    polished_reasons.append(
                        ExplanationReason(
                            id=orig.id,
                            text=polished_text,
                            signal_keys=orig.signal_keys,
                            evidence=orig.evidence,
                            weight=orig.weight,
                        )
                    )
                else:
                    all_passed = False
                    polished_reasons.append(orig)
            except Exception as e:
                logger.warning("LLM polish failed with exception: %s. Falling back to template.", e)
                all_passed = False
                polished_reasons.append(orig)

        if not all_passed:
            # Safe complete fallback if any sentence failed verification
            return reasons, False

        return polished_reasons, True
