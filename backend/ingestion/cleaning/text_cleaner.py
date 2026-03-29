import logging
import re

log = logging.getLogger("verity.ingestion.cleaning")

# ── Compiled patterns ────────────────────────────────────────────────────────

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_DOI = re.compile(r"doi:\s*10\.\d{4,}", re.IGNORECASE)
_ARXIV_ID = re.compile(r"arXiv:\s*\d{4}\.\d{4,5}", re.IGNORECASE)
_COPYRIGHT = re.compile(r"(©|\bcopyright\b|\ball rights reserved\b)", re.IGNORECASE)
_ACM_IEEE = re.compile(r"\b(ACM|IEEE|Springer|Elsevier)\b.*\d{4}", re.IGNORECASE)
_PAGE_NUMBER = re.compile(r"^\s*-?\s*\d+\s*-?\s*$")
_REFERENCE_LINE = re.compile(r"^\s*\[\d+\]")
_ORCID = re.compile(r"orcid\.org", re.IGNORECASE)
_URL_ONLY_LINE = re.compile(r"^\s*https?://\S+\s*$")

# C0/DEL control characters except tab (\x09), newline (\x0a), carriage return (\x0d).
# PDF text extraction can emit these (notably NUL \x00), and PostgreSQL's TEXT type
# rejects NUL bytes outright — strip them before anything touches the DB.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Section headings that signal non-content (truncate everything after these)
_NOISE_SECTION_HEADING = re.compile(
    r"^(references|bibliography|acknowledgments?|acknowledgements?|"
    r"about the authors?|author contributions?|funding|competing interests?|"
    r"conflict of interest|appendix)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ── Page-level cleaner ───────────────────────────────────────────────────────

def clean_page_text(text: str) -> str:
    """Clean a full page of text before chunking.

    - Strips control characters (incl. NUL) that PostgreSQL TEXT rejects
    - Truncates at references / acknowledgments / bibliography headings
    - Removes email lines, DOI lines, copyright lines, page numbers
    """
    # Strip DB-hostile control bytes first (NUL etc. from PDF extraction)
    text = _CONTROL_CHARS.sub("", text)

    # Truncate at noise section headings
    match = _NOISE_SECTION_HEADING.search(text)
    if match:
        text = text[: match.start()].strip()
        log.debug("truncated at noise section heading at char %d", match.start())

    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()

        if not stripped:
            kept.append(line)
            continue
        if _EMAIL.search(stripped):
            continue
        if _DOI.search(stripped):
            continue
        if _ARXIV_ID.search(stripped):
            continue
        if _COPYRIGHT.search(stripped):
            continue
        if _ACM_IEEE.search(stripped):
            continue
        if _PAGE_NUMBER.match(stripped):
            continue
        if _ORCID.search(stripped):
            continue
        if _URL_ONLY_LINE.match(stripped):
            continue

        kept.append(line)

    return "\n".join(kept).strip()


# ── Chunk-level filter ───────────────────────────────────────────────────────

def is_clean_chunk(text: str, min_words: int = 30) -> bool:
    """Return True if a chunk is worth embedding.

    Drops chunks that are:
    - Too short (headers, footers, lone titles)
    - Reference list entries  ([1] Lewis et al...)
    - Contain emails or DOIs
    - Have very low alphabetic content (tables of numbers, metadata)
    """
    words = text.split()

    if len(words) < min_words:
        log.debug("drop — too short (%d words)", len(words))
        return False

    # Count lines that look like reference entries
    ref_lines = sum(1 for line in text.splitlines() if _REFERENCE_LINE.match(line))
    if ref_lines >= 3:
        log.debug("drop — reference section (%d ref lines)", ref_lines)
        return False

    if _EMAIL.search(text):
        log.debug("drop — contains email")
        return False

    if _DOI.search(text):
        log.debug("drop — contains DOI")
        return False

    # Alphabetic ratio — pure number tables / metadata score very low
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    if alpha_ratio < 0.45:
        log.debug("drop — low alpha ratio (%.2f)", alpha_ratio)
        return False

    return True
