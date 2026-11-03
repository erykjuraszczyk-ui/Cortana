import tempfile
import unittest
from pathlib import Path

from cortana_soul.semantic import (
    LongTermContextAssembler,
    SemanticMemoryStore,
    split_into_chunks,
)


class TinyEmbedder:
    dimension = 4

    def embed(self, text):
        lowered = text.lower()
        if "planet" in lowered or "orbital" in lowered:
            return (1.0, 0.0, 0.0, 0.0)
        if "python" in lowered or "program" in lowered:
            return (0.0, 1.0, 0.0, 0.0)
        return (0.0, 0.0, 1.0, 0.0)


class SemanticMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SemanticMemoryStore(Path(self.temp.name) / "semantic.sqlite3", TinyEmbedder())

    def tearDown(self):
        self.temp.cleanup()

    def test_ingestion_requires_consent(self):
        with self.assertRaises(PermissionError):
            self.store.ingest("Planet science notes", source="notes")

    def test_semantic_search_ranks_matching_embedding(self):
        self.store.ingest("Orbital mechanics and planets", source="astronomy", consent=True)
        self.store.ingest("Python programming basics", source="coding", consent=True)
        results = self.store.search("planet orbit", top_k=2)
        self.assertEqual(results[0].record.source, "astronomy")
        self.assertGreater(results[0].score, results[1].score)

    def test_search_validates_query_and_top_k(self):
        with self.assertRaises(ValueError):
            self.store.search(" ")
        with self.assertRaises(ValueError):
            self.store.search("planet", top_k=0)

    def test_document_delete_requires_confirmation(self):
        doc_id = self.store.ingest("Planet science notes", source="notes", consent=True)
        with self.assertRaises(PermissionError):
            self.store.delete_document(doc_id)
        self.assertEqual(self.store.delete_document(doc_id, confirmed=True), 1)
        self.assertEqual(self.store.search("planet"), ())

    def test_clear_all_requires_confirmation(self):
        self.store.ingest("Planet science notes", source="notes", consent=True)
        with self.assertRaises(PermissionError):
            self.store.clear_all()
        self.assertEqual(self.store.clear_all(confirmed=True), 1)

    def test_chunking_respects_maximum(self):
        chunks = split_into_chunks("word " * 500, max_chars=200, overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 200 for chunk in chunks))

    def test_context_assembler_is_bounded_and_attributed(self):
        self.store.ingest("Orbital mechanics and planets", source="astronomy", consent=True)
        results = self.store.search("planet orbit")
        context = LongTermContextAssembler(max_characters=200).assemble("planet orbit", results)
        self.assertEqual(len(context.items), 1)
        self.assertEqual(context.items[0].source, "astronomy")
        self.assertLessEqual(context.character_count, 200)

    def test_invalid_embedding_dimension_is_rejected(self):
        class BadEmbedder:
            dimension = 3
            def embed(self, text):
                return [1.0, 2.0]
        with self.assertRaises(ValueError):
            SemanticMemoryStore(Path(self.temp.name) / "bad.sqlite3", BadEmbedder())


if __name__ == "__main__":
    unittest.main()
