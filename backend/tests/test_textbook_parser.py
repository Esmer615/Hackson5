from pathlib import Path

import fitz
import pytest

from apps.textbooks.services.parser import (
    FALLBACK_TITLE,
    clean_page_text,
    parse_textbook,
    split_chapters,
)


def test_split_chapters_detects_chinese_chapter_titles():
    pages = [
        (1, "第一章 绪论\n生理学是研究生命活动规律的科学。"),
        (2, "第二章 细胞\n细胞膜维持稳态。"),
    ]

    chapters = split_chapters(pages)

    assert [chapter.title for chapter in chapters] == ["第一章 绪论", "第二章 细胞"]
    assert chapters[0].page_start == 1
    assert chapters[1].page_end == 2


def test_parse_markdown_textbook(tmp_path: Path):
    file_path = tmp_path / "病理学.md"
    file_path.write_text(
        "# 第一章 绪论\n炎症是防御性反应。\n# 第二章 损伤\n细胞损伤可逆或不可逆。",
        encoding="utf-8",
    )

    parsed = parse_textbook(file_path, "病理学.md", mode="demo")

    assert parsed.title == "病理学"
    assert parsed.total_pages == 1
    assert parsed.total_chars > 20
    assert len(parsed.chapters) == 2
    assert parsed.chapters[0].title == "第一章 绪论"


def test_split_chapters_preserves_pre_heading_content_in_fallback_chapter():
    chapters = split_chapters([(1, "导言\n第一章 绪论\n正文")])

    assert [chapter.title for chapter in chapters] == [FALLBACK_TITLE, "第一章 绪论"]
    assert chapters[0].page_start == 1
    assert chapters[0].page_end == 1
    assert chapters[0].content == "导言"
    assert chapters[1].content == "正文"


def test_clean_page_text_removes_footer_blank_lines_and_page_number_lines():
    cleaned = clean_page_text("保留内容\n\n第 1 页 / 共 20 页\n\n12\n\n第二段\n")

    assert cleaned == "保留内容\n第二段"


def test_split_chapters_without_headings_returns_single_fallback_chapter():
    chapters = split_chapters([(3, "课程导读\n核心概念")])

    assert len(chapters) == 1
    assert chapters[0].title == FALLBACK_TITLE
    assert chapters[0].page_start == 3
    assert chapters[0].page_end == 3
    assert chapters[0].content == "课程导读\n核心概念"


def _insert_pdf_text_with_cjk_font(page: fitz.Page, text: str) -> None:
    candidate_fonts = [
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        Path("/usr/share/fonts/truetype/arphic/ukai.ttc"),
    ]

    for font_path in candidate_fonts:
        if font_path.exists():
            page.insert_text((72, 72), text, fontname="F0", fontfile=str(font_path))
            return

    pytest.skip("CJK font not available for PDF fixture")


def test_parse_pdf_textbook_uses_page_text(tmp_path: Path):
    file_path = tmp_path / "生理学.pdf"
    doc = fitz.open()
    page = doc.new_page()
    _insert_pdf_text_with_cjk_font(
        page, "第一章 绪论\n生理学是研究生命活动规律的科学。"
    )
    doc.save(file_path)
    doc.close()

    parsed = parse_textbook(file_path, "生理学.pdf", mode="demo")

    assert parsed.title == "生理学"
    assert parsed.total_pages == 1
    assert parsed.chapters[0].title == "第一章 绪论"
    assert "生命活动" in parsed.chapters[0].content
