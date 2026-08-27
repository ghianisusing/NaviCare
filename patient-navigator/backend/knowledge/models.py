"""
Healthcare knowledge base models.

`embedding` is stored as a plain JSON list of floats via Django's
portable `JSONField` rather than a Postgres-specific vector column.
This keeps the project runnable against both the SQLite fallback (see
config/settings.py) and Postgres without an extension dependency.

If pgvector is available in a given deployment, `DocumentChunk.embedding`
is a natural column to migrate to `VectorField` for indexed similarity
search — see knowledge/retrieval.py for where that swap would happen;
nothing outside that module assumes the current in-Python cosine
similarity implementation.
"""

from django.db import models


class HealthcareDocument(models.Model):
    class Category(models.TextChoices):
        GENERAL_HEALTH = "general_health", "General Health"
        SYMPTOMS = "symptoms", "Symptoms"
        DIAGNOSTIC_TESTS = "diagnostic_tests", "Diagnostic Tests"
        PREVENTIVE_CARE = "preventive_care", "Preventive Care"
        COMMON_PROCEDURES = "common_procedures", "Common Procedures"
        HEALTHCARE_SERVICES = "healthcare_services", "Healthcare Services"

    title = models.CharField(max_length=255)
    content = models.TextField()
    source = models.CharField(max_length=255, help_text="Human-readable name of the source, e.g. publisher.")
    source_url = models.URLField(blank=True)
    category = models.CharField(max_length=32, choices=Category.choices)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "title"]

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(HealthcareDocument, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    chunk_index = models.PositiveIntegerField()
    embedding = models.JSONField(help_text="List of floats produced by knowledge/embeddings.py")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(fields=["document", "chunk_index"], name="unique_chunk_index_per_document")
        ]

    def __str__(self):
        return f"{self.document.title} [chunk {self.chunk_index}]"
