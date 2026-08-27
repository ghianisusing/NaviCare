from django.contrib import admin

from .models import DocumentChunk, HealthcareDocument


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    readonly_fields = ("chunk_index", "content", "created_at")
    fields = ("chunk_index", "content", "created_at")
    can_delete = False


@admin.register(HealthcareDocument)
class HealthcareDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "source", "updated_at")
    list_filter = ("category",)
    search_fields = ("title", "content", "source")
    inlines = [DocumentChunkInline]
