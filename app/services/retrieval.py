"""
retrieval.py - RAG-lite grounded retrieval engine.
Retrieves the most relevant knowledge base article using cosine similarity over embeddings.
Ensures draft responses are grounded in real help-center policies without hallucinations.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np


class KBRetriever:
    """Retrieves grounded KB articles by cosine similarity over sentence embeddings."""

    def __init__(self, kb_path: Optional[Path] = None, similarity_threshold: float = 0.35):
        if kb_path is None:
            kb_path = Path(__file__).resolve().parent.parent.parent / "data" / "kb_articles.json"
        self.kb_path = kb_path
        self.similarity_threshold = similarity_threshold
        self.articles: List[Dict[str, str]] = []
        self.article_embeddings: Optional[np.ndarray] = None
        self._load_kb()

    def _load_kb(self):
        if self.kb_path.exists():
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.articles = json.load(f)
        else:
            self.articles = []

    def index_articles(self, embedder):
        """Precompute article embeddings for fast in-memory cosine search."""
        if not self.articles:
            return
        texts = [f"{a.get('title', '')}: {a.get('content', '')}" for a in self.articles]
        embeddings = embedder.encode(texts, normalize_embeddings=True)
        self.article_embeddings = np.array(embeddings)

    def retrieve(
        self, query_embedding: np.ndarray
    ) -> Tuple[Optional[Dict[str, str]], float]:
        """
        Finds the top-ranked KB article for the given normalized query embedding.
        Returns (article_dict_or_None, top_similarity_score).
        """
        if self.article_embeddings is None or len(self.articles) == 0:
            return None, 0.0

        # Cosine similarity for normalized embeddings is the dot product
        similarities = np.dot(self.article_embeddings, query_embedding)
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= self.similarity_threshold:
            return self.articles[best_idx], best_score

        return None, best_score


_retriever_instance: Optional[KBRetriever] = None


def get_retriever() -> KBRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = KBRetriever()
    return _retriever_instance
