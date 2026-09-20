"""Unit tests for optional LLM polish service and anti-hallucination verifier."""

import pytest

from app.llm.polish import (
    FakeLLMProvider,
    LLMPolishService,
    verify_polished_reason,
)
from app.recsys.explain import ExplanationReason


def test_verifier_accepts_faithful_paraphrase() -> None:
    original = ExplanationReason(
        id="RULE_SHARED_TAGS",
        text="Shares synthwave and retrowave with Pacific Coast.",
        signal_keys=["shared_tags", "nearest_seed_id"],
        evidence={"shared_tags": ["synthwave", "retrowave"], "nearest_seed_title": "Pacific Coast"},
        weight=1.0,
    )

    # Valid paraphrase: rephrases without introducing new facts
    faithful_polish = "Shares retrowave and synthwave style with Pacific Coast."
    assert verify_polished_reason(original, faithful_polish)


def test_verifier_rejects_injected_number() -> None:
    original = ExplanationReason(
        id="RULE_MAINSTREAM",
        text="Well-known catalog benchmark track (80% popularity).",
        signal_keys=["popularity_pct"],
        evidence={"popularity_pct": 80.0},
        weight=1.0,
    )

    # Injected number "1984" not in evidence or original text
    hallucinated_polish = "Well-known catalog benchmark track from 1984 with 80% popularity."
    assert not verify_polished_reason(original, hallucinated_polish)


def test_verifier_rejects_injected_unsupported_tag_or_entity() -> None:
    original = ExplanationReason(
        id="RULE_ACOUSTIC_MATCH",
        text="Shares similar acoustic and rhythmic texture with your seeds (85% acoustic match).",
        signal_keys=["pct_a", "sim_a"],
        evidence={"pct_a": 0.85},
        weight=1.0,
    )

    # Injected entity / instrument "saxophone" not in original or evidence
    hallucinated_polish = (
        "Shares similar acoustic texture featuring saxophone solos (85% acoustic match)."
    )
    assert not verify_polished_reason(original, hallucinated_polish)


@pytest.mark.asyncio
async def test_llm_polish_service_disabled_by_default() -> None:
    fake_provider = FakeLLMProvider()
    service = LLMPolishService(provider=fake_provider, enabled=False)

    reasons = [
        ExplanationReason(
            id="RULE_NEW_ARTIST",
            text="Introduces Perturbator, a new artist for your listening profile.",
            signal_keys=["artist_new"],
            evidence={"artist_name": "Perturbator"},
            weight=1.0,
        )
    ]

    out_reasons, was_polished = await service.polish_reasons(reasons)
    assert not was_polished
    assert out_reasons == reasons
    assert fake_provider.call_count == 0


@pytest.mark.asyncio
async def test_llm_polish_service_fallback_on_verifier_failure() -> None:
    # Canned response injects hallucinated instrument
    fake_provider = FakeLLMProvider(
        canned_responses={
            "Rewrite this explanation": (
                "Introduces Perturbator with heavy electric accordion solos."
            )
        }
    )
    service = LLMPolishService(provider=fake_provider, enabled=True)

    reasons = [
        ExplanationReason(
            id="RULE_NEW_ARTIST",
            text="Introduces Perturbator, a new artist for your listening profile.",
            signal_keys=["artist_new"],
            evidence={"artist_name": "Perturbator"},
            weight=1.0,
        )
    ]

    out_reasons, was_polished = await service.polish_reasons(reasons)
    # Must reject and safely fallback to original reason
    assert not was_polished
    assert out_reasons[0].text == reasons[0].text
    assert "accordion" not in out_reasons[0].text
