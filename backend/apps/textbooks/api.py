from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import Q
from ninja import File, Form, Query, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.textbooks.models import (
    KnowledgeEdge,
    KnowledgeNode,
    PipelineRun,
    RagChunk,
    Textbook,
)
from apps.textbooks.schemas import PipelineRunIn, RagQueryIn, TeacherChatIn
from apps.textbooks.services.pipeline import run_pipeline
from apps.textbooks.services.rag import build_rag_index, query_rag
from apps.textbooks.services.reporting import generate_report
from apps.textbooks.services.teacher import apply_teacher_feedback

router = Router(tags=["textbooks"])

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


@router.post("/textbooks/upload")
def upload_textbooks(
    request,
    files: list[UploadedFile] = File(...),
    mode: str = Form("demo"),
) -> dict[str, Any]:
    textbooks = []
    for uploaded_file in files:
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HttpError(400, f"Unsupported file format: {extension or 'unknown'}")

    for uploaded_file in files:
        extension = Path(uploaded_file.name).suffix.lower()
        textbook = Textbook.objects.create(
            filename=uploaded_file.name,
            original_name=uploaded_file.name,
            file_format=extension.removeprefix("."),
            file_size=uploaded_file.size or 0,
            title=Path(uploaded_file.name).stem,
            processing_mode=_normalize_mode(mode),
        )
        textbook.file.save(uploaded_file.name, uploaded_file, save=True)
        textbooks.append(_serialize_textbook(textbook))

    return {"data": {"textbooks": textbooks}, "message": "uploaded"}


@router.post("/pipeline/run")
def run_textbook_pipeline(request, payload: PipelineRunIn) -> dict[str, Any]:
    textbook_ids = [int(textbook_id) for textbook_id in payload.textbook_ids]
    mode = _normalize_mode(payload.mode)
    textbooks = list(Textbook.objects.filter(id__in=textbook_ids).order_by("id"))
    found_ids = {textbook.id for textbook in textbooks}
    missing_ids = [
        textbook_id for textbook_id in textbook_ids if textbook_id not in found_ids
    ]
    if missing_ids:
        raise HttpError(400, f"Unknown textbook ids: {missing_ids}")

    Textbook.objects.filter(id__in=textbook_ids).update(processing_mode=mode)
    run = PipelineRun.objects.create(mode=mode)
    run.textbooks.set(textbooks)
    result = run_pipeline(run.id)
    run.refresh_from_db()
    return {
        "data": {
            "run_id": run.id,
            "status": _serialize_pipeline_run(run),
            "result": result,
        },
        "message": "pipeline completed",
    }


@router.get("/pipeline/status")
def pipeline_status(request, run_id: int | None = Query(None)) -> dict[str, Any]:
    run = _get_pipeline_run(run_id)
    return {"data": _serialize_pipeline_run(run), "message": "ok"}


@router.get("/graph")
def graph(request, integrated: bool = Query(False)) -> dict[str, Any]:
    nodes = KnowledgeNode.objects.select_related("textbook", "chapter").order_by(
        "node_id"
    )
    if integrated:
        nodes = nodes.filter(is_integrated=True)
    node_ids = list(nodes.values_list("id", flat=True))
    edges = KnowledgeEdge.objects.filter(
        Q(source_id__in=node_ids) | Q(target_id__in=node_ids)
    ).select_related("source", "target")
    return {
        "data": {
            "nodes": [_serialize_node(node) for node in nodes],
            "edges": [_serialize_edge(edge) for edge in edges],
        },
        "message": "ok",
    }


@router.post("/rag/index")
def rag_index(request, payload: PipelineRunIn | None = None) -> dict[str, Any]:
    textbook_ids = payload.textbook_ids if payload is not None else []
    result = build_rag_index(textbook_ids)
    return {"data": result, "message": "indexed"}


@router.get("/rag/status")
def rag_status(request) -> dict[str, Any]:
    return {
        "data": {
            "chunks": RagChunk.objects.count(),
            "textbooks": RagChunk.objects.values("textbook_id").distinct().count(),
        },
        "message": "ok",
    }


@router.post("/rag/query")
def rag_query(request, payload: RagQueryIn) -> dict[str, Any]:
    if not payload.question.strip():
        raise HttpError(400, "Question is required")
    return {"data": query_rag(payload.question), "message": "ok"}


@router.post("/teacher/chat")
def teacher_chat(request, payload: TeacherChatIn) -> dict[str, Any]:
    if not payload.message.strip():
        raise HttpError(400, "Message is required")
    result = apply_teacher_feedback(payload.message, payload.decision_id)
    return {"data": result, "message": "ok"}


@router.get("/report")
def report(request) -> dict[str, Any]:
    textbook_ids = list(Textbook.objects.order_by("id").values_list("id", flat=True))
    latest_run = PipelineRun.objects.order_by("-created_at", "-id").first()
    content = ""
    if latest_run and latest_run.summary.get("report"):
        content = str(latest_run.summary["report"])
    else:
        content = generate_report(textbook_ids)
    return {"data": {"report": content}, "message": "ok"}


def _normalize_mode(mode: str) -> str:
    normalized = (mode or Textbook.ProcessingMode.DEMO).strip().lower()
    allowed_modes = {choice for choice, _label in Textbook.ProcessingMode.choices}
    if normalized not in allowed_modes:
        raise HttpError(400, f"Unsupported processing mode: {mode}")
    return normalized


def _get_pipeline_run(run_id: int | None) -> PipelineRun:
    if run_id is not None:
        run = PipelineRun.objects.filter(id=run_id).first()
    else:
        run = PipelineRun.objects.order_by("-created_at", "-id").first()
    if run is None:
        raise HttpError(404, "Pipeline run not found")
    return run


def _serialize_textbook(textbook: Textbook) -> dict[str, Any]:
    return {
        "id": textbook.id,
        "filename": textbook.filename,
        "original_name": textbook.original_name,
        "file_format": textbook.file_format,
        "file_size": textbook.file_size,
        "title": textbook.title,
        "parse_status": textbook.parse_status,
        "processing_mode": textbook.processing_mode,
    }


def _serialize_pipeline_run(run: PipelineRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "mode": run.mode,
        "status": run.status,
        "current_stage": run.current_stage,
        "progress": run.progress,
        "errors": run.errors,
        "summary": run.summary,
        "textbook_ids": list(run.textbooks.values_list("id", flat=True)),
    }


def _serialize_node(node: KnowledgeNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "node_id": node.node_id,
        "name": node.name,
        "definition": node.definition,
        "category": node.category,
        "page": node.page,
        "frequency": node.frequency,
        "is_integrated": node.is_integrated,
        "source_node_ids": node.source_node_ids,
        "textbook_id": node.textbook_id,
        "chapter_id": node.chapter_id,
    }


def _serialize_edge(edge: KnowledgeEdge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "source": edge.source.node_id,
        "target": edge.target.node_id,
        "relation_type": edge.relation_type,
        "description": edge.description,
    }


__all__ = ["router"]
