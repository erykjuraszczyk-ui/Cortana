"""Dependency-free BM25 and hybrid retrieval over approved memory records."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .semantic import SemanticSearchResult


_TOKEN_RE = re.compile(r"[^\\W_]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    return tuple(token.casefold() for token in _TOKEN_RE.findall(text))


@dataclass(frozen=True)
class LexicalSearchResult:
    record: object
    score: float


class BM25Index:
    """Small in-process BM25 index. Rebuild from approved records at startup."""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        if (isinstance(k1, bool) or not isinstance(k1, (int, float))
                or not math.isfinite(k1) or k1 <= 0):
            raise ValueError("k1 must be positive and finite")
        if (isinstance(b, bool) or not isinstance(b, (int, float))
                or not math.isfinite(b) or not 0 <= b <= 1):
            raise ValueError("b must be between 0 and 1")
        self.k1, self.b = float(k1), float(b)
        self._documents: dict[str, tuple[object, tuple[str, ...], Counter]] = {}
        self._df: Counter = Counter()
        self._total_length = 0

    def add(self, records: Iterable[object]) -> None:
        for record in records:
            record_id = getattr(record, "record_id", None)
            text = getattr(record, "text", None)
            if not isinstance(record_id, str) or not isinstance(text, str):
                raise ValueError("records must expose string record_id and text fields")
            if record_id in self._documents:
                self.remove(record_id)
            terms = tokenize(text)
            counts = Counter(terms)
            self._documents[record_id] = (record, terms, counts)
            self._total_length += len(terms)
            self._df.update(counts.keys())

    def remove(self, record_id: str) -> bool:
        item = self._documents.pop(record_id, None)
        if item is None:
            return False
        _, terms, counts = item
        self._total_length -= len(terms)
        self._df.subtract(counts.keys())
        self._df += Counter()
        return True

    def clear(self) -> None:
        self._documents.clear()
        self._df.clear()
        self._total_length = 0

    def search(self, query: str, *, top_k: int = 10) -> tuple[LexicalSearchResult, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be from 1 to 100")
        query_terms = set(tokenize(query))
        count = len(self._documents)
        if not query_terms or not count:
            return ()
        average_length = self._total_length / count or 1.0
        ranked = []
        for record, terms, frequencies in self._documents.values():
            length = len(terms)
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / average_length
                )
                score += idf * frequency * (self.k1 + 1) / denominator
            if score > 0:
                ranked.append(LexicalSearchResult(record, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return tuple(ranked[:top_k])


class HybridRetriever:
    """Weighted fusion of cosine similarity and BM25 relevance.

    Each channel is normalized within its candidate set before weighting. Scores
    are ranking values, not probabilities; missing candidates receive no score.
    """

    def __init__(
        self,
        semantic_search: Callable[..., Sequence[SemanticSearchResult]],
        lexical_index: BM25Index,
        *,
        semantic_weight: float = 0.65,
        lexical_weight: float = 0.35,
    ) -> None:
        weights = (semantic_weight, lexical_weight)
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 for value in weights
        ):
            raise ValueError("retrieval weights must be finite non-negative numbers")
        if sum(weights) <= 0:
            raise ValueError("at least one retrieval weight must be positive")
        self.semantic_search = semantic_search
        self.lexical_index = lexical_index
        total = float(sum(weights))
        self.semantic_weight = float(semantic_weight) / total
        self.lexical_weight = float(lexical_weight) / total

    def search(self, query: str, *, top_k: int = 5) -> tuple[SemanticSearchResult, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be from 1 to 100")
        candidate_k = min(100, top_k * 4)
        semantic = self.semantic_search(query, top_k=candidate_k)
        lexical = self.lexical_index.search(query, top_k=candidate_k)

        semantic_scores = {
            result.record.record_id: max(0.0, min(1.0, (float(result.score) + 1.0) / 2.0))
            for result in semantic
        }
        max_lexical = max((result.score for result in lexical), default=0.0)
        lexical_scores = {
            result.record.record_id: (result.score / max_lexical if max_lexical else 0.0)
            for result in lexical
        }
        records = {}
        for result in semantic:
            records[result.record.record_id] = result.record
        for result in lexical:
            records[result.record.record_id] = result.record

        ranked = []
        for record_id, record in records.items():
            score = (
                self.semantic_weight * semantic_scores.get(record_id, 0.0)
                + self.lexical_weight * lexical_scores.get(record_id, 0.0)
            )
            ranked.append(SemanticSearchResult(record, score))
        ranked.sort(key=lambda item: (-item.score, item.record.record_id))
        return tuple(ranked[:top_k])
