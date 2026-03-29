import logging

import fitz  # PyMuPDF

from backend.ingestion.parsers.base import BaseParser, ParsedPage

log = logging.getLogger("verity.ingestion.parsers.pdf")

# Lazy import to avoid loading Groq at import time for non-PDF pipelines
_describe_image = None


def _get_image_describer():
    global _describe_image
    if _describe_image is None:
        from backend.ingestion.multimodal.image_describer import describe_image
        _describe_image = describe_image
    return _describe_image


class PDFParser(BaseParser):
    def __init__(self, extract_images: bool = True):
        self.extract_images = extract_images

    def parse(self, source: str) -> list[ParsedPage]:
        pages = []
        describer = _get_image_describer() if self.extract_images else None

        with fitz.open(source) as doc:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text().strip()

                # Append image descriptions to the page text
                if describer:
                    image_descriptions = self._extract_image_descriptions(page, describer)
                    if image_descriptions:
                        text += "\n\n" + "\n".join(image_descriptions)
                        log.debug("[pdf] page %d — added %d image descriptions", page_num, len(image_descriptions))

                if text.strip():
                    pages.append(ParsedPage(text=text, page_number=page_num))

        return pages

    def _extract_image_descriptions(self, page, describer) -> list[str]:
        descriptions = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base_image = page.parent.extract_image(xref)
                image_bytes = base_image["image"]
                desc = describer(image_bytes)
                if desc:
                    descriptions.append(f"[Figure: {desc}]")
            except Exception as exc:
                log.debug("[pdf] image extraction failed for xref=%d: %s", xref, exc)
        return descriptions
