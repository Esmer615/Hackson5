from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from apps.textbooks.models import ConversationMessage, IntegrationDecision

DECISION_ID_RE = re.compile(r"\b(?:merge|keep|remove)_\d+\b", re.IGNORECASE)
KEEP_KEYWORDS = ("保留", "不要删除")
SEPARATE_KEYWORDS = ("分开", "撤销", "不是同一个")


def apply_teacher_feedback(
    message: str, decision_id: int | str | None
) -> dict[str, Any]:
    content = (message or "").strip()
    decision = _find_decision(content, decision_id)

    with transaction.atomic():
        ConversationMessage.objects.create(
            role=ConversationMessage.Role.USER,
            content=content,
            related_decision=decision,
        )
        if decision is None:
            assistant_content = (
                "未找到对应的整合决策，请提供如 "
                "merge_001、keep_001 或 remove_001 的编号。"
            )
            ConversationMessage.objects.create(
                role=ConversationMessage.Role.ASSISTANT,
                content=assistant_content,
                related_decision=None,
            )
            return {"updated": False, "message": assistant_content, "decision": None}

        updated = _should_keep(content)
        if updated:
            decision.action = IntegrationDecision.Action.KEEP
            decision.teacher_overridden = True
            decision.save(update_fields=["action", "teacher_overridden", "updated_at"])
            assistant_content = (
                f"已按教师反馈保留 {decision.decision_id}，后续报告将以教师意见为准。"
            )
        else:
            assistant_content = (
                f"{decision.decision_id} 的当前决策是 {decision.action}。"
                f"系统理由: {decision.reason or '暂无理由'}"
            )

        ConversationMessage.objects.create(
            role=ConversationMessage.Role.ASSISTANT,
            content=assistant_content,
            related_decision=decision,
        )
        return {
            "updated": updated,
            "message": assistant_content,
            "decision": _serialize_decision(decision),
        }


def _find_decision(
    message: str, decision_id: int | str | None
) -> IntegrationDecision | None:
    if decision_id not in (None, ""):
        query = IntegrationDecision.objects.filter(pk=decision_id).first()
        if query is not None:
            return query
        query = IntegrationDecision.objects.filter(decision_id=str(decision_id)).first()
        if query is not None:
            return query

    match = DECISION_ID_RE.search(message)
    if match is None:
        return None
    return IntegrationDecision.objects.filter(decision_id=match.group(0)).first()


def _should_keep(message: str) -> bool:
    return any(keyword in message for keyword in KEEP_KEYWORDS + SEPARATE_KEYWORDS)


def _serialize_decision(decision: IntegrationDecision) -> dict[str, Any]:
    return {
        "id": decision.id,
        "decision_id": decision.decision_id,
        "action": decision.action,
        "affected_node_ids": decision.affected_node_ids,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "teacher_overridden": decision.teacher_overridden,
    }


__all__ = ["apply_teacher_feedback"]
