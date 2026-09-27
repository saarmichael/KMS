"""Merge the keyword and vector rankings into one ranked list of assets.

Reciprocal rank fusion scores a unit by its places in the two lists, not by the paths' own scores,
which are on scales that cannot be compared (a `ts_rank` and a cosine distance).
"""

from dataclasses import dataclass, replace
from uuid import UUID

from kms.search import MATCH_TIER, MatchKind, UnitHit

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
        match: How the unit matched, from which paths found it.
        unit_kind: Which part of the asset the unit is.
        asset_type: The asset's type, "image" or "text".
    """

    unit_id: int
    asset_id: UUID
    score: float
    match: MatchKind
    unit_kind: str
    asset_type: str


@dataclass(frozen=True)
class AssetMatch:
    """One asset found by the search.

    Attributes:
        asset_id: The asset's id.
        unit_id: The id of the asset's best unit of its strongest match, which the snippet is
            taken from.
        score: The asset's best unit score over the top score of the whole query.
        match: The strongest match among the asset's units.
    """

    asset_id: UUID
    unit_id: int
    score: float
    match: MatchKind


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
    hits_by_unit: dict[int, UnitHit] = {}
    for hit in keyword_hits + vector_hits:
        # A path that missed the unit adds nothing, so a unit on both paths collects two terms.
        scores[hit.unit_id] = scores.get(hit.unit_id, 0.0) + 1 / (RRF_K + hit.rank)
        hits_by_unit[hit.unit_id] = hit

    # Only the keyword path knows about words, so its hits decide exact or partial.
    keyword_matches: dict[int, MatchKind] = {}
    for hit in keyword_hits:
        keyword_matches[hit.unit_id] = MatchKind.EXACT if hit.all_words else MatchKind.PARTIAL

    units = []
    for unit_id, score in scores.items():
        hit = hits_by_unit[unit_id]
        units.append(
            FusedUnit(
                unit_id=unit_id,
                asset_id=hit.asset_id,
                score=score,
                match=keyword_matches.get(unit_id, MatchKind.SEMANTIC),
                unit_kind=hit.unit_kind,
                asset_type=hit.asset_type,
            )
        )
    units.sort(key=lambda unit: (-unit.score, unit.unit_id))
    return units


def group_by_asset(units: list[FusedUnit], top_score: float) -> list[AssetMatch]:
    """One match per asset: its best score, its strongest match, and the unit that shows it.
    Never raises.

    Args:
        units: Fused units in the order `fuse_units` returns them, best first, possibly
            filtered since.
        top_score: The best unit score of the whole query, before any filter, so that a filter
            never changes the scores it leaves.

    Returns:
        One match per asset, in the order of their best units. Empty when `units` is empty.
    """
    # The list is already best first, so an asset's first unit is its best one and the assets
    # come out in order without a second sort. An asset scores by its best unit, not the sum of
    # its units, so a long file with many weak chunks does not outrank one strong match.
    matches: dict[UUID, AssetMatch] = {}
    for unit in units:
        found = matches.get(unit.asset_id)
        if found is None:
            matches[unit.asset_id] = AssetMatch(
                asset_id=unit.asset_id,
                unit_id=unit.unit_id,
                score=unit.score / top_score,
                match=unit.match,
            )
        elif MATCH_TIER[unit.match] < MATCH_TIER[found.match]:
            # A stronger match further down: the snippet moves to it, so an exact match shows
            # its words. The score stays the asset's best.
            matches[unit.asset_id] = replace(found, unit_id=unit.unit_id, match=unit.match)
    return list(matches.values())
