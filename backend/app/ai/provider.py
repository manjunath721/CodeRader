"""
LLM provider abstraction (master spec §24, architecture.md). Callers never
talk to a specific vendor SDK directly — they call `generate_answer`, which
dispatches based on `LLM_PROVIDER`. With no provider configured ("none",
the default), a templated answer is built directly from the structured
context with no external call at all, which trivially satisfies the
grounding requirement in §42 since nothing is invented.
"""
import httpx

from app.core.config import get_settings
from app.core.errors import AIProviderUnavailableError

settings = get_settings()

SYSTEM_PROMPT = (
    "You are the CodeRadar AI Project Analyst. You explain software-team "
    "knowledge-risk metrics that have ALREADY been computed and are given to you "
    "as structured context. Rules:\n"
    "1. Never invent a statistic, score, or name that is not present in the context.\n"
    "2. Every number you state must reference the underlying metric from the context.\n"
    "3. If the context does not contain what's needed to answer, say: "
    "\"I don't have enough repository data to determine that.\"\n"
    "4. Use the terms 'repository-derived estimate' language already present in the "
    "context; do not claim these are proven predictions or personnel decisions."
)


def generate_answer(question: str, context: dict) -> str:
    if settings.LLM_PROVIDER == "none" or not settings.LLM_API_KEY:
        return _templated_answer(question, context)
    if settings.LLM_PROVIDER == "anthropic":
        return _anthropic_answer(question, context)
    raise AIProviderUnavailableError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER!r}")


def _anthropic_answer(question: str, context: dict) -> str:
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.LLM_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL or "claude-sonnet-4-6",
                "max_tokens": 500,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Structured context (JSON):\n{context}\n\nQuestion: {question}",
                    }
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks) if text_blocks else _templated_answer(question, context)
    except httpx.HTTPError as exc:
        raise AIProviderUnavailableError(f"LLM provider request failed: {exc}") from exc


def _templated_answer(question: str, context: dict) -> str:
    """
    Deterministic, zero-hallucination fallback: turns the structured context
    dict directly into prose. Used whenever no LLM_API_KEY is configured, so
    the AI Project Analyst still works out of the box in the demo (§37).
    """
    if context.get("type") == "module_risk":
        m = context["module"]
        return (
            f"{m['name']} has a risk score of {m['score']}/100 ({m['level']}) because its "
            f"knowledge concentration is {m['concentration_pct']}%, bus factor is {m['bus_factor']}, "
            f"and documentation coverage is {round(m['documentation_score'] * 100)}%. "
            f"These are repository-derived estimates, not scientifically proven predictions."
        )
    if context.get("type") == "module_backup":
        m = context["module"]
        candidates = context.get("candidates", [])
        if not candidates:
            return f"I don't have enough repository data to recommend a backup developer for {m['name']}."
        top = candidates[0]
        return (
            f"The strongest repository-derived backup candidate for {m['name']} is "
            f"{top['developer_name']} ({top['compatibility']}% compatibility), based on their module "
            f"knowledge, related-module experience, reviews, and recent activity. This is not a "
            f"personnel decision — just a repository-derived signal."
        )
    if context.get("type") == "simulation":
        s = context["simulation"]
        return (
            f"If {context.get('developer_name', 'this developer')} became unavailable, repository-derived "
            f"potential knowledge impact is {s['knowledge_impact_pct']}%, affecting "
            f"{', '.join(m['name'] for m in s['affected_modules']) or 'no modules'}. "
            f"Project resilience would move from {s['resilience_before']} ({s['resilience_label_before']}) "
            f"to {s['resilience_after']} ({s['resilience_label_after']})."
        )
    if context.get("type") == "resilience":
        r = context["resilience"]
        return (
            f"Project resilience is {r['score']}/100 ({r['label']}), based on developer redundancy, "
            f"knowledge distribution, documentation coverage, critical-module risk, and dependency "
            f"concentration — see the component breakdown for the exact contribution of each factor."
        )
    if context.get("type") == "recommendations":
        recs = context.get("recommendations", [])
        if not recs:
            return "I don't have enough repository data to generate recommendations yet."
        lines = [f"{r['severity']}: {r['title']}" for r in recs[:5]]
        return "Top repository-derived risks and recommendations:\n" + "\n".join(lines)
    if context.get("type") == "no_data":
        return "I don't have enough repository data to determine that."
    return "I don't have enough repository data to determine that."
