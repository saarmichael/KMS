"""The reranker used while reranking is off: search results get no relevance and keep the order
fusion gave them."""

from kms.ai.errors import RetryPolicy
from kms.ai.interfaces import Reranker


class NoOpReranker(Reranker):
    """Gives no relevance."""

    def rerank(self, query: str, documents: list[str], policy: RetryPolicy) -> None:
        """Give no relevance.

        Args:
            query: Not read.
            documents: Not read.
            policy: Not read; nothing is called.

        Returns:
            None. Never raises.
        """
        return None
