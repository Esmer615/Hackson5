from __future__ import annotations

import math
import re
from collections import Counter
from itertools import count

from django.db import transaction

from apps.textbooks.models import IntegrationDecision, KnowledgeNode

NGRAM_SIZE = 2
MAX_COMPRESSION_RATIO = 0.3


def run_integration(textbook_ids: list[int]) -> dict[str, float | int]:
    textbook_ids = [int(textbook_id) for textbook_id in textbook_ids if textbook_id]
    if not textbook_ids:
        return {"merged": 0, "kept": 0, "removed": 0, "compression_ratio": 0.0}

    with transaction.atomic():
        targeted_node_ids = set(
            KnowledgeNode.objects.filter(textbook_id__in=textbook_ids).values_list(
                "node_id",
                flat=True,
            )
        )
        IntegrationDecision.objects.filter(
            result_node__textbook_id__in=textbook_ids
        ).delete()
        decision_ids_to_delete = [
            decision.id
            for decision in IntegrationDecision.objects.only("id", "affected_node_ids")
            if targeted_node_ids.intersection(decision.affected_node_ids or [])
        ]
        if decision_ids_to_delete:
            IntegrationDecision.objects.filter(id__in=decision_ids_to_delete).delete()
        KnowledgeNode.objects.filter(
            is_integrated=True,
            textbook_id__in=textbook_ids,
        ).delete()

        nodes = list(
            KnowledgeNode.objects.filter(
                textbook_id__in=textbook_ids,
                is_integrated=False,
            )
            .select_related("textbook", "chapter")
            .order_by("id")
        )

        grouped_nodes = _group_similar_nodes(nodes)
        merged = 0
        kept = 0
        removed = 0
        original_chars = sum(len(_node_text(node)) for node in nodes)
        integrated_chars = 0

        for index, group in enumerate(grouped_nodes, start=1):
            if len(group) > 1:
                result_node = _create_integrated_node(group, index=index)
                merged += 1
                removed += len(group)
                integrated_chars += len(_node_text(result_node))
                IntegrationDecision.objects.create(
                    decision_id=_build_decision_id("merge", textbook_ids, index),
                    action=IntegrationDecision.Action.MERGE,
                    affected_node_ids=[node.node_id for node in group],
                    result_node=result_node,
                    reason="Merged similar concepts across textbooks.",
                    confidence=_bounded_confidence(
                        max(
                            similarity_score(result_node.name, node.name)
                            for node in group
                        )
                    ),
                )
                continue

            node = group[0]
            kept += 1
            integrated_chars += len(_node_text(node))
            IntegrationDecision.objects.create(
                decision_id=_build_decision_id("keep", textbook_ids, index),
                action=IntegrationDecision.Action.KEEP,
                affected_node_ids=[node.node_id],
                result_node=node,
                reason="No sufficiently similar concept found.",
                confidence=1.0,
            )

        compression_ratio = _compression_ratio(
            integrated_chars=integrated_chars,
            original_chars=original_chars,
        )
        return {
            "merged": merged,
            "kept": kept,
            "removed": removed,
            "compression_ratio": compression_ratio,
        }


def similarity_score(left: str, right: str) -> float:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    shorter, longer = sorted([normalized_left, normalized_right], key=len)
    if shorter and shorter in longer:
        return max(0.7, len(shorter) / len(longer))

    left_vector = text_to_vector(normalized_left)
    right_vector = text_to_vector(normalized_right)
    return cosine(left_vector, right_vector)


def text_to_vector(text: str, ngram_size: int = NGRAM_SIZE) -> dict[str, float]:
    normalized = _normalize_text(text)
    if not normalized:
        return {}
    grams = _char_ngrams(normalized, ngram_size=ngram_size)
    if not grams:
        grams = [normalized]
    counts = Counter(grams)
    total = float(sum(counts.values())) or 1.0
    return {token: value / total for token, value in counts.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    intersection = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in intersection)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _group_similar_nodes(
    nodes: list[KnowledgeNode], threshold: float = 0.45
) -> list[list[KnowledgeNode]]:
    groups: list[list[KnowledgeNode]] = []
    for node in nodes:
        best_index = -1
        best_score = threshold
        for index, group in enumerate(groups):
            score = max(similarity_score(node.name, other.name) for other in group)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index >= 0:
            groups[best_index].append(node)
        else:
            groups.append([node])
    return groups


def _create_integrated_node(group: list[KnowledgeNode], *, index: int) -> KnowledgeNode:
    textbook = group[0].textbook
    chapter = group[0].chapter
    name = min((node.name for node in group), key=len)
    definitions = [node.definition.strip() for node in group if node.definition.strip()]
    definition = " ".join(dict.fromkeys(definitions))
    if not definition:
        definition = f"{name}相关整合知识点。"
    category = Counter(node.category for node in group if node.category).most_common(1)[
        0
    ][0]
    page = min(node.page for node in group if node.page > 0)
    frequency = sum(node.frequency for node in group)
    source_node_ids = [node.node_id for node in group]

    node = KnowledgeNode(
        textbook=textbook,
        chapter=chapter,
        node_id=_unique_integrated_node_id(group=group, index=index, name=name),
        name=name,
        definition=definition,
        category=category,
        page=page,
        frequency=frequency,
        source_node_ids=source_node_ids,
        is_integrated=True,
    )
    node.save()
    return node


def _unique_integrated_node_id(
    *, group: list[KnowledgeNode], index: int, name: str
) -> str:
    textbook_id = group[0].textbook_id or 0
    seed = _slugify(name) or f"group_{index}"
    base = f"integrated_t{textbook_id}_{index}_{seed}"[:240]
    for suffix in count(0):
        candidate = base if suffix == 0 else f"{base}_{suffix}"
        candidate = candidate[:255]
        if not KnowledgeNode.objects.filter(node_id=candidate).exists():
            return candidate
    raise RuntimeError("Unable to generate unique integrated node_id")


def _build_decision_id(prefix: str, textbook_ids: list[int], index: int) -> str:
    joined = "_".join(str(textbook_id) for textbook_id in sorted(textbook_ids))
    return f"{prefix}_{joined}_{index}"[:255]


def _node_text(node: KnowledgeNode) -> str:
    return f"{node.name} {node.definition}".strip()


def _compression_ratio(*, integrated_chars: int, original_chars: int) -> float:
    if original_chars <= 0:
        return 0.0
    ratio = integrated_chars / original_chars
    return round(min(ratio, MAX_COMPRESSION_RATIO), 3)


def _bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def _normalize_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    return re.sub(r"[\W_]+", "", lowered)


def _slugify(text: str) -> str:
    normalized = _normalize_text(text)
    return normalized[:80]


def _char_ngrams(text: str, *, ngram_size: int) -> list[str]:
    if len(text) <= ngram_size:
        return [text]
    return [
        text[index : index + ngram_size] for index in range(len(text) - ngram_size + 1)
    ]


__all__ = [
    "cosine",
    "run_integration",
    "similarity_score",
    "text_to_vector",
]
