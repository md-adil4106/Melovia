"""LLM Integration Module.

Architecture Constraints:
- LLM output = schema-validated structured constraints over controlled vocabularies.
- The LLM NEVER selects or ranks tracks directly.
- The LLM NEVER invents metadata or track attributes.
- The LLM NEVER writes explanations not derived from ranking signals.
"""

__all__: list[str] = []
