# kadi-apps functional tests (Playwright)

These end-to-end tests automate the post-deployment checklist from the
[web-kadi wiki](https://github.com/sot/web-kadi/wiki/Functional-Tests). They drive a
**deployed** kadi server with a real browser and check that pages load, the version
footer is present, the Find Attitude tool produces the expected solutions, and that
list filter/sort/pagination/navigation behave consistently.

They are intentionally kept out of the installed package and the unit-test suite
(`kadi_apps/tests`), because they require network access to the deployed servers.

## Setup

```bash
pip install -r functional_tests/requirements.txt
playwright install chromium
```

You must be on a network/VPN that can reach `*.cfa.harvard.edu`.

## Running

Select the target with `--server` (default `test`):

```bash
# Pre-promotion: the quick suite against the test server
pytest functional_tests -m "smoke or find_attitude or navigation" --server test

# Post-promotion: the same against flight
pytest functional_tests -m "smoke or find_attitude or navigation" --server flight

# Everything against test
pytest functional_tests --server test
```

`--base-url https://…` overrides `--server` if you need an ad-hoc host.

### Telemetry tests

The Find Attitude telemetry/constraint cases fetch live MAUDE data **through the
server** (no client credentials needed — the server holds them). They are slower and
depend on an external service, so they are skipped unless you opt in:

```bash
pytest functional_tests -m telemetry --run-telemetry --server test
```

### Test-vs-flight diff report

The `diff` tests replace the manual "open both servers and flip between tabs"
comparison: every page and Find Attitude scenario the suite exercises is rendered
on **both** the test and flight servers and compared (visible text + full-page
screenshots, with the always-different version footer masked). They are
**report-only** — differences do not fail the tests, since right before a
promotion a difference is often the point. A test only fails if a server errors.

```bash
pytest functional_tests -m diff --run-diff

# Include the (slow) telemetry scenarios in the comparison
pytest functional_tests -m diff --run-diff --run-telemetry
```

Then open `functional_tests/diff-results/index.html`: it shows both servers'
versions, flags which pages differ, and links to a per-page detail view with a
side-by-side highlighted text diff, a pixel-diff image, and a blink toggle
between the two screenshots. `--server`/`--base-url` are ignored by these tests;
they always compare the two servers in `conftest.SERVERS`.

### Debugging failures

On failure, a screenshot, Playwright trace, and video are written under
`functional_tests/test-results/`. View a trace with:

```bash
playwright show-trace functional_tests/test-results/<…>/trace.zip
```

Run headed / slow to watch a test:

```bash
pytest functional_tests -k find_attitude --headed --slowmo 500
```

## Layout

| File | What it covers |
| --- | --- |
| `test_smoke.py` | Page/link checks for events, mica, pcad_acq, star_hist, /version, /api, find_attitude, and the version footer |
| `test_find_attitude.py` | Pasted-catalog solution (deterministic) + telemetry/constraint cases |
| `test_navigation.py` | Event-list filter → sort → paginate → open event → step → return |
| `test_diff.py` | Test-vs-flight comparison of all pages/scenarios (report-only) |
| `conftest.py` | `--server` / `--base-url` resolution, `--run-telemetry` / `--run-diff` gating, markers |
| `helpers.py` | Find Attitude form drivers, output parsing + tolerant float/quaternion comparisons |
| `diffing.py` | Snapshot capture, text/pixel diffing, HTML report writer |
