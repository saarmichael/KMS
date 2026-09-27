from dataclasses import replace
from uuid import UUID

import pytest

from kms.search import MatchKind, UnitHit
from kms.search.fuse import fuse_units, group_by_asset

PHOTO = UUID(int=1)
NOTES = UUID(int=2)
DIAGRAM = UUID(int=3)


def ranked(*units: tuple[int, UUID], all_words: bool = False) -> list[UnitHit]:
    """Hits in the order given, ranked from 1, as a search path returns them."""
    hits = []
    for rank, (unit_id, asset_id) in enumerate(units, start=1):
        hits.append(
            UnitHit(
                unit_id=unit_id,
                asset_id=asset_id,
                rank=rank,
                all_words=all_words,
                unit_kind="content",
                asset_type="text",
            )
        )
    return hits


def grouped(units):
    """Assets from units that were not filtered, so the top unit sets the scale."""
    return group_by_asset(units, units[0].score)


def test_unit_score_is_the_sum_of_reciprocal_ranks():
    keyword_hits = ranked((10, PHOTO))
    vector_hits = ranked((11, NOTES), (10, PHOTO))

    units = fuse_units(keyword_hits, vector_hits)

    assert units[0].unit_id == 10
    assert units[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert units[1].unit_id == 11
    assert units[1].score == pytest.approx(1 / 61)


def test_unit_on_both_paths_outranks_units_on_one_path():
    keyword_hits = ranked((1, PHOTO), (2, PHOTO), (30, NOTES))
    vector_hits = ranked((3, DIAGRAM), (4, DIAGRAM), (30, NOTES))

    units = fuse_units(keyword_hits, vector_hits)

    assert units[0].unit_id == 30


def test_one_path_alone_keeps_its_order():
    keyword_hits = ranked((7, NOTES), (3, PHOTO), (5, DIAGRAM))

    units = fuse_units(keyword_hits, [])

    assert [unit.unit_id for unit in units] == [7, 3, 5]


def test_equal_scores_are_ordered_by_unit_id():
    keyword_hits = ranked((9, PHOTO))
    vector_hits = ranked((4, NOTES))

    units = fuse_units(keyword_hits, vector_hits)

    assert [unit.unit_id for unit in units] == [4, 9]
    swapped = fuse_units(vector_hits, keyword_hits)
    assert [unit.unit_id for unit in swapped] == [4, 9]


def test_best_unit_wins_per_asset():
    keyword_hits = ranked((20, NOTES), (21, NOTES))
    vector_hits = ranked((21, NOTES), (22, PHOTO))

    matches = grouped(fuse_units(keyword_hits, vector_hits))

    assert [(match.asset_id, match.unit_id) for match in matches] == [(NOTES, 21), (PHOTO, 22)]


def test_asset_with_one_strong_unit_beats_asset_with_many_weak_units():
    keyword_hits = ranked((1, PHOTO), (2, NOTES), (3, NOTES), (4, NOTES), (5, NOTES))

    matches = grouped(fuse_units(keyword_hits, []))

    assert [match.asset_id for match in matches] == [PHOTO, NOTES]


def test_top_asset_scores_one_and_the_rest_less():
    keyword_hits = ranked((1, PHOTO), (2, NOTES), (3, DIAGRAM))
    vector_hits = ranked((1, PHOTO), (3, DIAGRAM))

    matches = grouped(fuse_units(keyword_hits, vector_hits))

    assert matches[0].score == 1.0
    for match in matches[1:]:
        assert 0 < match.score < 1.0
    assert matches[1].score >= matches[2].score


def test_no_hits_give_no_assets():
    assert fuse_units([], []) == []
    assert group_by_asset([], 1.0) == []


def test_unit_match_follows_its_hits():
    keyword_hits = ranked((1, PHOTO), (2, NOTES), all_words=True)
    keyword_hits[1] = replace(keyword_hits[1], all_words=False)
    vector_hits = ranked((1, PHOTO), (3, DIAGRAM))

    matches = {unit.unit_id: unit.match for unit in fuse_units(keyword_hits, vector_hits)}

    assert matches == {1: MatchKind.EXACT, 2: MatchKind.PARTIAL, 3: MatchKind.SEMANTIC}


def test_asset_takes_its_strongest_match_and_its_snippet_unit():
    # Unit 5 scores best by being on both paths but holds only some words; unit 6 holds all.
    keyword_hits = ranked((6, NOTES), (5, NOTES), all_words=True)
    keyword_hits[1] = replace(keyword_hits[1], all_words=False)
    vector_hits = ranked((5, NOTES))

    units = fuse_units(keyword_hits, vector_hits)
    match = grouped(units)[0]

    assert units[0].unit_id == 5
    assert match.match == MatchKind.EXACT
    assert match.unit_id == 6
    assert match.score == 1.0


def test_scores_are_measured_against_the_given_top_score():
    units = fuse_units(ranked((1, PHOTO), (2, NOTES)), [])

    matches = group_by_asset(units[1:], units[0].score)

    assert matches[0].asset_id == NOTES
    assert matches[0].score == pytest.approx(units[1].score / units[0].score)
