import pytest

from kms.search.keyword import uses_search_syntax


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("london museum", False),
        ("black hair", False),
        ("oregano", False),
        ('"black hair"', True),
        ("hair -tied", True),
        ("london or paris", True),
        ("London OR Paris", True),
    ],
)
def test_uses_search_syntax(query, expected):
    assert uses_search_syntax(query) is expected
