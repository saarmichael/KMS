"""What the user chooses about the results: which ones to see, and in what order."""

from enum import StrEnum

from kms.search import MATCH_TIER, MatchKind
from kms.search.fuse import AssetMatch, FusedUnit


class SearchOrder(StrEnum):
    """How the results are ordered.

    EXACT_FIRST: exact matches first, the rest by score. TIERED: exact, then partial, then
    semantic matches, each by score. BLENDED: by score alone.
    """

    EXACT_FIRST = "exact_first"
    TIERED = "tiered"
    BLENDED = "blended"


def filter_units(
    units: list[FusedUnit], asset_types: list[str] | None, unit_kinds: list[str] | None
) -> list[FusedUnit]:
    """Keep the units of the chosen asset types and the chosen parts of an asset. Never raises.

    Filtering units rather than assets means the snippet always comes from a chosen part.

    Args:
        units: Fused units, best first.
        asset_types: The asset types to keep; None keeps all.
        unit_kinds: The parts of an asset to keep ("content", "metadata", ...); None keeps all.

    Returns:
        The kept units, in their order.
    """
    kept = []
    for unit in units:
        if asset_types is not None and unit.asset_type not in asset_types:
            continue
        if unit_kinds is not None and unit.unit_kind not in unit_kinds:
            continue
        kept.append(unit)
    return kept


def filter_matches(
    matches: list[AssetMatch], match_kinds: list[MatchKind] | None
) -> list[AssetMatch]:
    """Keep the assets whose strongest match is one of the chosen kinds. Never raises.

    Args:
        matches: Assets, best first.
        match_kinds: The kinds to keep; None keeps all.

    Returns:
        The kept assets, in their order.
    """
    if match_kinds is None:
        return matches
    return [match for match in matches if match.match in match_kinds]


def order_matches(matches: list[AssetMatch], order: SearchOrder) -> list[AssetMatch]:
    """Put the assets in the chosen order. Never raises.

    Python's sort is stable, so assets that share a tier keep their score order.

    Args:
        matches: Assets, best score first.
        order: The order the user chose.

    Returns:
        The same assets in the chosen order.
    """
    if order == SearchOrder.EXACT_FIRST:
        return sorted(matches, key=lambda match: match.match != MatchKind.EXACT)
    if order == SearchOrder.TIERED:
        return sorted(matches, key=lambda match: MATCH_TIER[match.match])
    return matches
