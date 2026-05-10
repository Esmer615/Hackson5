from pathlib import Path

import pytest
from django.core.files import File

from apps.textbooks.models import (
    ConversationMessage,
    IntegrationDecision,
    KnowledgeNode,
    PipelineRun,
    RagChunk,
    Textbook,
)
from apps.textbooks.services import pipeline
from apps.textbooks.services.pipeline import report_node, run_pipeline
from apps.textbooks.services.reporting import generate_report
from apps.textbooks.services.teacher import apply_teacher_feedback


@pytest.mark.django_db
def test_run_pipeline_parses_txt_builds_graph_rag_and_completes(
    tmp_path: Path, settings
):
    settings.DEEPSEEK_API_KEY = ""
    settings.MEDIA_ROOT = tmp_path / "media"
    source_path = tmp_path / "physiology.txt"
    source_path.write_text(
        "# 第一章 绪论\n"
        "生理学研究稳态和细胞功能。稳态依赖神经调节和体液调节。\n"
        "# 第二章 循环\n"
        "血压影响微循环灌注，微循环参与物质交换。",
        encoding="utf-8",
    )
    textbook = Textbook.objects.create(
        filename="physiology.txt",
        original_name="physiology.txt",
        file_format="txt",
        file_size=source_path.stat().st_size,
        title="生理学",
        processing_mode=Textbook.ProcessingMode.DEMO,
    )
    with source_path.open("rb") as handle:
        textbook.file.save("physiology.txt", File(handle), save=True)
    run = PipelineRun.objects.create(mode=Textbook.ProcessingMode.DEMO)
    run.textbooks.add(textbook)

    result = run_pipeline(run.id)

    run.refresh_from_db()
    textbook.refresh_from_db()
    assert result["run_id"] == run.id
    assert result["errors"] == []
    assert run.status == PipelineRun.Status.COMPLETED
    assert run.current_stage == "report"
    assert run.progress == 100
    assert textbook.parse_status == Textbook.ParseStatus.COMPLETED
    assert textbook.chapters.count() == 2
    assert KnowledgeNode.objects.filter(textbook=textbook).exists()
    assert RagChunk.objects.filter(textbook=textbook).exists()
    assert "report" in run.summary
    assert "整合报告" in run.summary["report"]


@pytest.mark.django_db
def test_report_node_marks_run_failed_when_report_generation_fails(monkeypatch):
    run = PipelineRun.objects.create(mode=Textbook.ProcessingMode.DEMO)

    def raise_report_error(textbook_ids: list[int]) -> str:
        raise RuntimeError("report boom")

    monkeypatch.setattr(pipeline, "generate_report", raise_report_error)

    result = report_node(
        {
            "run_id": run.id,
            "textbook_ids": [],
            "errors": [],
            "summary": {"rag": {"chunk_count": 0}},
        }
    )

    run.refresh_from_db()
    assert run.status == PipelineRun.Status.FAILED
    assert run.current_stage == "report"
    assert run.progress == 100
    assert "report: report boom" in run.errors
    assert "report: report boom" in result["errors"]
    assert run.summary == {"rag": {"chunk_count": 0}}


@pytest.mark.django_db
def test_apply_teacher_feedback_changes_remove_decision_to_keep_and_records_history():
    decision = IntegrationDecision.objects.create(
        decision_id="remove_001",
        action=IntegrationDecision.Action.REMOVE,
        affected_node_ids=["node_a"],
        reason="重复知识点，建议删除。",
        confidence=0.73,
    )

    result = apply_teacher_feedback(
        "remove_001 这个知识点不要删除，请保留", decision.id
    )

    decision.refresh_from_db()
    messages = list(ConversationMessage.objects.filter(related_decision=decision))
    assert result["updated"] is True
    assert result["decision"]["decision_id"] == "remove_001"
    assert decision.action == IntegrationDecision.Action.KEEP
    assert decision.teacher_overridden is True
    assert [message.role for message in messages] == [
        ConversationMessage.Role.USER,
        ConversationMessage.Role.ASSISTANT,
    ]
    assert "已按教师反馈保留" in messages[1].content


@pytest.mark.django_db
def test_apply_teacher_feedback_can_find_decision_from_message_and_reports_missing():
    decision = IntegrationDecision.objects.create(
        decision_id="merge_007",
        action=IntegrationDecision.Action.MERGE,
        affected_node_ids=["node_a", "node_b"],
        reason="名称相近，自动合并。",
        confidence=0.88,
    )

    found = apply_teacher_feedback("请撤销 merge_007，这不是同一个概念", None)
    missing = apply_teacher_feedback("请保留 remove_404", None)

    decision.refresh_from_db()
    assert found["updated"] is True
    assert decision.action == IntegrationDecision.Action.KEEP
    assert decision.teacher_overridden is True
    assert missing["updated"] is False
    assert missing["decision"] is None
    assert (
        ConversationMessage.objects.filter(related_decision__isnull=True).count() == 2
    )


@pytest.mark.django_db
def test_generate_report_contains_required_sections():
    textbook = Textbook.objects.create(
        filename="pathology.txt",
        original_name="pathology.txt",
        file_format="txt",
        title="病理学",
        parse_status=Textbook.ParseStatus.COMPLETED,
        total_pages=1,
        total_chars=42,
    )
    node = KnowledgeNode.objects.create(
        textbook=textbook,
        node_id="node_inflammation",
        name="炎症",
        definition="机体对损伤的防御反应。",
    )
    IntegrationDecision.objects.create(
        decision_id="keep_001",
        action=IntegrationDecision.Action.KEEP,
        affected_node_ids=[node.node_id],
        result_node=node,
        reason="无重复知识点。",
        confidence=1.0,
    )

    report = generate_report([textbook.id])

    assert "# 整合报告" in report
    for section in [
        "整合概览",
        "整合决策摘要",
        "知识图谱统计",
        "重点整合案例",
        "教学完整性说明",
    ]:
        assert f"## {section}" in report
    assert "病理学" in report
    assert "keep_001" in report
