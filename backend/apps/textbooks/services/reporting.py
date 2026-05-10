from __future__ import annotations

from collections import Counter
from typing import Any

from apps.textbooks.models import (
    IntegrationDecision,
    KnowledgeEdge,
    KnowledgeNode,
    Textbook,
)


def generate_report(textbook_ids: list[int]) -> str:
    normalized_ids = [int(textbook_id) for textbook_id in textbook_ids if textbook_id]
    textbooks = list(Textbook.objects.filter(id__in=normalized_ids).order_by("id"))
    textbook_titles = [
        book.title or book.original_name or book.filename for book in textbooks
    ]
    decisions = _decisions_for_textbooks(normalized_ids)
    nodes = KnowledgeNode.objects.filter(textbook_id__in=normalized_ids)
    edges = KnowledgeEdge.objects.filter(source__textbook_id__in=normalized_ids)
    action_counts = Counter(decision.action for decision in decisions)
    teacher_override_count = sum(
        1 for decision in decisions if decision.teacher_overridden
    )

    lines = [
        "# 整合报告",
        "",
        "## 整合概览",
        f"- 教材数量: {len(textbooks)}",
        f"- 教材范围: {_join_or_default(textbook_titles, '暂无教材')}",
        f"- 章节数量: {sum(book.chapters.count() for book in textbooks)}",
        f"- 总字符数: {sum(book.total_chars for book in textbooks)}",
        "",
        "## 整合决策摘要",
        f"- 合并决策: {action_counts[IntegrationDecision.Action.MERGE]}",
        f"- 保留决策: {action_counts[IntegrationDecision.Action.KEEP]}",
        f"- 删除决策: {action_counts[IntegrationDecision.Action.REMOVE]}",
        f"- 教师覆盖: {teacher_override_count}",
        "",
        "## 知识图谱统计",
        f"- 知识点数量: {nodes.count()}",
        f"- 整合知识点数量: {nodes.filter(is_integrated=True).count()}",
        f"- 关系数量: {edges.count()}",
        "",
        "## 重点整合案例",
    ]
    lines.extend(_case_lines(decisions))
    lines.extend(
        [
            "",
            "## 教学完整性说明",
            "- 报告保留未被合并的独立知识点，避免因自动去重丢失教学要点。",
            "- 低置信度或教师覆盖的决策应在课堂使用前复核。",
            "- RAG 索引基于章节原文切分，可追溯到教材章节内容。",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _decisions_for_textbooks(textbook_ids: list[int]) -> list[IntegrationDecision]:
    if not textbook_ids:
        return list(IntegrationDecision.objects.none())

    node_ids = set(
        KnowledgeNode.objects.filter(textbook_id__in=textbook_ids).values_list(
            "node_id", flat=True
        )
    )
    decisions = list(
        IntegrationDecision.objects.filter(result_node__textbook_id__in=textbook_ids)
        .select_related("result_node")
        .order_by("decision_id")
    )
    seen_ids = {decision.id for decision in decisions}
    for decision in IntegrationDecision.objects.all().order_by("decision_id"):
        if decision.id in seen_ids:
            continue
        affected_ids = set(_as_string_list(decision.affected_node_ids))
        if affected_ids & node_ids:
            decisions.append(decision)
            seen_ids.add(decision.id)
    decisions.sort(key=lambda item: item.decision_id)
    return decisions


def _case_lines(decisions: list[IntegrationDecision]) -> list[str]:
    if not decisions:
        return ["- 暂无整合案例。"]

    case_lines: list[str] = []
    for decision in decisions[:5]:
        node_name = (
            decision.result_node.name if decision.result_node else "未生成结果节点"
        )
        affected = _join_or_default(_as_string_list(decision.affected_node_ids), "无")
        case_lines.append(
            "- "
            f"{decision.decision_id}: {decision.action} -> {node_name}; "
            f"影响节点: {affected}; 依据: {decision.reason or '暂无说明'}"
        )
    return case_lines


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _join_or_default(values: list[str], default: str) -> str:
    cleaned = [value for value in values if value]
    return "、".join(cleaned) if cleaned else default


__all__ = ["generate_report"]
