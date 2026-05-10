from __future__ import annotations

from typing import Any, Protocol

from django.db import transaction

from apps.textbooks.models import KnowledgeEdge, KnowledgeNode, Textbook


class ChapterGraphClient(Protocol):
    def extract_chapter_graph(
        self,
        *,
        textbook_title: str,
        chapter_title: str,
        content: str,
    ) -> dict[str, list[dict[str, Any]]]: ...


def build_graph_for_textbook(
    textbook: Textbook,
    client: ChapterGraphClient,
) -> dict[str, int]:
    with transaction.atomic():
        KnowledgeEdge.objects.filter(
            source__textbook=textbook,
            source__is_integrated=False,
        ).delete()
        KnowledgeNode.objects.filter(textbook=textbook, is_integrated=False).delete()

        total_nodes = 0
        total_edges = 0

        for chapter in textbook.chapters.all().order_by("order", "id"):
            payload = client.extract_chapter_graph(
                textbook_title=textbook.title
                or textbook.original_name
                or textbook.filename,
                chapter_title=chapter.title,
                content=chapter.content,
            )
            nodes_by_name: dict[str, KnowledgeNode] = {}
            for index, node_data in enumerate(payload.get("nodes", []), start=1):
                if not isinstance(node_data, dict):
                    continue
                name = str(node_data.get("name", "")).strip()
                if not name or name in nodes_by_name:
                    continue
                node = KnowledgeNode.objects.create(
                    textbook=textbook,
                    chapter=chapter,
                    node_id=_build_node_id(textbook.id, chapter.id, name, index),
                    name=name,
                    definition=str(node_data.get("definition", "")).strip(),
                    category=str(node_data.get("category", "核心概念")).strip()
                    or "核心概念",
                    page=_coerce_positive_int(
                        node_data.get("page"), default=chapter.page_start or 1
                    ),
                    frequency=_coerce_positive_int(
                        node_data.get("frequency"), default=1
                    ),
                )
                nodes_by_name[name] = node
                total_nodes += 1

            for edge_data in payload.get("edges", []):
                if not isinstance(edge_data, dict):
                    continue
                source_name = str(edge_data.get("source", "")).strip()
                target_name = str(edge_data.get("target", "")).strip()
                relation_type = str(edge_data.get("relation_type", "")).strip()
                if source_name == target_name:
                    continue
                if relation_type not in KnowledgeEdge.RelationType.values:
                    continue
                source = nodes_by_name.get(source_name)
                target = nodes_by_name.get(target_name)
                if source is None or target is None:
                    continue
                KnowledgeEdge.objects.create(
                    source=source,
                    target=target,
                    relation_type=relation_type,
                    description=str(edge_data.get("description", "")).strip(),
                )
                total_edges += 1

        return {"nodes": total_nodes, "edges": total_edges}


def _build_node_id(textbook_id: int, chapter_id: int, name: str, index: int) -> str:
    safe_name = "".join(
        character if character.isalnum() else "_" for character in name.lower()
    )
    safe_name = "_".join(part for part in safe_name.split("_") if part)
    if not safe_name:
        safe_name = f"node_{index}"
    return f"book_{textbook_id}_chapter_{chapter_id}_{index}_{safe_name}"[:255]


def _coerce_positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
