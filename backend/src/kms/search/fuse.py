"""Merge the keyword and vector rankings into one ranked list of assets.

Reciprocal rank fusion scores a unit by its places in the two lists, not by the paths' own scores,
which are on scales that cannot be compared (a `ts_rank` and a cosine distance).
"""

from dataclasses import dataclass
from uuid import UUID

from kms.search import UnitHit

# The paper's value. A k this large keeps the top ranks close together, so a unit found by both
# paths beats a unit found first by only one.
RRF_K = 60


@dataclass(frozen=True)
class FusedUnit:
    """One unit with its fused score.

    Attributes:
        unit_id: The search unit's id.
        asset_id: The asset the unit belongs to.
        score: The unit's RRF score, summed over the paths that found it.
    """

    unit_id: int
    asset_id: UUID
    score: float


@dataclass(frozen=True)
class AssetMatch:
    """One asset found by the search.

    Attributes:
        asset_id: The asset's id.
        unit_id: The id of the asset's best unit, which the snippet is taken from.
        score: The best unit's score over the top asset's, so the top asset scores 1.0.
    """

    asset_id: UUID
    unit_id: int
    score: float


def fuse_units(keyword_hits: list[UnitHit], vector_hits: list[UnitHit]) -> list[FusedUnit]:
    """Score every unit found by either path with reciprocal rank fusion. Never raises.

    Args:
        keyword_hits: The keyword path's hits, each with its rank in that path.
        vector_hits: The vector path's hits, each with its rank in that path.

    Returns:
        Each unit once, best score first, equal scores in unit id order. Empty when both paths
        found nothing.
    """
    scores: dict[int, float] = {}
    asset_ids: dict[int, UUID] = {}
    for hit in keyword_hits + vector_hits:
        # A path that missed the unit adds nothing, so a unit on both paths collects two terms.
        scores[hit.unit_id] = scores.get(hit.unit_id, 0.0) + 1 / (RRF_K + hit.rank)
        asset_ids[hit.unit_id] = hit.asset_id

    units = []
    for unit_id, score in scores.items():
        units.append(FusedUnit(unit_id=unit_id, asset_id=asset_ids[unit_id], score=score))
    units.sort(key=lambda unit: (-unit.score, unit.unit_id))
    return units


def group_by_asset(units: list[FusedUnit]) -> list[AssetMatch]:
    """Keep each asset's best unit and normalise the scores against the top asset. Never raises.

    Args:
        units: Fused units in the order `fuse_units` returns them, best first.

    Returns:
        One match per asset, in the order of their best units. Empty when `units` is empty.
    """
    if not units:
        return []

    # The list is already best first, so an asset's first unit is its best one and the assets
    # come out in order without a second sort. An asset scores by its best unit, not the sum of
    # its units, so a long file with many weak chunks does not outrank one strong match.
    top_score = units[0].score
    matches = []
    seen_asset_ids = set()
    for unit in units:
        if unit.asset_id in seen_asset_ids:
            continue
        seen_asset_ids.add(unit.asset_id)
        matches.append(
            AssetMatch(asset_id=unit.asset_id, unit_id=unit.unit_id, score=unit.score / top_score)
        )
    return matches
