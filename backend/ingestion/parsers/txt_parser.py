from backend.ingestion.parsers.base import BaseParser, ParsedPage


class TXTParser(BaseParser):
    def parse(self, source: str) -> list[ParsedPage]:
        with open(source, "r", encoding="utf-8") as f:
            text = f.read().strip()
        return [ParsedPage(text=text, page_number=None)]
