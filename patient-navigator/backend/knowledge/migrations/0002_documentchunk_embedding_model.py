from django.db import migrations, models


def label_existing_chunks(apps, schema_editor):
    # Every chunk stored before this migration came from the local
    # word-hashing vectorizer; its model id encodes the vector length.
    DocumentChunk = apps.get_model("knowledge", "DocumentChunk")
    for chunk in DocumentChunk.objects.filter(embedding_model="").iterator():
        chunk.embedding_model = f"local-hash-{len(chunk.embedding or [])}"
        chunk.save(update_fields=["embedding_model"])


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentchunk",
            name="embedding_model",
            field=models.CharField(db_index=True, default="", max_length=100),
        ),
        migrations.RunPython(label_existing_chunks, migrations.RunPython.noop),
    ]
