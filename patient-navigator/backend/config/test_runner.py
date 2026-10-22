"""
Test runner that pins the knowledge base to the offline word-hashing
embedder, so the suite never calls a paid embedding API or depends on
the network — even when a developer's .env sets EMBEDDING_PROVIDER.
Tests that exercise a hosted provider mock its HTTP call explicitly.
"""

import os

from django.test.runner import DiscoverRunner


class OfflineEmbeddingsTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        # An env var wins over .env in python-decouple; it's also
        # inherited by --parallel worker processes.
        os.environ["EMBEDDING_PROVIDER"] = "local"

        from knowledge.embeddings import set_embedding_provider

        set_embedding_provider(None)
        super().setup_test_environment(**kwargs)
