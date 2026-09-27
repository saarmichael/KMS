"""Hybrid search: a keyword path and a vector path, each returning ranked unit hits."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class MatchKind(StrEnum):
    """How a unit, or an asset, matched the query.

    EXACT: the keyword path found every query word in it. PARTIAL: the keyword path found some
    of them. SEMANTIC: only the vector path found it, by meaning.
    """

    EXACT = "exact"
    PARTIAL = "partial"
    SEMANTIC = "semantic"


# The strongest kind first; a lower tier is a stronger match.
MATCH_TIER = {MatchKind.EXACT: 0, MatchKind.PARTIAL: 1, MatchKind.SEMANTIC: 2}


@dataclass(frozen=True)
class UnitHit:
    """One search unit found by one path.

    Attributes:
        unit_id: The search unit's id.
        asset_id: The asset the unit belongs to.
        rank: The unit's place in its path's list, 1 for the best, with no gaps.
        all_words: True when the keyword path found every query word in the unit; always False
            on the vector path.
        unit_kind: Which part of the asset the unit is: "metadata", "content", "image",
            "visible_text" or "filename".
        asset_type: The asset's type, "image" or "text".
    """

    unit_id: int
    asset_id: UUID
    rank: int
    all_words: bool
    unit_kind: str
    asset_type: str
