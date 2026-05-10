import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.textbooks.models import (
    Chapter,
    ConversationMessage,
    IntegrationDecision,
    KnowledgeEdge,
    KnowledgeNode,
    PipelineRun,
    RagChunk,
    Textbook,
)


@pytest.mark.django_db
def test_textbook_graph_and_rag_models_store_demo_state():
    textbook = Textbook.objects.create(
        filename="生理学.txt",
        original_name="生理学.txt",
        file_format="txt",
        file_size=128,
        title="生理学",
        total_pages=1,
        total_chars=42,
        parse_status=Textbook.ParseStatus.COMPLETED,
        processing_mode=Textbook.ProcessingMode.DEMO,
    )
    chapter = Chapter.objects.create(
        textbook=textbook,
        chapter_id="ch_001",
        title="第一章 绪论",
        page_start=1,
        page_end=1,
        content="生理学是研究生命活动规律的科学。",
        char_count=18,
        order=1,
    )
    node = KnowledgeNode.objects.create(
        textbook=textbook,
        chapter=chapter,
        node_id="book_1_node_1",
        name="生理学",
        definition="研究生命活动规律的科学。",
        category="核心概念",
        page=1,
        frequency=1,
    )
    target = KnowledgeNode.objects.create(
        textbook=textbook,
        chapter=chapter,
        node_id="book_1_node_2",
        name="稳态",
        definition="内环境保持相对稳定。",
        category="核心概念",
        page=1,
        frequency=1,
    )
    edge = KnowledgeEdge.objects.create(
        source=node,
        target=target,
        relation_type=KnowledgeEdge.RelationType.PREREQUISITE,
        description="理解稳态需要先了解生理学。",
    )
    decision = IntegrationDecision.objects.create(
        decision_id="merge_001",
        action=IntegrationDecision.Action.MERGE,
        affected_node_ids=[node.id, target.id],
        result_node=node,
        reason="两个知识点在演示数据中合并展示。",
        confidence=0.91,
    )
    chunk = RagChunk.objects.create(
        textbook=textbook,
        chapter=chapter,
        chunk_id="chunk_001",
        content="生理学是研究生命活动规律的科学。",
        page_start=1,
        page_end=1,
        order=1,
        vector={"生理": 0.5, "理学": 0.5},
    )
    message = ConversationMessage.objects.create(
        role=ConversationMessage.Role.USER,
        content="请保留稳态。",
        related_decision=decision,
    )
    run = PipelineRun.objects.create(
        mode=Textbook.ProcessingMode.DEMO,
        status=PipelineRun.Status.COMPLETED,
        current_stage="report",
        progress=100,
    )
    run.textbooks.add(textbook)

    assert str(textbook) == "生理学.txt"
    assert edge.relation_type == "prerequisite"
    assert decision.affected_node_ids == [node.id, target.id]
    assert chunk.vector["生理"] == 0.5
    assert message.role == "user"
    assert run.textbooks.count() == 1


@pytest.mark.django_db
def test_chapter_duplicate_chapter_id_within_textbook_violates_unique_constraint():
    textbook = Textbook.objects.create(
        filename="book-a.txt",
        original_name="book-a.txt",
        file_format="txt",
    )
    Chapter.objects.create(
        textbook=textbook,
        chapter_id="ch_001",
        title="Chapter 1",
    )

    with pytest.raises(IntegrityError):
        Chapter.objects.create(
            textbook=textbook,
            chapter_id="ch_001",
            title="Duplicate Chapter 1",
        )


@pytest.mark.django_db
def test_knowledge_node_save_rejects_mismatched_textbook_and_chapter():
    textbook_a = Textbook.objects.create(
        filename="book-a.txt",
        original_name="book-a.txt",
        file_format="txt",
    )
    textbook_b = Textbook.objects.create(
        filename="book-b.txt",
        original_name="book-b.txt",
        file_format="txt",
    )
    chapter_b = Chapter.objects.create(
        textbook=textbook_b,
        chapter_id="ch_b_001",
        title="Chapter B1",
    )

    with pytest.raises(ValidationError, match="chapter.*textbook"):
        KnowledgeNode.objects.create(
            textbook=textbook_a,
            chapter=chapter_b,
            node_id="node_mismatch",
            name="Mismatch",
        )


