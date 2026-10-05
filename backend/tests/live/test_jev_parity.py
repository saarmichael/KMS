"""Jev, the API and the UI agree, checked against the running app: `make dev` first, then
`make test-parity`.

For each query, the search API is read page by page with `reranker=jev`; every result must carry
a relevance, in falling order. Jev itself is then asked about each result, directly through the
TypeSafe SDK and not through the app, and must give the relevance the API gave. Last, a browser
drives the UI the way a user would (Filters, Jev, the query, Show more until the end) and must
show the same results in the same order with the same relevance; the side-by-side view must show
Voyage's list and Jev's list as the API gives them.

The app is the one at PARITY_API_URL and PARITY_UI_URL (the API and the Vite server of
`make dev` by default), searching PARITY_COLLECTION ("demo"). The browser is the installed
Google Chrome, run headless. Skipped when JEV_API_KEY is not set, or the app is not running
with Jev on.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from playwright.sync_api import Page, expect, sync_playwright
from typesafe_sdk import TypeSafeClient

from kms.ai.interfaces import RerankDocument
from kms.ai.jev import QUESTION, QUESTION_NAME, jev_state
from kms.config import get_settings

API_URL = os.environ.get("PARITY_API_URL", "http://localhost:8000")
UI_URL = os.environ.get("PARITY_UI_URL", "http://localhost:5173")
COLLECTION = os.environ.get("PARITY_COLLECTION", "demo")
# Jev does not give exactly the same answer twice: the same request, sent twice, came back up to
# 0.05 apart for results in the middle of the scale (0.25, then 0.28). The API's relevance is
# remembered from one such answer, so it is held to the same spread.
JEV_TOLERANCE = 0.06
QUERIES = ["food", "receipt", "waterfall", "documents to keep after a trip"]


def app_has_jev() -> bool:
    """True when the app answers at API_URL and lists Jev among its rerankers."""
    try:
        config = httpx.get(f"{API_URL}/api/config", timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return False
    return "jev" in config.get("rerankers", [])


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not get_settings().jev_api_key, reason="needs JEV_API_KEY"),
    pytest.mark.skipif(not app_has_jev(), reason=f"needs the app at {API_URL} with Jev on"),
]


def api_results(query: str, reranker: str) -> list[dict]:
    """Every result of a search, read from the API page by page, in order."""
    results = []
    page = 1
    while True:
        params = {"collection": COLLECTION, "q": query, "page": page, "reranker": reranker}
        response = httpx.get(f"{API_URL}/api/search", params=params, timeout=60)
        response.raise_for_status()
        body = response.json()
        assert body["reranker"] == reranker
        results.extend(body["results"])
        if not body["has_more"]:
            return results
        page += 1


def title_of(result: dict) -> str:
    """The title a card shows: the asset's title, or its file name before it is described."""
    metadata = result["asset"]["metadata"]
    if metadata is None:
        return result["asset"]["filename"]
    return metadata["title"]


def document_of(result: dict) -> RerankDocument:
    """The result as the app's Jev reranker reads it, built from the API's answer alone."""
    metadata = result["asset"]["metadata"]
    return RerankDocument(
        text=result["snippet"]["text"],
        kind=result["snippet"]["kind"],
        title=metadata["title"] if metadata else None,
        filename=result["asset"]["filename"],
        tags=tuple(metadata["tags"]) if metadata else (),
    )


def ask_jev_directly(query: str, results: list[dict]) -> list[float]:
    """Jev's relevance for each result, asked through the SDK, outside the app and its cache."""
    client = TypeSafeClient(api_key=get_settings().jev_api_key)

    def ask(result: dict) -> float:
        answer = client.system_one(
            state=jev_state(query, document_of(result)),
            questions={QUESTION_NAME: QUESTION},
            model=get_settings().jev_model,
        )
        return answer.nouls[QUESTION_NAME].noul

    with ThreadPoolExecutor(max_workers=20) as executor:
        return list(executor.map(ask, results))


def expected_cards(results: list[dict]) -> list[tuple[str, str | None]]:
    """What the UI must show for each result: its title and its relevance as the card writes it."""
    cards = []
    for result in results:
        relevance = None
        if result["relevance"] is not None:
            relevance = f"Relevance {result['relevance']:.2f}"
        cards.append((title_of(result), relevance))
    return cards


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chrome = playwright.chromium.launch(channel="chrome", headless=True)
        yield chrome
        chrome.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1400, "height": 1000})
    page = context.new_page()
    yield page
    context.close()


def search_in_ui(page: Page, query: str, reranker_label: str) -> None:
    """Open the UI, choose the reranker in the filters, and search."""
    page.goto(UI_URL)
    page.get_by_role("button", name="Filters").click()
    page.get_by_role("button", name=reranker_label, exact=True).click()
    page.get_by_role("textbox", name="Search").fill(query)
    page.get_by_role("textbox", name="Search").press("Enter")


def read_cards(page: Page, container: str) -> list[tuple[str, str | None]]:
    """Click Show more until every page is loaded, then read each card's title and relevance."""
    # Only the visible cards: the collection's file list stays on the page, hidden, during a search.
    cards = page.locator(f"{container} li:has(h3):visible")
    expect(cards.first).to_be_visible(timeout=30_000)
    show_more = page.locator(container).get_by_role("button", name="Show more")
    while show_more.count() > 0:
        shown = cards.count()
        expect(show_more).to_be_enabled(timeout=30_000)
        show_more.click()
        expect(cards).not_to_have_count(shown, timeout=30_000)

    read = []
    for card in cards.all():
        # A card in a column starts its title with its place, "1. ".
        title = re.sub(r"^\d+\.\s*", "", card.locator("h3").inner_text()).strip()
        relevance_label = card.get_by_text(re.compile(r"^Relevance \d\.\d\d$"))
        relevance = relevance_label.inner_text() if relevance_label.count() else None
        read.append((title, relevance))
    return read


@pytest.mark.parametrize("query", QUERIES)
def test_api_gives_jev_relevance_to_every_result_in_falling_order(query):
    results = api_results(query, "jev")

    relevances = [result["relevance"] for result in results]
    assert results, f"no results for {query!r}"
    assert None not in relevances
    assert relevances == sorted(relevances, reverse=True)


@pytest.mark.parametrize("query", QUERIES)
def test_api_relevance_is_what_jev_answers(query):
    results = api_results(query, "jev")

    direct = ask_jev_directly(query, results)

    for result, jev_relevance in zip(results, direct, strict=True):
        assert result["relevance"] == pytest.approx(jev_relevance, abs=JEV_TOLERANCE), title_of(
            result
        )


@pytest.mark.parametrize("query", QUERIES)
def test_ui_shows_the_api_jev_ranking(page, query):
    results = api_results(query, "jev")

    search_in_ui(page, query, "Jev")
    shown = read_cards(page, "main")

    assert shown == expected_cards(results)


@pytest.mark.parametrize("query", QUERIES[:2])
def test_ui_side_by_side_shows_both_api_rankings(page, query):
    voyage_results = api_results(query, "voyage")
    jev_results = api_results(query, "jev")

    search_in_ui(page, query, "Both")
    voyage_shown = read_cards(page, 'section[aria-label="Ranked by voyage"]')
    jev_shown = read_cards(page, 'section[aria-label="Ranked by jev"]')

    assert voyage_shown == expected_cards(voyage_results)
    assert jev_shown == expected_cards(jev_results)
