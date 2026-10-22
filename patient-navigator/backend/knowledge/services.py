"""
Thin service wrapper tying document CRUD to ingestion, so the admin API
views stay simple: save the document, then (re-)ingest it.

Each is one transaction: if embedding fails, the document change is
rolled back too, so stored content never drifts from what's searchable.
"""

from django.db import transaction

from .ingestion import ingest_document
from .models import HealthcareDocument


@transaction.atomic
def create_document(**fields) -> HealthcareDocument:
    document = HealthcareDocument.objects.create(**fields)
    ingest_document(document)
    return document


@transaction.atomic
def update_document(document: HealthcareDocument, **fields) -> HealthcareDocument:
    for field, value in fields.items():
        setattr(document, field, value)
    document.save()
    ingest_document(document)
    return document
