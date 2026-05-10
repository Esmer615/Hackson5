from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.textbooks.models import Textbook


@pytest.mark.django_db
def test_textbooks_end_to_end_api_flow(settings, tmp_path):
    settings.DEEPSEEK_API_KEY = ""
    settings.MEDIA_ROOT = tmp_path / "media"
    client = Client()
    upload = SimpleUploadedFile(
        "physiology.txt",
        (
            "# 第一章 绪论\n"
            "生理学研究稳态和细胞功能。稳态依赖神经调节和体液调节。\n"
            "# 第二章 循环\n"
            "血压影响微循环灌注，微循环参与物质交换。"
        ).encode(),
        content_type="text/plain",
    )

    upload_response = client.post(
        "/api/textbooks/upload",
        {"files": [upload], "mode": "demo"},
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    textbook_id = upload_payload["data"]["textbooks"][0]["id"]
    assert upload_payload["message"] == "uploaded"
    assert Textbook.objects.filter(id=textbook_id, file_format="txt").exists()

    run_response = client.post(
        "/api/pipeline/run",
        {"textbook_ids": [textbook_id], "mode": "demo"},
        content_type="application/json",
    )

    assert run_response.status_code == 200
    run_payload = run_response.json()
    run_id = run_payload["data"]["run_id"]
    assert run_payload["data"]["status"]["progress"] == 100

    status_response = client.get("/api/pipeline/status", {"run_id": run_id})

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["data"]["status"] == "completed"
    assert status_payload["data"]["progress"] == 100

    graph_response = client.get("/api/graph")

    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["data"]["nodes"]

    rag_response = client.post(
        "/api/rag/query",
        {"question": "什么是稳态？"},
        content_type="application/json",
    )

    assert rag_response.status_code == 200
    assert rag_response.json()["data"]["answer"]

    teacher_response = client.post(
        "/api/teacher/chat",
        {"message": "请说明当前整合状态"},
        content_type="application/json",
    )

    assert teacher_response.status_code == 200
    assert teacher_response.json()["message"] == "ok"

    report_response = client.get("/api/report")

    assert report_response.status_code == 200
    assert "整合报告" in report_response.json()["data"]["report"]


@pytest.mark.django_db
def test_upload_unsupported_extension_returns_400(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    client = Client()
    upload = SimpleUploadedFile(
        "malware.exe",
        BytesIO(b"not a textbook").read(),
        content_type="application/octet-stream",
    )

    response = client.post("/api/textbooks/upload", {"files": [upload]})

    assert response.status_code == 400
    assert Textbook.objects.count() == 0
