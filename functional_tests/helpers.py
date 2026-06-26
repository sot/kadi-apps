"""Helpers for parsing and asserting on Find Attitude output.

The Find Attitude page renders, for each solution, a ``Solution Quaternion``
strong block, an ``RA=/Dec=/Roll=`` block, and a ``<pre>`` star-match summary
table (astropy pformat) whose last column is ``m_agasc_id`` and whose unmatched
rows show ``--``.  See
kadi_apps/blueprints/find_attitude/templates/find_attitude/index.html
"""

import re

# The 8-star catalog from the wiki functional-test page (groups 2 and the
# Production-Server check). Indented to look natural when typed into the form;
# get_stars_from_text tolerates leading whitespace.
STAR_CATALOG = """\
slot yag zag mag
0    -381.28    1479.95      7.2
1    -582.55    -830.85      8.9
2    2076.33   -2523.10      8.5
3    -498.12    -958.33      5.0
4    -431.68    1600.98      8.2
5    -282.40     980.50      7.9
6   -3276.80   -3276.80     13.9
7     573.25   -2411.70      7.1
"""

_QUAT_RE = re.compile(r"Solution Quaternion:\s*\[([^\]]+)\]")
_RADECROLL_RE = re.compile(r"RA=\s*([-\d.]+)\s+Dec=\s*([-\d.]+)\s+Roll=\s*([-\d.]+)")


def assert_close(actual, expected, atol, label=""):
    assert abs(actual - expected) <= atol, (
        f"{label}: {actual} not within {atol} of {expected}"
    )


def assert_quat_close(actual, expected, atol=1e-4, label="quaternion"):
    assert len(actual) == len(expected) == 4, f"{label}: expected 4 components"
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert abs(a - e) <= atol, (
            f"{label}[{i}]: {a} not within {atol} of {e} (full={actual} vs {expected})"
        )


def quats_match(actual, expected, atol=1e-4):
    """True if every component is within atol (helper for unordered matching)."""
    return len(actual) == len(expected) == 4 and all(
        abs(a - e) <= atol for a, e in zip(actual, expected)
    )


def _parse_summary_table(text):
    """Parse one star-match ``<pre>`` block -> (agasc_ids set, n_matched)."""
    agasc_ids = set()
    n_matched = 0
    for line in text.splitlines():
        toks = line.replace("|", " ").split()
        # Data rows start with an integer slot; skip header / dashed separator.
        if not toks or not toks[0].isdigit():
            continue
        last = toks[-1]
        if last.lstrip("-").isdigit() and last != "--":
            agasc_ids.add(int(last))
            n_matched += 1
    return agasc_ids, n_matched


def parse_solutions(page):
    """Return a list of solution dicts parsed from the rendered page.

    Each dict has: ``quat`` (list[float]), ``ra``/``dec``/``roll`` (float or
    None), ``agasc_ids`` (set[int]), ``n_matched`` (int).
    """
    body = page.inner_text("body")
    quats = [
        [float(v) for v in m.group(1).split(",")] for m in _QUAT_RE.finditer(body)
    ]

    # Star-match summary tables, in document order (one per solution). The
    # trailing "Supplied find_attitude Inputs" <pre> lacks the m_agasc_id header.
    summaries = [
        t for t in page.locator("pre").all_inner_texts() if "m_agasc_id" in t
    ]

    # RA/Dec/Roll for the solution coordinates. (Only unambiguous when there is
    # no estimated-attitude block, i.e. the pasted-catalog case.)
    radecroll = _RADECROLL_RE.findall(body)

    solutions = []
    for i, quat in enumerate(quats):
        agasc_ids, n_matched = (
            _parse_summary_table(summaries[i]) if i < len(summaries) else (set(), 0)
        )
        ra = dec = roll = None
        if len(quats) == 1 and radecroll:
            ra, dec, roll = (float(x) for x in radecroll[0])
        solutions.append(
            {
                "quat": quat,
                "ra": ra,
                "dec": dec,
                "roll": roll,
                "agasc_ids": agasc_ids,
                "n_matched": n_matched,
            }
        )
    return solutions


def filter_star_rows(stars_text, keep_slots):
    """Keep the header plus rows whose slot is in ``keep_slots``; drop the rest.

    Used for the "edit the stars to only include slots N…" steps. Lines are kept
    verbatim so the result still parses with get_stars_from_text.
    """
    keep = set(keep_slots)
    out = []
    header_done = False
    for line in stars_text.splitlines():
        toks = line.replace("|", " ").split()
        if toks and toks[0].isdigit():
            if int(toks[0]) in keep:
                out.append(line)
        else:
            # Header / column line(s) and any non-data line: keep.
            if line.strip():
                out.append(line)
                header_done = True
            elif header_done:
                # preserve a single trailing structure; skip blank noise
                continue
    return "\n".join(out) + "\n"
