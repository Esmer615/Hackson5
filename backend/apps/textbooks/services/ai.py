from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

import httpx
from django.conf import settings

ALLOWED_RELATIONS = {"prerequisite", "parallel", "contains", "applies_to"}
STOPWORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "that",
    "this",
    "these",
    "those",
    "chapter",
    "section",
    "lesson",
    "textbook",
    "book",
    "content",
    "page",
    "pages",
    "第一章",
    "第二章",
    "第三章",
    "第四章",
    "第五章",
    "第一节",
    "第二节",
    "第三节",
    "教材",
}

FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]+|[\u4e00-\u9fff]{2,12}")


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = getattr(settings, "DEEPSEEK_API_KEY", "") or ""
        self.base_url = getattr(
            settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self.model = getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")

    def extract_chapter_graph(
        self,
        *,
        textbook_title: str,
        chapter_title: str,
        content: str,
    ) -> dict[str, list[dict[str, Any]]]:
        if not self.api_key:
            return fallback_extract_graph(
                textbook_title=textbook_title,
                chapter_title=chapter_title,
                content=content,
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract knowledge graphs from textbook chapters. "
                        "Return only JSON with nodes and edges."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Textbook: {textbook_title}\n"
                        f"Chapter: {chapter_title}\n"
                        f"Content:\n{content}\n\n"
                        "Return JSON with keys nodes and edges."
                    ),
                },
            ],
            "temperature": 0.2,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content_text = data["choices"][0]["message"]["content"]
                graph_payload = extract_json_payload(content_text)
                return normalize_graph_payload(graph_payload)
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            httpx.HTTPError,
            json.JSONDecodeError,
        ):
            return fallback_extract_graph(
                textbook_title=textbook_title,
                chapter_title=chapter_title,
                content=content,
            )

    def answer_with_context(
        self, *, question: str, contexts: list[dict[str, Any]]
    ) -> str:
        if not self.api_key:
            return _deterministic_answer(question=question, contexts=contexts)

        prompt_lines = [
            "You answer questions using only the provided textbook context.",
            "Cite the textbook and chapter in a short, direct answer.",
            f"Question: {question}",
            "Context:",
        ]
        for index, context in enumerate(contexts, start=1):
            textbook = context.get("textbook", "")
            chapter = context.get("chapter", "")
            content = context.get("content", "")
            prompt_lines.append(f"{index}. 《{textbook}》{chapter}: {content}")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise RAG assistant."},
                {"role": "user", "content": "\n".join(prompt_lines)},
            ],
            "temperature": 0.2,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"]).strip()
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            httpx.HTTPError,
            json.JSONDecodeError,
        ):
            return _deterministic_answer(question=question, contexts=contexts)


def extract_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty JSON payload")

    for match in FENCE_RE.finditer(stripped):
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for start in _json_start_positions(stripped):
        try:
            payload, _ = decoder.raw_decode(stripped[start:])
            return payload
        except json.JSONDecodeError:
            continue

    raise ValueError("No JSON object found")


def normalize_graph_payload(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Graph payload must be a dictionary")

    raw_nodes = payload.get("nodes", [])
    raw_edges = payload.get("edges", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("Graph payload must contain node and edge lists")

    nodes: list[dict[str, Any]] = []
    node_names: set[str] = set()
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue
        name = str(raw_node.get("name", "")).strip()
        if not name or name in node_names:
            continue
        node_names.add(name)
        nodes.append(
            {
                "name": name,
                "definition": str(raw_node.get("definition", "")).strip(),
                "category": str(raw_node.get("category", "核心概念")).strip()
                or "核心概念",
                "page": _coerce_positive_int(raw_node.get("page"), default=1),
                "frequency": _coerce_positive_int(raw_node.get("frequency"), default=1),
            }
        )

    edges: list[dict[str, Any]] = []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            continue
        source = str(raw_edge.get("source", "")).strip()
        target = str(raw_edge.get("target", "")).strip()
        relation_type = str(raw_edge.get("relation_type", "")).strip()
        if (
            not source
            or not target
            or source == target
            or relation_type not in ALLOWED_RELATIONS
            or source not in node_names
            or target not in node_names
        ):
            continue
        edges.append(
            {
                "source": source,
                "target": target,
                "relation_type": relation_type,
                "description": str(raw_edge.get("description", "")).strip(),
            }
        )

    return {"nodes": nodes, "edges": edges}


def fallback_extract_graph(
    *,
    textbook_title: str,
    chapter_title: str,
    content: str,
) -> dict[str, list[dict[str, Any]]]:
    text = " ".join(
        part for part in [textbook_title, chapter_title, content] if part
    ).strip()
    candidates: list[str] = []
    for match in TERM_RE.finditer(text):
        term = match.group(0).strip()
        normalized = term.lower()
        if normalized in STOPWORDS:
            continue
        if term not in candidates:
            candidates.append(term)
        if len(candidates) >= 4:
            break

    if len(candidates) < 2:
        for fallback_term in [textbook_title, chapter_title, "核心概念", "知识点"]:
            term = str(fallback_term).strip()
            if term and term not in candidates:
                candidates.append(term)
            if len(candidates) >= 2:
                break

    if len(candidates) < 2:
        candidates.extend(["概念A", "概念B"][: 2 - len(candidates)])

    nodes: list[dict[str, Any]] = []
    for index, name in enumerate(candidates, start=1):
        nodes.append(
            {
                "name": name,
                "definition": f"{chapter_title or textbook_title}中的关键概念。"
                if index == 1
                else "相关知识点。",
                "category": "核心概念" if index == 1 else "相关概念",
                "page": 1,
                "frequency": 1,
            }
        )

    edges: list[dict[str, Any]] = []
    for left, right in zip(candidates, candidates[1:]):
        edges.append(
            {
                "source": left,
                "target": right,
                "relation_type": "parallel",
                "description": "Fallback association between candidate terms.",
            }
        )

    return {"nodes": nodes, "edges": edges}


def _deterministic_answer(*, question: str, contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return f"根据现有教材内容，暂未找到足够依据回答：{question}"

    first = contexts[0]
    textbook = str(first.get("textbook", "")).strip() or "未知教材"
    chapter = str(first.get("chapter", "")).strip() or "未知章节"
    content = str(first.get("content", "")).strip() or "暂无可引用内容"
    return f"根据《{textbook}》{chapter}：{content}"


def _json_start_positions(text: str) -> Iterable[int]:
    for index, char in enumerate(text):
        if char in "[{":
            yield index


def _coerce_positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
