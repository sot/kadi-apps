"""Find Attitude tests.

Test ``test_pasted_catalog`` is deterministic and needs no telemetry.

Tests that require telemetry are marked ``telemetry`` and run only with the ``--run-telemetry`` flag
they fetch ACA star data from MAUDE via the server at fixed historical dates, so the
solutions are reproducible.

The form-driving sequences live in ``helpers.py`` as ``run_*`` scenario
generators (shared with ``test_diff.py``); each ``next()`` advances to the next
rendered stage and this module asserts the expected values.

Expected values come from https://github.com/sot/web-kadi/wiki/Functional-Tests
"""

import pytest
from helpers import (
    assert_close,
    assert_quat_close,
    parse_solutions,
    quats_match,
    run_get_telem_current,
    run_multiple_solutions,
    run_pasted_catalog,
    run_safe_mode_constraints,
)
from playwright.sync_api import expect

pytestmark = pytest.mark.find_attitude


def _body(page):
    return page.inner_text("body")


def _assert_no_error(page):
    assert "ERROR generated" not in _body(page), "Find Attitude returned an error block"


def test_pasted_catalog(page):
    """Paste the 8-star catalog and solve with no constraints."""
    for _stage in run_pasted_catalog(page):
        pass

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
    for _stage in run_get_telem_current(page):
        pass
    _assert_no_error(page)
    # The onboard attitude estimate and pitch are populated regardless of whether
    # any stars are currently tracked.
    assert page.input_value("#att").strip(), "estimated attitude not populated"
    assert page.input_value("#pitch").strip(), "pitch not populated"


@pytest.mark.telemetry
def test_safe_mode_constraints(page):
    """Safe-mode case: no solution without constraints, then 1 solution with them."""
    stages = run_safe_mode_constraints(page)

    assert next(stages) == "get_telem"
    _assert_no_error(page)

    # Without constraints there should be no solution.
    assert next(stages) == "solve_no_constraints"
    assert "No matching solutions" in _body(page)
    assert parse_solutions(page) == []

    # With a sun-pitch constraint and no attitude estimate: 1 solution, 3 stars.
    assert next(stages) == "solve_pitch_constraint"
    sols = parse_solutions(page)
    assert len(sols) == 1, f"expected 1 solution, got {len(sols)}"
    assert sols[0]["n_matched"] == 3
    assert_quat_close(
        sols[0]["quat"],
        [0.069077874629, -0.618548169182, -0.485812977408, 0.613687347613],
        atol=1e-3,
    )

    # Loosening distance tolerance to 4 should match a 4th star (403964656).
    assert next(stages) == "solve_distance_tolerance_4"
    sols = parse_solutions(page)
    assert len(sols) == 1, f"expected 1 solution, got {len(sols)}"
    assert sols[0]["n_matched"] == 4
    assert 403964656 in sols[0]["agasc_ids"]


@pytest.mark.telemetry
def test_multiple_solutions(page):
    """Confirm the app can return multiple solutions."""
    stages = run_multiple_solutions(page)

    assert next(stages) == "get_telem"
    _assert_no_error(page)

    assert next(stages) == "solve_constraints"
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
