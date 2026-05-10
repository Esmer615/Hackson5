from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz
from django.conf import settings

FALLBACK_TITLE = "第一部分 教材内容"
CHINESE_HEADING_RE = re.compile(
    r"^第\s*[0-9零一二三四五六七八九十百千万两]+\s*[章节篇]\s*[-:：.、]?\s*.+$"
)
PAGE_FOOTER_RE = re.compile(r"^第\s*\d+\s*页\s*/\s*共\s*\d+\s*页$")
SHORT_PAGE_NUMBER_RE = re.compile(r"^[\[(（]?[0-9]{1,4}[\])）]?$")
MULTI_BLANK_RE = re.compile(r"\n{2,}")


@dataclass(slots=True)
class ParsedChapter:
    chapter_id: str
    title: str
    page_start: int
    page_end: int
    content: str
    char_count: int
    order: int


@dataclass(slots=True)
class ParsedTextbook:
    filename: str
    title: str
    total_pages: int
    total_chars: int
    chapters: list[ParsedChapter]


def parse_textbook(path: Path, filename: str, mode: str = "demo") -> ParsedTextbook:
    suffix = path.suffix.lower()
    title = Path(filename).stem

    if suffix == ".pdf":
        pages = _extract_pdf_pages(path, mode)
    elif suffix in {".md", ".markdown", ".txt"}:
        text = path.read_text(encoding="utf-8")
        pages = [(1, text)]
    else:
        raise ValueError(f"Unsupported textbook format: {suffix}")

    cleaned_pages = [
        (page_number, clean_page_text(text)) for page_number, text in pages
    ]
    chapters = split_chapters(cleaned_pages)
    combined_text = "\n".join(text for _, text in cleaned_pages if text).strip()

    return ParsedTextbook(
        filename=filename,
        title=title,
        total_pages=max(len(cleaned_pages), 1),
        total_chars=len(combined_text),
        chapters=chapters,
    )


def split_chapters(pages: list[tuple[int, str]]) -> list[ParsedChapter]:
    chapters: list[ParsedChapter] = []
    current_title: str | None = None
    current_start: int | None = None
    current_lines: list[str] = []

    for page_number, page_text in pages:
        lines = [line for line in page_text.splitlines() if line.strip()]
        for line in lines:
            heading = _extract_heading(line)
            if heading is not None:
                if current_title is not None:
                    chapters.append(
                        _build_chapter(
                            title=current_title,
                            page_start=current_start or 1,
                            page_end=page_number,
                            content_lines=current_lines,
                            order=len(chapters) + 1,
                        )
                    )
                current_title = heading
                current_start = page_number
                current_lines = []
                continue

            if current_title is None:
                current_title = FALLBACK_TITLE
                current_start = page_number

            current_lines.append(line)

    if current_title is not None:
        final_page = pages[-1][0] if pages else 1
        chapters.append(
            _build_chapter(
                title=current_title,
                page_start=current_start or 1,
                page_end=final_page,
                content_lines=current_lines,
                order=len(chapters) + 1,
            )
        )

    if chapters:
        return chapters

    fallback_page = pages[0][0] if pages else 1
    all_lines: list[str] = []
    for _, page_text in pages:
        all_lines.extend(line for line in page_text.splitlines() if line.strip())
    return [
        _build_chapter(
            title=FALLBACK_TITLE,
            page_start=fallback_page,
            page_end=pages[-1][0] if pages else fallback_page,
            content_lines=all_lines,
            order=1,
        )
    ]


def clean_page_text(text: str) -> str:
    normalized_text = unicodedata.normalize("NFKC", text)
    cleaned_lines: list[str] = []
    for raw_line in normalized_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if PAGE_FOOTER_RE.match(line):
            continue
        if SHORT_PAGE_NUMBER_RE.match(line):
            continue
        cleaned_lines.append(line)

    return MULTI_BLANK_RE.sub("\n\n", "\n".join(cleaned_lines)).strip()


def _extract_pdf_pages(path: Path, mode: str) -> list[tuple[int, str]]:
    parsed_mode = mode.lower()
    max_pages = (
        settings.DEMO_MAX_PAGES if parsed_mode == "demo" else settings.QUALITY_MAX_PAGES
    )
    pages: list[tuple[int, str]] = []

    with fitz.open(path) as document:
        limit = min(document.page_count, max_pages)
        for index in range(limit):
            text = document.load_page(index).get_text("text")
            pages.append((index + 1, text))

    return pages


def _extract_heading(line: str) -> str | None:
    stripped = line.strip()
    markdown_match = re.match(r"^#{1,6}\s+(.+)$", stripped)
    if markdown_match:
        return markdown_match.group(1).strip()
    if CHINESE_HEADING_RE.match(stripped):
        return stripped
    return None


def _build_chapter(
    *,
    title: str,
    page_start: int,
    page_end: int,
    content_lines: list[str],
    order: int,
) -> ParsedChapter:
    content = "\n".join(content_lines).strip()
    return ParsedChapter(
        chapter_id=f"ch_{order:03d}",
        title=title,
        page_start=max(page_start, 1),
        page_end=max(page_end, 1),
        content=content,
        char_count=len(content),
        order=order,
    )
