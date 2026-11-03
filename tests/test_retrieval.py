import unittest
from dataclasses import dataclass

from cortana_soul.retrieval import BM25Index, HybridRetriever


@dataclass(frozen=True)
class Record:
    record_id: str
    text: str
    source: str = "test"
    document_id: str = "doc"
    created_at: str = "2026-01-01T00:00:00+00:00"


@dataclass(frozen=True)
class Result:
    record: Record
    score: float


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.alpha = Record("a", "Qdrant vector database stores embeddings")
        self.beta = Record("b", "BM25 lexical ranking matches exact terms")
        self.gamma = Record("c", "Local embeddings support semantic search")
        self.index = BM25Index()
        self.index.add([self.alpha, self.beta, self.gamma])

    def test_bm25_finds_exact_terms(self):
        results = self.index.search("Qdrant embeddings")
        self.assertEqual(results[0].record.record_id, "a")

    def test_bm25_empty_query_has_no_results(self):
        self.assertEqual(self.index.search("!!!"), ())

    def test_bm25_remove(self):
        self.assertTrue(self.index.remove("a"))
        self.assertEqual(self.index.search("Qdrant"), ())

    def test_bm25_replacing_record_updates_document_frequency(self):
        self.index.add([Record("a", "new content")])
        self.assertEqual(self.index.search("Qdrant"), ())

    def test_bm25_clear(self):
        self.index.clear()
        self.assertEqual(self.index.search("Qdrant"), ())

    def test_hybrid_merges_semantic_and_lexical_candidates(self):
        def semantic(query, top_k):
            return (Result(self.gamma, -0.5),)
        hybrid = HybridRetriever(semantic, self.index)
        results = hybrid.search("Qdrant embeddings", top_k=3)
        ids = [item.record.record_id for item in results]
        self.assertIn("a", ids)
        self.assertIn("c", ids)
        self.assertEqual(ids[0], "a")

    def test_hybrid_validates_weights(self):
        with self.assertRaises(ValueError):
            HybridRetriever(lambda *args, **kwargs: (), self.index,
                            semantic_weight=0, lexical_weight=0)

    def test_hybrid_validates_top_k(self):
        hybrid = HybridRetriever(lambda *args, **kwargs: (), self.index)
        with self.assertRaises(ValueError):
            hybrid.search("test", top_k=0)

    def test_weights_are_normalized(self):
        hybrid = HybridRetriever(lambda *args, **kwargs: (), self.index,
                                 semantic_weight=2, lexical_weight=2)
        self.assertEqual(hybrid.semantic_weight, 0.5)
        self.assertEqual(hybrid.lexical_weight, 0.5)


if __name__ == "__main__":
    unittest.main()
