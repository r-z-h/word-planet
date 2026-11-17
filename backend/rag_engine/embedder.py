"""本地 bge 嵌入器（独立于 app）。离线加载，不联网。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


class Embedder:
    def __init__(self, model_dir: Path | str):
        self.model_dir = str(model_dir)
        self._m = None

    def model(self):
        if self._m is None:
            from sentence_transformers import SentenceTransformer

            self._m = SentenceTransformer(self.model_dir, device="cpu")
        return self._m

    def dim(self) -> int:
        return int(self.model().get_sentence_embedding_dimension())

    def encode(self, texts: list[str], prefix: str = "") -> list[list[float]]:
        vecs = self.model().encode(
            [prefix + t for t in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vecs]
