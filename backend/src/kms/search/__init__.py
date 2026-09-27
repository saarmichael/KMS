"""Hybrid search: a keyword path and a vector path, each returning ranked unit hits."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UnitHit:
    """One search unit found by one path.

    Attributes:
        unit_id: The search unit's id.
        asset_id: The asset the unit belongs to.
        rank: The unit's place in its path's list, 1 for the best, with no gaps.
    """

    unit_id: int
    asset_id: UUID
    rank: int
