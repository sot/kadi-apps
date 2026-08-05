"""Test-vs-flight diff report (report-only; gated by ``--run-diff``).

Every page/scenario the suite exercises is rendered on *both* deployed servers
and the results are compared: normalized visible text plus full-page
screenshots (version footer masked on both). Differences never fail a test --
right before a promotion they are often the point -- the tests only fail if a
server errors. Read the report at ``functional_tests/diff-results/index.html``.

Run with::

    pytest functional_tests -m diff --run-diff
    pytest functional_tests -m diff --run-diff --run-telemetry   # + telemetry scenarios

``--server`` / ``--base-url`` are ignored here: these tests always compare the
``test`` and ``flight`` servers from ``conftest.SERVERS``.
"""

from pathlib import Path

import pytest
from conftest import SERVERS
from diffing import DiffReport, capture
from helpers import (
    run_get_telem_current,
    run_multiple_solutions,
    run_pasted_catalog,
    run_safe_mode_constraints,
)
from test_smoke import PAGES

pytestmark = pytest.mark.diff

# Same fixed viewport on both servers so screenshots are comparable.
VIEWPORT = {"width": 1280, "height": 900}

DIFF_DIR = Path(__file__).parent / "diff-results"

# Paths to compare beyond the smoke-test pages. /version is not diffed (it
# differs by construction); it is shown in the report header instead.
EXTRA_PAGES = [("api", "/api")]


@pytest.fixture(scope="session")
def diff_report():
    """Collects comparisons across all diff tests; renders the report last."""
    report = DiffReport(DIFF_DIR)
    yield report
    if report.entries:
        path = report.finalize()
        print(f"\ndiff report: {path}")


@pytest.fixture(scope="session")
def servers(browser, diff_report):
    """One Playwright page per deployed server, plus /version in the report."""
    contexts = []
    pages = {}
    for name, url in SERVERS.items():
        context = browser.new_context(base_url=url, viewport=VIEWPORT)
        contexts.append(context)
        pages[name] = context.new_page()
    for name, page in pages.items():
        response = page.goto("/version")
        assert response is not None and response.ok, f"{name}: /version unreachable"
        diff_report.set_versions(name, page.inner_text("body").strip())
    yield pages
    for context in contexts:
        context.close()


def _goto_and_capture(pages, path):
    snaps = {}
    for name, page in pages.items():
        response = page.goto(path)
        assert response is not None and response.ok, (
            f"{name}: {path} returned HTTP "
            f"{response.status if response else 'no response'}"
        )
        snaps[name] = capture(page)
    return snaps


def _diff_scenario(pages, diff_report, scenario, prefix):
    """Run a helpers ``run_*`` scenario on both servers in lockstep, recording
    a diff entry after each stage."""
    for stage_test, stage_flight in zip(scenario(pages["test"]), scenario(pages["flight"])):
        assert stage_test == stage_flight  # generators advance in lockstep
        diff_report.add(
            f"{prefix}:{stage_test}",
            test_snap=capture(pages["test"]),
            flight_snap=capture(pages["flight"]),
        )


@pytest.mark.parametrize(
    "item_id,path",
    [(i, p) for i, p, _ in PAGES] + EXTRA_PAGES,
    ids=[i for i, _, _ in PAGES] + [i for i, _ in EXTRA_PAGES],
)
def test_page_diff(servers, diff_report, item_id, path):
    snaps = _goto_and_capture(servers, path)
    diff_report.add(item_id, test_snap=snaps["test"], flight_snap=snaps["flight"])


def test_find_attitude_diff(servers, diff_report):
    _diff_scenario(servers, diff_report, run_pasted_catalog, "find_attitude_pasted")


@pytest.mark.telemetry
@pytest.mark.parametrize(
    "scenario",
    [run_get_telem_current, run_safe_mode_constraints, run_multiple_solutions],
    ids=lambda s: s.__name__.removeprefix("run_"),
)
def test_telemetry_scenario_diff(servers, diff_report, scenario):
    _diff_scenario(
        servers, diff_report, scenario, scenario.__name__.removeprefix("run_")
    )
