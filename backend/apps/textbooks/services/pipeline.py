from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from apps.textbooks.models import Chapter, PipelineRun, Textbook
from apps.textbooks.services import ai as ai_service
from apps.textbooks.services.graph_builder import build_graph_for_textbook
from apps.textbooks.services.integration import run_integration
from apps.textbooks.services.parser import parse_textbook
from apps.textbooks.services.rag import build_rag_index
from apps.textbooks.services.reporting import generate_report

STAGE_PARSE = "parse"
STAGE_GRAPH = "graph"
STAGE_INTEGRATE = "integrate"
STAGE_RAG = "rag"
STAGE_REPORT = "report"
STAGES = [STAGE_PARSE, STAGE_GRAPH, STAGE_INTEGRATE, STAGE_RAG, STAGE_REPORT]
STAGE_PROGRESS = {
    STAGE_PARSE: 20,
    STAGE_GRAPH: 40,
    STAGE_INTEGRATE: 60,
    STAGE_RAG: 80,
    STAGE_REPORT: 100,
}


class PipelineState(TypedDict, total=False):
    run_id: int
    textbook_ids: list[int]
    errors: list[str]
    summary: dict[str, Any]


def run_pipeline(run_id: int) -> dict[str, Any]:
    textbook_ids = list(
        PipelineRun.objects.get(id=run_id).textbooks.values_list("id", flat=True)
    )
    state: PipelineState = {
        "run_id": int(run_id),
        "textbook_ids": textbook_ids,
        "errors": [],
        "summary": {},
    }
    return PIPELINE_GRAPH.invoke(state)


def parse_node(state: PipelineState) -> PipelineState:
    run = _get_run(state)
    _update_run(
        run, status=PipelineRun.Status.RUNNING, current_stage=STAGE_PARSE, progress=0
    )

    errors = list(state.get("errors", []))
    textbook_ids = state.get("textbook_ids", [])
    textbooks = list(Textbook.objects.filter(id__in=textbook_ids).order_by("id"))

    for textbook in textbooks:
        try:
            if not textbook.file:
                raise FileNotFoundError(f"Textbook file missing for {textbook.id}")
            parsed = parse_textbook(
                Path(textbook.file.path), textbook.filename, textbook.processing_mode
            )
            textbook.chapters.all().delete()
            chapters = []
            for chapter in parsed.chapters:
                chapters.append(
                    Chapter(
                        textbook=textbook,
                        chapter_id=chapter.chapter_id,
                        title=chapter.title,
                        page_start=chapter.page_start,
                        page_end=chapter.page_end,
                        content=chapter.content,
                        char_count=chapter.char_count,
                        order=chapter.order,
                    )
                )
            Chapter.objects.bulk_create(chapters)
            textbook.title = textbook.title or parsed.title
            textbook.total_pages = parsed.total_pages
            textbook.total_chars = parsed.total_chars
            textbook.parse_status = Textbook.ParseStatus.COMPLETED
            textbook.error_message = ""
            textbook.save(
                update_fields=[
                    "title",
                    "total_pages",
                    "total_chars",
                    "parse_status",
                    "error_message",
                    "updated_at",
                ]
            )
        except Exception as exc:  # noqa: BLE001
            textbook.parse_status = Textbook.ParseStatus.FAILED
            textbook.error_message = str(exc)
            textbook.save(update_fields=["parse_status", "error_message", "updated_at"])
            errors.append(f"textbook:{textbook.id}: {exc}")

    _update_run(run, current_stage=STAGE_PARSE, progress=STAGE_PROGRESS[STAGE_PARSE])
    return {"errors": errors, "summary": state.get("summary", {})}


def graph_node(state: PipelineState) -> PipelineState:
    run = _get_run(state)
    _update_run(run, current_stage=STAGE_GRAPH, progress=STAGE_PROGRESS[STAGE_GRAPH])

    errors = list(state.get("errors", []))
    try:
        textbooks = list(Textbook.objects.filter(id__in=state.get("textbook_ids", [])))
        for textbook in textbooks:
            if textbook.parse_status == Textbook.ParseStatus.COMPLETED:
                build_graph_for_textbook(textbook, ai_service.DeepSeekClient())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"graph: {exc}")

    return {"errors": errors, "summary": state.get("summary", {})}


def integrate_node(state: PipelineState) -> PipelineState:
    run = _get_run(state)
    _update_run(
        run, current_stage=STAGE_INTEGRATE, progress=STAGE_PROGRESS[STAGE_INTEGRATE]
    )

    errors = list(state.get("errors", []))
    summary = dict(state.get("summary", {}))
    try:
        integration_result = run_integration(state.get("textbook_ids", []))
        summary["integration"] = integration_result
    except Exception as exc:  # noqa: BLE001
        errors.append(f"integrate: {exc}")

    return {"errors": errors, "summary": summary}


def rag_node(state: PipelineState) -> PipelineState:
    run = _get_run(state)
    _update_run(run, current_stage=STAGE_RAG, progress=STAGE_PROGRESS[STAGE_RAG])

    errors = list(state.get("errors", []))
    summary = dict(state.get("summary", {}))
    try:
        rag_result = build_rag_index(state.get("textbook_ids", []))
        summary["rag"] = rag_result
    except Exception as exc:  # noqa: BLE001
        errors.append(f"rag: {exc}")

    return {"errors": errors, "summary": summary}


def report_node(state: PipelineState) -> PipelineState:
    run = _get_run(state)
    _update_run(run, current_stage=STAGE_REPORT, progress=STAGE_PROGRESS[STAGE_REPORT])

    errors = list(state.get("errors", []))
    summary = dict(state.get("summary", {}))
    try:
        summary["report"] = generate_report(state.get("textbook_ids", []))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"report: {exc}")

    run.status = (
        PipelineRun.Status.COMPLETED if not errors else PipelineRun.Status.FAILED
    )
    run.current_stage = STAGE_REPORT
    run.progress = STAGE_PROGRESS[STAGE_REPORT]
    run.errors = errors
    run.summary = summary
    run.save(
        update_fields=[
            "status",
            "current_stage",
            "progress",
            "errors",
            "summary",
            "updated_at",
        ]
    )
    return {"errors": errors, "summary": summary}


def _get_run(state: PipelineState) -> PipelineRun:
    return PipelineRun.objects.get(id=state["run_id"])


def _update_run(run: PipelineRun, **changes: Any) -> None:
    for field_name, value in changes.items():
        setattr(run, field_name, value)
    update_fields = list(changes.keys()) + ["updated_at"]
    run.save(update_fields=update_fields)


def _build_pipeline_graph() -> StateGraph[PipelineState]:
    graph = StateGraph(PipelineState)
    graph.add_node(STAGE_PARSE, parse_node)
    graph.add_node(STAGE_GRAPH, graph_node)
    graph.add_node(STAGE_INTEGRATE, integrate_node)
    graph.add_node(STAGE_RAG, rag_node)
    graph.add_node(STAGE_REPORT, report_node)
    graph.add_edge(START, STAGE_PARSE)
    graph.add_edge(STAGE_PARSE, STAGE_GRAPH)
    graph.add_edge(STAGE_GRAPH, STAGE_INTEGRATE)
    graph.add_edge(STAGE_INTEGRATE, STAGE_RAG)
    graph.add_edge(STAGE_RAG, STAGE_REPORT)
    graph.add_edge(STAGE_REPORT, END)
    return graph


PIPELINE_GRAPH = _build_pipeline_graph().compile()
