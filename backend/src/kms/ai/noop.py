"""The reranker used while reranking is off: search results keep the order fusion gave them."""

from kms.ai.interfaces import Reranker


class NoOpReranker(Reranker):
    """Returns every order unchanged."""

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        """Keep the order given.

        Args:
            query: Not read.
            documents: The results' texts, in the current order.

        Returns:
            0, 1, 2, … one index per document. Never raises.
        """
        return list(range(len(documents)))
