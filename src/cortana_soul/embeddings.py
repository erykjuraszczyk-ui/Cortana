"""Optional local embedding runtime backed by Sentence Transformers.

The package is imported only when the adapter is instantiated, keeping the
Cortana core lightweight and usable without ML dependencies.
"""
from __future__ import annotations

from typing import Sequence

from .semantic import EmbeddingProvider, _validate_vector


class LocalSentenceTransformer:
    """Generate embeddings locally; CPU is the portable default."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        *,
        device: str = "cpu",
        local_files_only: bool = False,
    ) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        if not isinstance(device, str) or not device.strip():
            raise ValueError("device must be a non-empty string")
        if not isinstance(local_files_only, bool):
            raise ValueError("local_files_only must be a boolean")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "LocalSentenceTransformer requires the optional 'sentence-transformers' package"
            ) from exc
        try:
            self._model = SentenceTransformer(
                model_name.strip(), device=device, local_files_only=local_files_only
            )
            dimension = self._model.get_sentence_embedding_dimension()
        except Exception as exc:
            raise RuntimeError(f"could not load embedding model: {model_name}") from exc
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
            raise RuntimeError("embedding model did not expose a valid output dimension")
        self._dimension = dimension
        self.model_name = model_name.strip()
        self.device = device

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> Sequence[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        try:
            vector = self._model.encode(
                text, convert_to_numpy=True, normalize_embeddings=False,
                show_progress_bar=False,
            ).tolist()
        except Exception as exc:
            raise RuntimeError("local embedding inference failed") from exc
        return _validate_vector(vector, self.dimension)
