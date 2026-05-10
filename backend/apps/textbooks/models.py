from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def validate_chapter_textbook_consistency(instance: models.Model) -> None:
    chapter = getattr(instance, "chapter", None)
    textbook = getattr(instance, "textbook", None)
    if chapter is None or textbook is None:
        return
    if chapter.textbook_id != textbook.id:
        raise ValidationError(
            {"chapter": "chapter.textbook_id must match textbook_id when both are set."}
        )


class Textbook(models.Model):
    class ParseStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PARSING = "parsing", "Parsing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class ProcessingMode(models.TextChoices):
        DEMO = "demo", "Demo"
        QUALITY = "quality", "Quality"

    filename = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="textbooks/", blank=True)
    file_format = models.CharField(max_length=32)
    file_size = models.PositiveBigIntegerField(default=0)
    title = models.CharField(max_length=255, blank=True)
    total_pages = models.PositiveIntegerField(default=0)
    total_chars = models.PositiveIntegerField(default=0)
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.PENDING,
    )
    processing_mode = models.CharField(
        max_length=20,
        choices=ProcessingMode.choices,
        default=ProcessingMode.DEMO,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name or self.filename


class Chapter(models.Model):
    textbook = models.ForeignKey(
        Textbook,
        on_delete=models.CASCADE,
        related_name="chapters",
    )
    chapter_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    page_start = models.PositiveIntegerField(default=1)
    page_end = models.PositiveIntegerField(default=1)
    content = models.TextField(blank=True)
    char_count = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["textbook", "chapter_id"],
                name="unique_textbook_chapter_id",
            )
        ]
        ordering = ["textbook_id", "order", "id"]


class KnowledgeNode(models.Model):
    textbook = models.ForeignKey(
        Textbook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_nodes",
    )
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_nodes",
    )
    node_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    definition = models.TextField(blank=True)
    category = models.CharField(max_length=255, default="核心概念")
    page = models.PositiveIntegerField(default=1)
    frequency = models.PositiveIntegerField(default=1)
    source_node_ids = models.JSONField(default=list, blank=True)
    is_integrated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["node_id"]

    def clean(self) -> None:
        super().clean()
        validate_chapter_textbook_consistency(self)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class KnowledgeEdge(models.Model):
    class RelationType(models.TextChoices):
        PREREQUISITE = "prerequisite", "Prerequisite"
        PARALLEL = "parallel", "Parallel"
        CONTAINS = "contains", "Contains"
        APPLIES_TO = "applies_to", "Applies To"

    source = models.ForeignKey(
        KnowledgeNode,
        on_delete=models.CASCADE,
        related_name="outgoing_edges",
    )
    target = models.ForeignKey(
        KnowledgeNode,
        on_delete=models.CASCADE,
        related_name="incoming_edges",
    )
    relation_type = models.CharField(max_length=20, choices=RelationType.choices)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["source_id", "target_id", "id"]


class IntegrationDecision(models.Model):
    class Action(models.TextChoices):
        MERGE = "merge", "Merge"
        KEEP = "keep", "Keep"
        REMOVE = "remove", "Remove"

    decision_id = models.CharField(max_length=255, unique=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    affected_node_ids = models.JSONField(default=list, blank=True)
    result_node = models.ForeignKey(
        KnowledgeNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_decisions",
    )
    reason = models.TextField(blank=True)
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    teacher_overridden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "decision_id"]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RagChunk(models.Model):
    textbook = models.ForeignKey(
        Textbook, on_delete=models.CASCADE, related_name="rag_chunks"
    )
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rag_chunks",
    )
    chunk_id = models.CharField(max_length=255, unique=True)
    content = models.TextField()
    page_start = models.PositiveIntegerField(default=1)
    page_end = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    vector = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["textbook_id", "order", "id"]

    def clean(self) -> None:
        super().clean()
        validate_chapter_textbook_consistency(self)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    related_decision = models.ForeignKey(
        IntegrationDecision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversation_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class PipelineRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    textbooks = models.ManyToManyField(
        Textbook, related_name="pipeline_runs", blank=True
    )
    mode = models.CharField(max_length=20, choices=Textbook.ProcessingMode.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    current_stage = models.CharField(max_length=255, default="pending")
    progress = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
