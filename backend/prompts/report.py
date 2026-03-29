_REPORT_PROMPT = """\
You are an expert research analyst. Your job is to synthesize findings from research papers and produce a thorough, well-structured answer.
{history_section}
Context (retrieved from research papers):
{context}

Question: {question}

Instructions:
- Write a detailed, comprehensive answer — aim for depth, not brevity.
- Structure your response with clear sections or numbered points where appropriate.
- Cite sources inline using [1], [2], etc. after every claim.
- Compare and contrast different approaches or findings where the context allows.
- Highlight key insights, limitations, and open problems if mentioned in the context.
- If the context does not contain enough information on a sub-topic, say so explicitly.
- Do NOT add information from outside the provided context.

Answer:\
"""

_HISTORY_SECTION = """\
Previous conversation (for continuity only — do not answer from memory):
{exchanges}

"""


def build_report_prompt(
    context: str,
    question: str,
    conversation_history: list[dict] | None = None,
    domain: str | None = None,
) -> str:
    history_section = ""
    if conversation_history:
        exchanges = "\n".join(
            f"{m['role'].capitalize()}: {m['content'][:300]}"
            for m in conversation_history[-6:]
        )
        history_section = _HISTORY_SECTION.format(exchanges=exchanges)

    return _REPORT_PROMPT.format(
        history_section=history_section,
        context=context,
        question=question,
    )
