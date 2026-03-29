import logging

from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs

log = logging.getLogger("verity.retrieval.hyde")

_SYSTEM = (
    "Write 2-3 sentences that directly answer this question as if from an academic paper. "
    "Be factual and concise. No preamble."
)


def generate_hypothetical_document(query: str) -> str:
    log.info("[hyde] generating hypothetical document for query=%r", query[:80])

    response = _llm.chat.completions.create(**provider_kwargs(),
        model=settings.fast_llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": query},
        ],
        temperature=0.3,
        max_tokens=120,
    )

    hyp_doc = response.choices[0].message.content.strip()
    log.info("[hyde] generated %d chars", len(hyp_doc))
    return hyp_doc
