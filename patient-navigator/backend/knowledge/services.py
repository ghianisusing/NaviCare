"""
Thin service wrapper tying document CRUD to ingestion, so the admin API
views stay simple: save the document, then (re-)ingest it.
"""

from .ingestion import ingest_document
from .models import HealthcareDocument


def create_document(**fields) -> HealthcareDocument:
    document = HealthcareDocument.objects.create(**fields)
    ingest_document(document)
    return document


def update_document(document: HealthcareDocument, **fields) -> HealthcareDocument:
    for field, value in fields.items():
        setattr(document, field, value)
    document.save()
    ingest_document(document)
    return document
