"""LLM Integration Module.

Architecture Constraints:
- LLM output = schema-validated structured constraints over controlled vocabularies.
- The LLM NEVER selects or ranks tracks directly.
- The LLM NEVER invents metadata or track attributes.
- The LLM NEVER writes explanations not derived from ranking signals.
"""

from app.llm.client import (
    FakeLLMClient,
    LLMClient,
    LLMClientError,
    LLMResponseValidationError,
    LLMTimeoutError,
    OpenAILLMClient,
    get_llm_client,
)
from app.llm.polish import (
    BaseLLMProvider,
    FakeLLMProvider,
    LLMPolishService,
    verify_polished_reason,
)
from app.llm.rule_parser import RuleBasedRefinementParser, parse_refinement_rule_based

__all__ = [
    "LLMClient",
    "OpenAILLMClient",
    "FakeLLMClient",
    "LLMClientError",
    "LLMTimeoutError",
    "LLMResponseValidationError",
    "get_llm_client",
    "RuleBasedRefinementParser",
    "parse_refinement_rule_based",
    "BaseLLMProvider",
    "FakeLLMProvider",
    "LLMPolishService",
    "verify_polished_reason",
]
