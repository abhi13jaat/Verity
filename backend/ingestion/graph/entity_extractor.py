import json
import logging

from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs

log = logging.getLogger("verity.ingestion.graph")

_SYSTEM = """Extract key technical entities from the text.
Return a JSON object: {"entities": ["entity1", "entity2", ...]}
Rules:
- Specific concepts, methods, models, datasets, algorithms, or metrics only
- Lowercase, 1-4 words max
- Max 10 entities
- No generic words like "paper", "study", "result"
Return ONLY the JSON object."""


def extract_entities(text: str) -> list[str]:
    try:
        response = _llm.chat.completions.create(**provider_kwargs(),
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text[:800]},
            ],
            temperature=0,
            max_tokens=120,
        )
        data = json.loads(response.choices[0].message.content)
        entities = [e.lower().strip() for e in data.get("entities", []) if e.strip()]
        log.debug("[graph] extracted %d entities: %s", len(entities), entities)
        return entities[:10]
    except Exception as exc:
        log.debug("[graph] entity extraction failed: %s", exc)
        return []