@pytest.mark.django_db
def test_rag_chunk_save_rejects_mismatched_textbook_and_chapter():
    textbook_a = Textbook.objects.create(
        filename="book-a.txt",
        original_name="book-a.txt",
        file_format="txt",
    )
    textbook_b = Textbook.objects.create(
        filename="book-b.txt",
        original_name="book-b.txt",
        file_format="txt",
    )
    chapter_b = Chapter.objects.create(
        textbook=textbook_b,
        chapter_id="ch_b_001",
        title="Chapter B1",
    )

    with pytest.raises(ValidationError, match="chapter.*textbook"):
        RagChunk.objects.create(
            textbook=textbook_a,
            chapter=chapter_b,
            chunk_id="chunk_mismatch",
            content="Mismatch",
        )


@pytest.mark.django_db
def test_integration_decision_confidence_out_of_range_fails_validation_on_save():
    with pytest.raises(ValidationError):
        IntegrationDecision.objects.create(
            decision_id="decision_low",
            action=IntegrationDecision.Action.KEEP,
            confidence=-0.01,
        )

    with pytest.raises(ValidationError):
        IntegrationDecision.objects.create(
            decision_id="decision_high",
            action=IntegrationDecision.Action.KEEP,
            confidence=1.01,
        )

    with pytest.raises(ValidationError):
        IntegrationDecision.objects.create(
            decision_id="decision_too_high",
            action=IntegrationDecision.Action.KEEP,
            confidence=1.5,
        )


@pytest.mark.django_db
def test_json_defaults_are_independent_objects():
    node_one = KnowledgeNode.objects.create(node_id="node_1", name="Node 1")
    node_two = KnowledgeNode.objects.create(node_id="node_2", name="Node 2")
    decision_one = IntegrationDecision.objects.create(
        decision_id="decision_1",
        action=IntegrationDecision.Action.KEEP,
    )
    decision_two = IntegrationDecision.objects.create(
        decision_id="decision_2",
        action=IntegrationDecision.Action.KEEP,
    )
    chunk_one = RagChunk.objects.create(
        textbook=Textbook.objects.create(
            filename="book-c.txt",
            original_name="book-c.txt",
            file_format="txt",
        ),
        chunk_id="chunk_1",
        content="Chunk 1",
    )
    chunk_two = RagChunk.objects.create(
        textbook=Textbook.objects.create(
            filename="book-d.txt",
            original_name="book-d.txt",
            file_format="txt",
        ),
        chunk_id="chunk_2",
        content="Chunk 2",
    )
    run_one = PipelineRun.objects.create(mode=Textbook.ProcessingMode.DEMO)
    run_two = PipelineRun.objects.create(mode=Textbook.ProcessingMode.QUALITY)

    node_one.source_node_ids.append("source-a")
    node_one.save(update_fields=["source_node_ids"])
    decision_one.affected_node_ids.append("node-1")
    decision_one.save(update_fields=["affected_node_ids"])
    chunk_one.vector["x"] = 1.0
    chunk_one.save(update_fields=["vector"])
    run_one.errors.append("error-a")
    run_one.summary["count"] = 1
    run_one.save(update_fields=["errors", "summary"])

    node_two.refresh_from_db()
    decision_two.refresh_from_db()
    chunk_two.refresh_from_db()
    run_two.refresh_from_db()

    assert node_one.source_node_ids == ["source-a"]
    assert node_two.source_node_ids == []
    assert decision_one.affected_node_ids == ["node-1"]
    assert decision_two.affected_node_ids == []
    assert chunk_one.vector == {"x": 1.0}
    assert chunk_two.vector == {}
    assert run_one.errors == ["error-a"]
    assert run_two.errors == []
    assert run_one.summary == {"count": 1}
    assert run_two.summary == {}
