import trafilatura

from backend.ingestion.parsers.base import BaseParser, ParsedPage


class WebParser(BaseParser):
    def parse(self, source: str) -> list[ParsedPage]:
        downloaded = trafilatura.fetch_url(source)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        if not text:
            raise ValueError(f"Could not extract text from URL: {source}")
        return [ParsedPage(text=text.strip(), page_number=None)]
