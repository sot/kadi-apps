"""Groups 2 & 3: the Find Attitude tool.

Group 2 (``test_pasted_catalog``) is deterministic and needs no telemetry.
Group 3 tests are marked ``telemetry`` (gated by ``--run-telemetry``): they fetch
ACA star data from MAUDE via the server at fixed historical dates, so the
solutions are reproducible.

Expected values come from https://github.com/sot/web-kadi/wiki/Functional-Tests
"""

import pytest
from playwright.sync_api import expect

from helpers import (
    STAR_CATALOG,
    assert_close,
    assert_quat_close,
    filter_star_rows,
    parse_solutions,
    quats_match,
)

pytestmark = pytest.mark.find_attitude

# Solving (and the server-side MAUDE fetch) can take a while.
SOLVE_TIMEOUT = 120_000

# Buttons (all share name="action").
GET_TELEM = "button[name=action][value=gettelem]"
SOLVE = "button[name=action][value=calc_solution]"
SOLVE_CONSTRAINTS = "button[name=action][value=calc_solution_constraints]"

# The star-data textarea has a name but no id (unlike the other inputs).
STARS = "textarea[name=stars_text]"


def _submit(page, selector):
    """Click a submit button and wait for the resulting page to render."""
    with page.expect_navigation(wait_until="load", timeout=SOLVE_TIMEOUT):
        page.click(selector)


def _body(page):
    return page.inner_text("body")


def _assert_no_error(page):
    assert "ERROR generated" not in _body(page), "Find Attitude returned an error block"


def test_pasted_catalog(page):
    """Paste the 8-star catalog and solve with no constraints."""
    page.goto("/find_attitude/")
    page.fill(STARS, STAR_CATALOG)
    _submit(page, SOLVE)

    expect(page.get_by_text("Attitude solution generated")).to_be_visible()
    sols = parse_solutions(page)
    assert len(sols) == 1, f"expected 1 solution, got {len(sols)}"
    s = sols[0]

    assert_close(s["ra"], 111.4057, 1e-3, "RA")
    assert_close(s["dec"], 48.9703, 1e-3, "Dec")
    assert_close(s["roll"], 171.0122, 1e-3, "Roll")
    assert_quat_close(
        s["quat"],
        [-0.538061326256, -0.731221726432, -0.291730641395, 0.301161134365],
    )

    assert s["agasc_ids"] == {
        445251736,
        445783648,
        445785880,
        445789056,
        445253208,
        445256328,
        445787240,
    }
    assert s["n_matched"] == 7  # slot 6 is unmatched


@pytest.mark.telemetry
def test_get_telem_current(page):
    """Fetch current ACA telemetry from MAUDE (the 'Get Telem' sanity step)."""
    page.goto("/find_attitude/")
    _submit(page, GET_TELEM)
    _assert_no_error(page)
    # The onboard attitude estimate and pitch are populated regardless of whether
    # any stars are currently tracked.
    assert page.input_value("#att").strip(), "estimated attitude not populated"
    assert page.input_value("#pitch").strip(), "pitch not populated"


@pytest.mark.telemetry
def test_safe_mode_constraints(page):
    """Safe-mode case: no solution without constraints, then 1 solution with them."""
    page.goto("/find_attitude/")
    page.fill("#date_solution", "2023:046:00:34:15.230")
    _submit(page, GET_TELEM)
    _assert_no_error(page)

    stars = filter_star_rows(page.input_value(STARS), {1, 5, 6, 7})
    page.fill(STARS, stars)

    # Without constraints there should be no solution.
    _submit(page, SOLVE)
    assert "No matching solutions" in _body(page)
    assert parse_solutions(page) == []

    # With a sun-pitch constraint and no attitude estimate: 1 solution, 3 stars.
    page.fill("#att", "")
    page.fill("#pitch", "90")
    _submit(page, SOLVE_CONSTRAINTS)
    sols = parse_solutions(page)
    assert len(sols) == 1, f"expected 1 solution, got {len(sols)}"
    assert sols[0]["n_matched"] == 3
    assert_quat_close(
        sols[0]["quat"],
        [0.069077874629, -0.618548169182, -0.485812977408, 0.613687347613],
        atol=1e-3,
    )

    # Loosening distance tolerance to 4 should match a 4th star (403964656).
    page.fill("#distance_tolerance", "4")
    _submit(page, SOLVE_CONSTRAINTS)
    sols = parse_solutions(page)
    assert len(sols) == 1, f"expected 1 solution, got {len(sols)}"
    assert sols[0]["n_matched"] == 4
    assert 403964656 in sols[0]["agasc_ids"]


@pytest.mark.telemetry
def test_multiple_solutions(page):
    """Confirm the app can return multiple solutions."""
    page.goto("/find_attitude/")
    page.fill("#date_solution", "2025:041:13:48:45.286")
    _submit(page, GET_TELEM)
    _assert_no_error(page)

    page.fill(STARS, filter_star_rows(page.input_value(STARS), {3, 4}))
    page.fill("#pitch", "")  # remove Sun Pitch
    page.fill("#att_err", "1.0")
    page.fill("#off_nom_roll_max", "20")
    page.fill("#min_stars", "2")
    _submit(page, SOLVE_CONSTRAINTS)

    sols = parse_solutions(page)
    assert len(sols) == 3, f"expected 3 solutions, got {len(sols)}"
    actual = [s["quat"] for s in sols]
    expected = [
        [0.710534179474, -0.417835190022, -0.565671984887, 0.023877589744],
        [0.680861428995, -0.321535092090, -0.641498079658, 0.146707576000],
        [0.672405430628, -0.330717399808, -0.643388873783, 0.156677041771],
    ]
    for exp in expected:
        assert any(quats_match(a, exp, atol=1e-3) for a in actual), (
            f"expected solution {exp} not found in {actual}"
        )
