import pytest

from apps.textbooks.models import Chapter, KnowledgeEdge, KnowledgeNode, Textbook
from apps.textbooks.services.ai import (
    DeepSeekClient,
    extract_json_payload,
    fallback_extract_graph,
)
from apps.textbooks.services.graph_builder import build_graph_for_textbook


class FakeGraphClient:
    def extract_chapter_graph(
        self, *, textbook_title: str, chapter_title: str, content: str
    ):
        return {
            "nodes": [
                {
                    "name": "血压",
                    "definition": "动脉血对血管壁的侧压力。",
                    "category": "核心概念",
                },
                {
                    "name": "微循环",
                    "definition": "血液与组织液交换的场所。",
                    "category": "应用",
                },
            ],
            "edges": [
                {
                    "source": "血压",
                    "target": "微循环",
                    "relation_type": "applies_to",
                    "description": "血压变化会影响微循环灌注。",
                }
            ],
        }


class RaisingGraphClient:
    def extract_chapter_graph(
        self, *, textbook_title: str, chapter_title: str, content: str
    ):
        raise RuntimeError("graph extraction failed")


def test_extract_json_payload_accepts_fenced_json():
    payload = extract_json_payload(
        """
        Here is the graph:
        ```json
        {"nodes": [{"name": "神经元"}], "edges": []}
        ```
        """
    )

    assert payload == {"nodes": [{"name": "神经元"}], "edges": []}


def test_extract_json_payload_uses_later_parseable_fenced_block():
    payload = extract_json_payload(
        """
        Preliminary notes:
        ```python
        nodes = []
        edges = []
        ```
        Final graph:
        ```json
        {"nodes": [], "edges": []}
        ```
        """
    )

    assert payload == {"nodes": [], "edges": []}


def test_fallback_extract_graph_returns_allowed_nodes_and_edges():
    payload = fallback_extract_graph(
        textbook_title="生理学",
        chapter_title="第一章 绪论",
        content="生理学研究稳态与内环境，细胞和器官共同维持功能。",
    )

    assert len(payload["nodes"]) >= 2
    assert len(payload["edges"]) >= 1
    assert {edge["relation_type"] for edge in payload["edges"]} <= {
        "prerequisite",
        "parallel",
        "contains",
        "applies_to",
    }


@pytest.mark.django_db
def test_build_graph_for_textbook_creates_nodes_and_applies_to_edge_using_fake_client():
    textbook = Textbook.objects.create(
        filename="hemodynamics.txt",
        original_name="hemodynamics.txt",
        file_format="txt",
        title="血流动力学",
    )
    Chapter.objects.create(
        textbook=textbook,
        chapter_id="ch_001",
        title="第一章 血流动力学",
        content="血压变化会影响微循环灌注。",
        page_start=3,
        page_end=5,
        order=1,
    )

    result = build_graph_for_textbook(textbook, FakeGraphClient())

    assert result == {"nodes": 2, "edges": 1}
    assert KnowledgeNode.objects.filter(textbook=textbook).count() == 2
    edge = KnowledgeEdge.objects.get()
    assert edge.relation_type == KnowledgeEdge.RelationType.APPLIES_TO
    assert edge.source.name == "血压"
    assert edge.target.name == "微循环"


@pytest.mark.django_db
def test_build_graph_for_textbook_uses_unique_node_ids_across_textbooks():
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
    for textbook in [textbook_a, textbook_b]:
        Chapter.objects.create(
            textbook=textbook,
            chapter_id="ch_001",
            title="第一章 血流动力学",
            content="血压变化会影响微循环灌注。",
            page_start=3,
            page_end=5,
            order=1,
        )

    build_graph_for_textbook(textbook_a, FakeGraphClient())
    build_graph_for_textbook(textbook_b, FakeGraphClient())

    node_ids = list(
        KnowledgeNode.objects.order_by("node_id").values_list("node_id", flat=True)
    )
    assert len(node_ids) == 4
    assert len(set(node_ids)) == 4

    textbook = Textbook.objects.create(
        filename="hemodynamics.txt",
        original_name="hemodynamics.txt",
        file_format="txt",
        title="血流动力学",
    )
    chapter = Chapter.objects.create(
        textbook=textbook,
        chapter_id="ch_001",
        title="第一章 血流动力学",
        content="血压变化会影响微循环灌注。",
        page_start=3,
        page_end=5,
        order=1,
    )
    node = KnowledgeNode.objects.create(
        textbook=textbook,
        chapter=chapter,
        node_id="ch_001_1_血压",
        name="血压",
    )
    KnowledgeEdge.objects.create(
        source=node,
        target=node,
        relation_type=KnowledgeEdge.RelationType.APPLIES_TO,
        description="self edge for rollback test",
    )

    with pytest.raises(RuntimeError, match="graph extraction failed"):
        build_graph_for_textbook(textbook, RaisingGraphClient())

    assert KnowledgeNode.objects.filter(textbook=textbook).count() == 1
    assert KnowledgeEdge.objects.filter(source__textbook=textbook).count() == 1


def test_deepseek_client_falls_back_without_api_key(settings):
    settings.DEEPSEEK_API_KEY = ""
    client = DeepSeekClient()

    graph = client.extract_chapter_graph(
        textbook_title="药理学",
        chapter_title="第一章 总论",
        content="药物作用影响受体和效应器。",
    )
    answer = client.answer_with_context(
        question="药物作用和受体有什么关系？",
        contexts=[
            {
                "textbook": "药理学",
                "chapter": "第一章 总论",
                "content": "药物通过与受体结合产生效应。",
            }
        ],
    )

    assert len(graph["nodes"]) >= 2
    assert "药物通过与受体结合产生效应。" in answer
    assert "药理学" in answer
    assert "第一章 总论" in answer
