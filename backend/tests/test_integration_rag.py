import pytest

from apps.textbooks.models import (
    Chapter,
    IntegrationDecision,
    KnowledgeNode,
    RagChunk,
    Textbook,
)
from apps.textbooks.services.ai import DeepSeekClient
from apps.textbooks.services.integration import run_integration, similarity_score
from apps.textbooks.services.rag import build_rag_index, query_rag


@pytest.mark.django_db
def test_run_integration_merges_similar_concepts_and_caps_compression_ratio():
    textbook_a = Textbook.objects.create(
        filename="pathology-a.txt",
        original_name="pathology-a.txt",
        file_format="txt",
        title="病理学 A",
    )
    textbook_b = Textbook.objects.create(
        filename="pathology-b.txt",
        original_name="pathology-b.txt",
        file_format="txt",
        title="病理学 B",
    )
    chapter_a = Chapter.objects.create(
        textbook=textbook_a,
        chapter_id="ch_a_001",
        title="第一章 炎症",
        content="炎症是机体对损伤因子的防御反应。",
        page_start=1,
        page_end=2,
        order=1,
    )
    chapter_b = Chapter.objects.create(
        textbook=textbook_b,
        chapter_id="ch_b_001",
        title="第一章 炎症反应",
        content="炎症反应涉及血管变化和细胞募集。",
        page_start=3,
        page_end=4,
        order=1,
    )
    node_a = KnowledgeNode.objects.create(
        textbook=textbook_a,
        chapter=chapter_a,
        node_id="node_a_inflammation",
        name="炎症",
        definition="机体对损伤因子的防御反应。",
        frequency=2,
        page=1,
    )
    node_b = KnowledgeNode.objects.create(
        textbook=textbook_b,
        chapter=chapter_b,
        node_id="node_b_inflammation_response",
        name="炎症反应",
        definition="炎症反应表现为血管变化和白细胞募集。",
        frequency=3,
        page=3,
    )
    node_c = KnowledgeNode.objects.create(
        textbook=textbook_b,
        chapter=chapter_b,
        node_id="node_c_pathogen",
        name="病原微生物",
        definition="可引起感染和炎症的微生物。",
        frequency=1,
        page=4,
    )

    first_result = run_integration([textbook_a.id, textbook_b.id])
    result = run_integration([textbook_a.id, textbook_b.id])

    assert first_result == result
    merged_node = KnowledgeNode.objects.get(is_integrated=True)
    merge_decision = IntegrationDecision.objects.get(
        action=IntegrationDecision.Action.MERGE
    )
    keep_decision = IntegrationDecision.objects.get(
        action=IntegrationDecision.Action.KEEP
    )

    assert result["merged"] == 1
    assert result["kept"] == 1
    assert result["removed"] == 2
    assert result["compression_ratio"] <= 0.3
    assert sorted(merged_node.source_node_ids) == sorted(
        [node_a.node_id, node_b.node_id]
    )
    assert merge_decision.result_node_id == merged_node.id
    assert sorted(merge_decision.affected_node_ids) == sorted(
        [node_a.node_id, node_b.node_id]
    )
    assert keep_decision.affected_node_ids == [node_c.node_id]


@pytest.mark.django_db
def test_build_rag_index_uses_unique_chunk_ids_across_textbooks():
    textbook_a = Textbook.objects.create(
        filename="a.txt",
        original_name="a.txt",
        file_format="txt",
        title="教材 A",
    )
    textbook_b = Textbook.objects.create(
        filename="b.txt",
        original_name="b.txt",
        file_format="txt",
        title="教材 B",
    )
    Chapter.objects.create(
        textbook=textbook_a,
        chapter_id="ch_001",
        title="第一章 炎症",
        content="炎症是防御反应。",
        order=1,
    )
    Chapter.objects.create(
        textbook=textbook_b,
        chapter_id="ch_001",
        title="第一章 免疫",
        content="免疫应答参与炎症。",
        order=1,
    )

    build_rag_index([textbook_a.id, textbook_b.id])

    chunk_ids = list(
        RagChunk.objects.order_by("chunk_id").values_list("chunk_id", flat=True)
    )
    assert len(chunk_ids) == 2
    assert len(set(chunk_ids)) == 2

    assert similarity_score("炎症", "炎症反应") > 0.45
    assert similarity_score("动作电位", "病原微生物") < 0.45


@pytest.mark.django_db
def test_build_rag_index_and_query_rag_return_inflammation_citations(settings):
    settings.DEEPSEEK_API_KEY = ""
    textbook = Textbook.objects.create(
        filename="pathology.txt",
        original_name="pathology.txt",
        file_format="txt",
        title="病理学",
    )
    chapter = Chapter.objects.create(
        textbook=textbook,
        chapter_id="ch_001",
        title="第一章 炎症",
        content=(
            "炎症是活体组织对损伤因子发生的防御反应。"
            "炎症的基本病理变化包括变质、渗出和增生。"
            "急性炎症常见中性粒细胞浸润。"
        ),
        page_start=10,
        page_end=12,
        order=1,
    )

    build_rag_index([textbook.id])
    result = query_rag("什么是炎症？", client=DeepSeekClient())

    chunk = RagChunk.objects.get(textbook=textbook, chapter=chapter)
    assert chunk.vector
    assert result["citations"]
    assert any(citation["chapter"] == "第一章 炎症" for citation in result["citations"])
    assert "炎症" in result["answer"]
    assert any(
        source_chunk["chapter"] == "第一章 炎症"
        for source_chunk in result["source_chunks"]
    )
