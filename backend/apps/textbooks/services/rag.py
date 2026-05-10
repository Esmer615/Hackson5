from __future__ import annotations

import math
from typing import Any

from django.db import transaction

from apps.textbooks.models import Chapter, RagChunk
from apps.textbooks.services.ai import DeepSeekClient
from apps.textbooks.services.integration import cosine, text_to_vector

MIN_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 80
NO_RESULT_ANSWER = "当前知识库中未找到相关信息"


def build_rag_index(textbook_ids: list[int]) -> dict[str, int]:
    textbook_ids = [int(textbook_id) for textbook_id in textbook_ids if textbook_id]
    if not textbook_ids:
        return {"chunks": 0}

    with transaction.atomic():
        RagChunk.objects.filter(textbook_id__in=textbook_ids).delete()

        total_chunks = 0
        chapters = (
            Chapter.objects.filter(textbook_id__in=textbook_ids)
            .select_related("textbook")
            .order_by("textbook_id", "order", "id")
        )
        for chapter in chapters:
            for chunk_order, content in enumerate(
                _chunk_chapter_content(chapter.content), start=1
            ):
                RagChunk.objects.create(
                    textbook=chapter.textbook,
                    chapter=chapter,
                    chunk_id=_build_chunk_id(chapter, chunk_order),
                    content=content,
                    page_start=chapter.page_start or 1,
                    page_end=chapter.page_end or chapter.page_start or 1,
                    order=chunk_order,
                    vector=text_to_vector(content),
                )
                total_chunks += 1

        return {"chunks": total_chunks}


def query_rag(
    question: str, top_k: int = 5, client: DeepSeekClient | None = None
) -> dict[str, Any]:
    client = client or DeepSeekClient()
    query_vector = text_to_vector(question)
    ranked_chunks = []
    for chunk in RagChunk.objects.select_related("textbook", "chapter").all():
        score = cosine(query_vector, _normalize_vector(chunk.vector))
        if score <= 0:
            continue
        ranked_chunks.append((score, chunk))
    ranked_chunks.sort(key=lambda item: item[0], reverse=True)
    selected = ranked_chunks[: max(top_k, 1)]

    if not selected:
        return {"answer": NO_RESULT_ANSWER, "citations": [], "source_chunks": []}

    contexts = []
    citations = []
    source_chunks = []
    for score, chunk in selected:
        chapter_title = chunk.chapter.title if chunk.chapter else "未知章节"
        textbook_title = (
            chunk.textbook.title
            or chunk.textbook.original_name
            or chunk.textbook.filename
        )
        contexts.append(
            {
                "textbook": textbook_title,
                "chapter": chapter_title,
                "content": chunk.content,
            }
        )
        citations.append(
            {
                "textbook": textbook_title,
                "chapter": chapter_title,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "chunk_id": chunk.chunk_id,
            }
        )
        source_chunks.append(
            {
                "chunk_id": chunk.chunk_id,
                "chapter": chapter_title,
                "textbook": textbook_title,
                "score": round(score, 3),
                "content": chunk.content,
            }
        )

    answer = client.answer_with_context(question=question, contexts=contexts).strip()
    if not answer:
        answer = NO_RESULT_ANSWER
    return {
        "answer": answer,
        "citations": citations,
        "source_chunks": source_chunks,
    }


def _chunk_chapter_content(content: str) -> list[str]:
    text = (content or "").strip()
    if not text:
        return []
    if len(text) <= MAX_CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + MAX_CHUNK_SIZE, length)
        if end < length and end - start >= MIN_CHUNK_SIZE:
            boundary = _find_breakpoint(text, start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _find_breakpoint(text: str, start: int, end: int) -> int:
    break_chars = "。！？\n；"
    search_start = min(end, len(text)) - 1
    minimum = start + MIN_CHUNK_SIZE
    for index in range(search_start, minimum - 1, -1):
        if text[index] in break_chars:
            return index + 1
    return end


def _build_chunk_id(chapter: Chapter, order: int) -> str:
    return f"rag_book_{chapter.textbook_id}_chapter_{chapter.id}_{order}"[:255]


def _normalize_vector(raw_vector: Any) -> dict[str, float]:
    if not isinstance(raw_vector, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, value in raw_vector.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            normalized[str(key)] = number
    return normalized


__all__ = [
    "build_rag_index",
    "query_rag",
]
