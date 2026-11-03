
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf as fitz

try:
    import tiktoken  
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  
    _ENC = None

MIN_CHARS = 50  
PAGE_NUMBER = re.compile(r"(page\s*)?\d+(\s*(of|/)\s*\d+)?", re.IGNORECASE)


class ResumeReadError(Exception):
    """Raised when a resume cannot be read or has no usable text."""


def count_tokens(text: str) -> int:
    """Token count via tiktoken (cl100k_base); falls back to ~4 chars/token."""
    if _ENC is not None:
        return len(_ENC.encode(text))
    return max(1, len(text) // 4)


def clean_text(text: str) -> str:
    """Normalise whitespace and drop standalone page numbers."""
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\u00a0]+", " ", line).strip()
        if PAGE_NUMBER.fullmatch(line):
            continue
        lines.append(line)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _strip_repeated_headers(pages: list[str]) -> list[str]:
    """Remove first/last lines that repeat on more than half the pages."""
    if len(pages) < 2:
        return pages
    edge = Counter()
    for p in pages:
        lines = [l.strip() for l in p.split("\n") if l.strip()]
        edge.update(set(lines[:2] + lines[-2:]))
    repeated = {l for l, c in edge.items() if c > len(pages) / 2}
    return ["\n".join(l for l in p.split("\n") if l.strip() not in repeated)
            for p in pages]


def _read_pdf(path: Path) -> str:
    try:
        with fitz.open(path) as doc:
            pages = [page.get_text("text") for page in doc]
    except Exception as exc:
        raise ResumeReadError(f"could not open PDF ({exc})") from exc
    return "\n".join(_strip_repeated_headers(pages))


def read_text_resume(path) -> str:
    """Return cleaned text of a PDF/TXT resume or raise ResumeReadError."""
    path = Path(path)
    if not path.is_file():
        raise ResumeReadError("file not found")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw, empty_msg = _read_pdf(path), "no text found (scanned file)"
    elif suffix in {".txt", ".md"}:
        raw, empty_msg = path.read_text(encoding="utf-8", errors="replace"), "file is empty"
    else:
        raise ResumeReadError(f"unsupported file type '{suffix}'")

    text = clean_text(raw)
    if len(text) < MIN_CHARS:
        raise ResumeReadError(empty_msg)
    return text


def report(path) -> None:
    path = Path(path)
    try:
        text = read_text_resume(path)
        print(f"{path.name}: {len(text)} characters, {count_tokens(text)} tokens")
    except ResumeReadError as err:
        print(f"{path.name}: Error - {err}")

if __name__ == "__main__":
    default_dir = Path(__file__).resolve().parent / "resumes"
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else default_dir
    if not target.exists():
        sys.exit(f"Path not found: {target}")

    files = sorted(p for p in target.iterdir() if p.is_file()) if target.is_dir() else [target]
    for f in files:
        report(f)