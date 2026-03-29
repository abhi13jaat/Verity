import base64
import logging

from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs

log = logging.getLogger("verity.ingestion.multimodal")

_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

_PROMPT = (
    "Describe this figure from a research paper. "
    "Focus on what it shows — key values, trends, relationships, or architecture. "
    "Be concise (2-3 sentences)."
)


def describe_image(image_bytes: bytes) -> str | None:
    if len(image_bytes) < 5_000:
        return None

    try:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        response = _llm.chat.completions.create(**provider_kwargs(),
            model=_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
            max_tokens=200,
        )
        description = response.choices[0].message.content.strip()
        log.debug("[multimodal] described image (%d bytes): %s", len(image_bytes), description[:80])
        return description
    except Exception as exc:
        log.warning("[multimodal] image description failed: %s", exc)
        return None
