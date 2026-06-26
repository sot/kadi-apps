"""Shared fixtures and configuration for the kadi-apps functional test suite.

These tests drive a *deployed* kadi web server (test or flight) with Playwright,
automating the manual checklist at
https://github.com/sot/web-kadi/wiki/Functional-Tests

Pick the target server with ``--server``::

    pytest functional_tests --server test     # https://web-kadi-test.cfa.harvard.edu  (default)
    pytest functional_tests --server flight   # https://web-kadi.cfa.harvard.edu

or override the URL entirely with pytest-playwright's ``--base-url``.

Both require network/VPN reachability to ``*.cfa.harvard.edu``.
"""

import os

import pytest

# Map the short server name to its base URL.
SERVERS = {
    "test": "https://web-kadi-test.cfa.harvard.edu",
    "flight": "https://web-kadi.cfa.harvard.edu",
}


def pytest_addoption(parser):
    group = parser.getgroup("kadi-apps functional tests")
    group.addoption(
        "--server",
        action="store",
        default=os.environ.get("KADI_SERVER", "test"),
        choices=sorted(SERVERS),
        help="Which deployed kadi server to test (default: test, or $KADI_SERVER). "
        "Ignored if --base-url is given.",
    )
    group.addoption(
        "--run-telemetry",
        action="store_true",
        default=False,
        help="Also run tests marked 'telemetry', which fetch live MAUDE data via the server.",
    )


@pytest.fixture(scope="session")
def base_url(request):
    """Base URL for the server under test.

    Overrides the ``base_url`` fixture from pytest-base-url so a plain
    ``--server`` selection is enough; an explicit ``--base-url`` still wins.
    """
    explicit = request.config.getoption("base_url")
    if explicit:
        return explicit.rstrip("/")
    return SERVERS[request.config.getoption("server")].rstrip("/")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-telemetry"):
        return
    skip = pytest.mark.skip(reason="needs --run-telemetry (fetches live MAUDE telemetry)")
    for item in items:
        if "telemetry" in item.keywords:
            item.add_marker(skip)
