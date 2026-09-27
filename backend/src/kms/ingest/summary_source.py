"""Which part of a text file the vision model reads to describe it.

The description only needs the topic of a file, so a very long file does not have to be read
whole. The chunks are built from the full text separately, so every passage stays searchable
whatever the description was made from.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# A rough estimate, close enough for English prose; no tokenizer is needed to stay well inside
# the model's context.
CHARS_PER_TOKEN = 4


class SummarySource(ABC):
    @abstractmethod
    def text_for_description(self, text: str) -> str:
        """Return the text the vision model is given for this file.

        Args:
            text: The full text of the file.

        Returns:
            The text to describe.
        """


class WholeFile(SummarySource):
    """The file fits the budget and is read whole."""

    def text_for_description(self, text: str) -> str:
        """Return the text unchanged.

        Args:
            text: The full text of the file.

        Returns:
            The same text.
        """
        return text


class Head(SummarySource):
    """The file is over the budget and only its beginning is read."""

    def __init__(self, token_budget: int):
        self.token_budget = token_budget

    def text_for_description(self, text: str) -> str:
        """Return the beginning of the text, as much as the budget allows.

        Args:
            text: The full text of the file.

        Returns:
            The first `token_budget * CHARS_PER_TOKEN` characters.
        """
        return text[: self.token_budget * CHARS_PER_TOKEN]


class MapReduce(SummarySource):
    """Summarise each part of a long file, then describe the summaries together.

    Not built: long files are described from their head instead.
    """

    def text_for_description(self, text: str) -> str:
        """Not built.

        Args:
            text: The full text of the file.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "Map-reduce summaries are not built; long files are described from their head"
        )


def choose_summary_source(text: str, token_budget: int) -> SummarySource:
    """Pick how a text file is read for its description.

    Args:
        text: The full text of the file.
        token_budget: How many tokens of the file the vision model may read.

    Returns:
        WholeFile when the text fits the budget, Head otherwise.
    """
    if len(text) <= token_budget * CHARS_PER_TOKEN:
        return WholeFile()
    # Only the beginning of the file shapes its description; its chunks still cover all of it.
    logger.info(
        "summary_head_only chars=%d budget_chars=%d", len(text), token_budget * CHARS_PER_TOKEN
    )
    return Head(token_budget)
