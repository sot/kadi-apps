"""Group 4: list filter / sort / pagination / event-navigation consistency.

Follows the wiki "Navigation test" sequence on the dark_cal event list: apply a
filter, sort by an uncorrelated column, page forward, open an event, step one
event forward, then return to the list via the list icon -- checking that filter
and sort are preserved throughout.

The sequence is adaptive (it does not hard-code "page 3" / "5th row") so it
stays valid as the underlying event data grows.

DOM reference: kadi_apps/blueprints/kadi/templates/events/event_list.html and
event_detail.html.
"""

from contextlib import contextmanager

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.navigation

NAV_TIMEOUT = 30_000

NEXT_ARROW = 'a:has(img[src*="right_grey_32.png"])'
LIST_ICON = 'a:has(img[src*="list_32.png"])'


@contextmanager
def _navigates(page, timeout=NAV_TIMEOUT):
    with page.expect_navigation(wait_until="load", timeout=timeout):
        yield


def test_event_navigation(page):
    page.goto("/kadi/events/dark_cal/list/")

    # 1. Apply a filter.
    page.fill("input[name=filter]", "dur<20000")
    with _navigates(page):
        page.press("input[name=filter]", "Enter")
    assert "filter=dur" in page.url, page.url
    rows = page.locator("table.srclist tbody tr")
    expect(rows.first).to_be_visible()

    # 2. Sort by an uncorrelated column (obsid).
    with _navigates(page):
        page.locator('thead a[href*="sort=obsid"]').first.click()
    assert "sort=obsid" in page.url, page.url
    assert "filter=dur" in page.url, "filter lost when sorting"
    expect(page.locator("table.srclist tbody tr").first).to_be_visible()

    # 3. Page forward (if the filtered set spans more than one page).
    next_arrow = page.locator(NEXT_ARROW)
    if next_arrow.count():
        before = page.locator("span.page-current").inner_text()
        with _navigates(page):
            next_arrow.first.click()
        assert page.locator("span.page-current").inner_text() != before, "page did not advance"
        assert "filter=dur" in page.url and "sort=obsid" in page.url, (
            f"filter/sort lost on pagination: {page.url}"
        )

    # 4. Open an event (prefer the 5th row; fall back to the last available).
    links = page.locator("table.srclist tbody tr a")
    n_links = links.count()
    assert n_links > 0, "no event links in the list"
    with _navigates(page):
        links.nth(min(4, n_links - 1)).click()
    expect(page.locator("h2", has_text="detail")).to_be_visible()
    assert "index=" in page.url, page.url
    detail_url = page.url

    # 5. Step one event forward.
    forward = page.locator(NEXT_ARROW)
    if forward.count():
        with _navigates(page):
            forward.first.click()
        assert page.url != detail_url, "did not move to the next event"
        expect(page.locator("h2", has_text="detail")).to_be_visible()

    # 6. Return to the list via the list icon; filter and sort must be preserved.
    with _navigates(page):
        page.locator(LIST_ICON).first.click()
    expect(page.locator("h2", has_text="list")).to_be_visible()
    assert "filter=dur" in page.url, f"filter lost on return: {page.url}"
    assert "sort=obsid" in page.url, f"sort lost on return: {page.url}"
