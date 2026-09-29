from uuid import UUID

from kms.search import MatchKind
from kms.search.fuse import AssetMatch, FusedUnit
from kms.search.order import SearchOrder, filter_matches, filter_units, order_matches

EXACT = MatchKind.EXACT
PARTIAL = MatchKind.PARTIAL
SEMANTIC = MatchKind.SEMANTIC


def unit(unit_id: int, unit_kind: str, asset_type: str) -> FusedUnit:
    return FusedUnit(
        unit_id=unit_id,
        asset_id=UUID(int=unit_id),
        score=1.0,
        match=SEMANTIC,
        unit_kind=unit_kind,
        asset_type=asset_type,
    )


def matches(*kinds: MatchKind) -> list[AssetMatch]:
    """Assets in score order, asset n holding the n-th kind given."""
    found = []
    for number, kind in enumerate(kinds, start=1):
        found.append(
            AssetMatch(asset_id=UUID(int=number), unit_id=number, score=1 / number, match=kind)
        )
    return found


def unit_ids(units):
    return [unit.unit_id for unit in units]


def asset_numbers(found):
    return [match.asset_id.int for match in found]


def test_filter_units_keeps_chosen_types_and_parts():
    units = [
        unit(1, "content", "text"),
        unit(2, "metadata", "text"),
        unit(3, "metadata", "image"),
        unit(4, "image", "image"),
    ]

    assert unit_ids(filter_units(units, None, None)) == [1, 2, 3, 4]
    assert unit_ids(filter_units(units, ["image"], None)) == [3, 4]
    assert unit_ids(filter_units(units, None, ["metadata"])) == [2, 3]
    assert unit_ids(filter_units(units, ["text"], ["metadata", "image"])) == [2]


def test_filter_matches_keeps_chosen_kinds():
    found = matches(SEMANTIC, EXACT, PARTIAL)

    assert asset_numbers(filter_matches(found, None)) == [1, 2, 3]
    assert asset_numbers(filter_matches(found, [EXACT, PARTIAL])) == [2, 3]


def test_blended_keeps_score_order():
    found = matches(SEMANTIC, EXACT, PARTIAL)

    assert asset_numbers(order_matches(found, SearchOrder.BLENDED)) == [1, 2, 3]


def test_exact_first_moves_exact_up_and_keeps_the_rest_in_order():
    found = matches(SEMANTIC, PARTIAL, EXACT, SEMANTIC, EXACT)

    assert asset_numbers(order_matches(found, SearchOrder.EXACT_FIRST)) == [3, 5, 1, 2, 4]


def test_tiered_orders_exact_then_partial_then_semantic():
    found = matches(SEMANTIC, PARTIAL, EXACT, SEMANTIC, PARTIAL)

    assert asset_numbers(order_matches(found, SearchOrder.TIERED)) == [3, 2, 5, 1, 4]


def test_relevance_order_keeps_score_order():
    found = matches(SEMANTIC, EXACT, PARTIAL)

    assert asset_numbers(order_matches(found, SearchOrder.RELEVANCE)) == [1, 2, 3]
