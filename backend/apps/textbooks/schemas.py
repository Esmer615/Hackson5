from ninja import Schema


class PipelineRunIn(Schema):
    textbook_ids: list[int]
    mode: str = "demo"


class RagQueryIn(Schema):
    question: str


class TeacherChatIn(Schema):
    message: str
    decision_id: int | str | None = None


class TextbookOut(Schema):
    id: int
    filename: str
    original_name: str
    file_format: str
    file_size: int
    title: str
    parse_status: str
    processing_mode: str
