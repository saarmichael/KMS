"""The reranker used while reranking is off: search results get no relevance and keep the order
fusion gave them."""

from kms.ai.errors import RetryPolicy
from kms.ai.interfaces import Reranker
from kms.config import Settings


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


def build_noop_reranker(settings: Settings) -> NoOpReranker:
    """Build the reranker that gives no relevance.

    Args:
        settings: The app settings; nothing is read.

    Returns:
        A NoOpReranker. Never raises.
    """
    return NoOpReranker()
