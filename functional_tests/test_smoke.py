"""Group 1: page-load / link checks from the wiki functional-test checklist.

For each page we assert the HTTP response is OK, the expected heading/content is
visible, and the error templates (404/500) are not present. List pages must show
a populated results table. A separate check verifies the version footer.
"""

import pytest
from playwright.sync_api import expect

# HTML pages served by the kadi_apps Flask app. Each entry:
#   (id, path, expected-heading-substring)
PAGES = [
    ("dark_cal_list", "/kadi/events/dark_cal/list/", "list"),
    ("dwell_list", "/kadi/events/dwell/list", "list"),
    ("orbit_list", "/kadi/events/orbit/list", "list"),
    (
        "dark_cal_event",
        "/kadi/events/dark_cal/2021:234:03:44:27.313?filter=&sort=-start&index=1",
        "detail",
    ),
    ("orbit_event", "/kadi/events/orbit/3059?filter=&sort=-start&index=0", "detail"),
    ("mica", "/mica/?obsid_or_date=24641", "Mica portal"),
    ("pcad_acq", "/pcad_acq/?obsid=24641", "PCAD Acquisition Table"),
    ("star_hist", "/star_hist/?agasc_id=553404184", "Star History"),
    ("find_attitude", "/find_attitude/", "Find Chandra attitude"),
]

LIST_PATHS = {p for _, p, kind in PAGES if kind == "list"}

pytestmark = pytest.mark.smoke


def _assert_no_error_page(page):
    body = page.inner_text("body")
    assert "Page not Found (404)" not in body, "got the 404 page"
    assert "Internal Error (500)" not in body, "got the 500 page"


@pytest.mark.parametrize(
    "path,expected", [(p, e) for _, p, e in PAGES], ids=[i for i, _, _ in PAGES]
)
def test_page_loads(page, path, expected):
    response = page.goto(path)
    assert response is not None and response.ok, (
        f"{path} returned HTTP {response.status if response else 'no response'}"
    )
    _assert_no_error_page(page)
    # Heading text appears in an h1/h2 on the page.
    expect(page.locator("h1, h2").filter(has_text=expected).first).to_be_visible()


@pytest.mark.parametrize("path", sorted(LIST_PATHS))
def test_list_page_has_rows(page, path):
    page.goto(path)
    rows = page.locator("table.srclist tbody tr")
    expect(rows.first).to_be_visible()
    assert rows.count() > 0, f"{path} list table has no rows"


def test_star_hist_found(page):
    """A valid AGASC id should not render the 'No AGASC entry' alert."""
    page.goto("/star_hist/?agasc_id=553404184")
    assert "No AGASC entry" not in page.inner_text("body")


def test_version_footer(page):
    """The wiki step: ska3-flight / kadi / kadi-apps versions shown at the bottom."""
    page.goto("/find_attitude/")
    footer = page.locator("footer")
    expect(footer).to_be_visible()
    text = footer.inner_text()
    for label in ("ska3-flight", "Kadi", "Kadi-apps"):
        assert label in text, f"footer missing '{label}': {text!r}"
    # Each label should be followed by a non-empty version token.
    for label in ("ska3-flight", "Kadi ", "Kadi-apps"):
        idx = text.find(label)
        tail = text[idx + len(label):].strip().split("\n")[0].strip()
        assert tail, f"footer '{label}' has no version value: {text!r}"


@pytest.mark.parametrize("path", ["/version", "/api"])
def test_endpoint_reachable(page, path):
    """/version and /api are served on the deployed host (possibly by a separate
    WSGI app); just confirm they respond OK with non-empty content."""
    response = page.goto(path)
    assert response is not None and response.ok, (
        f"{path} returned HTTP {response.status if response else 'no response'}"
    )
    assert page.inner_text("body").strip() or page.content().strip()
