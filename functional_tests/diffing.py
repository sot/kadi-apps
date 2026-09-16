"""Capture / compare / report machinery for the test-vs-flight diff tests.

``capture`` snapshots a rendered page (visible text + full-page screenshot)
with the version footer masked, since the deployed versions always differ
between servers. ``DiffReport`` collects one entry per compared page/stage and
writes a static HTML report to ``diff-results/`` (Bootstrap via CDN, styled
after the periscope drift trending pages): an index flagging which entries
differ, and a detail page per entry with prev/next navigation and tabs holding
a blink comparison of the two screenshots (the manual "flip between browser
tabs" check, automated), a side-by-side text diff, a pixel-diff image, and the
screenshots side by side. Differences fully explained by known URL
substitutions (each server naming itself) are flagged "expected diff" instead
of "differs".
"""

import difflib
import html
import io
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops

# (pattern, replacement) pairs rewritten in the page's text nodes before
# capture, so noise that is expected to differ between any two renders is
# excluded from both the text diff and the screenshots. Patterns are compiled
# as JavaScript RegExp — keep them JS/Python compatible. The version footer is
# handled separately by hiding the <footer> element.
NOISE_REPLACEMENTS = [
    # Find Attitude stamps the render time on the result page
    # ("Attitude solution generated at ..." / "ERROR generated at ...").
    (r"generated at .* on \S+", "generated at <time>"),
    (r"Date for Pitch/Roll: \S+", "Date for Pitch/Roll: <time>"),
]

# Floats printed with more than 8 decimals (proper-motion-corrected
# coordinates, fit results) jitter in their last digits between renders; they
# are rounded to 8 decimals, far below any meaningful difference. Passed to
# the JS below as data so no string-literal escaping is involved.
_FLOAT_TAIL_RE = r"-?\d+\.\d{9,}"

_NORMALIZE_JS = """
(args) => {
  const regs = args.replacements.map(([p, r]) => [new RegExp(p, 'g'), r]);
  const floatRe = new RegExp(args.floatPattern, 'g');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    let text = node.textContent;
    for (const [re, r] of regs) text = text.replace(re, r);
    text = text.replace(floatRe, (m) => Number(m).toFixed(8));
    if (text !== node.textContent) node.textContent = text;
  }
}
"""

# Pixel channel difference below this is ignored (antialiasing jitter).
PIXEL_THRESHOLD = 16


@dataclass
class Snapshot:
    """Rendered state of one page on one server."""

    text: str
    png: bytes


def capture(page):
    """Snapshot the current page: visible body text + full-page screenshot.

    The version footer is hidden (keeping its layout space) and the
    ``NOISE_REPLACEMENTS`` / float-tail normalizations are applied to the DOM
    first, so known noise is excluded from both the text and the screenshot.
    These changes only live until the next navigation, which is exactly the
    lifetime we want.
    """
    page.add_style_tag(content="footer { visibility: hidden; }")
    # Current-time timestamps (e.g. the proper-motion-correction date column in
    # the Find Attitude star tables) differ between any two renders: mask
    # year:doy timestamps whose day is today.
    today = time.strftime("%Y:%j", time.gmtime())
    replacements = NOISE_REPLACEMENTS + [
        (today + r":\d{2}:\d{2}:\d{2}(\.\d+)?", "<now>")
    ]
    page.evaluate(
        _NORMALIZE_JS, {"replacements": replacements, "floatPattern": _FLOAT_TAIL_RE}
    )
    text = page.inner_text("body")
    # For the text diff only (screenshots stay faithful): collapse column
    # padding and dashed table rules, whose widths astropy pformat derives
    # from float repr lengths that jitter between renders.
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[^\S\n]+", " ", line)
        line = re.sub(r"-{4,}", "----", line)
        lines.append(line.rstrip())
    return Snapshot(text="\n".join(lines), png=page.screenshot(full_page=True))


def text_diff_table(a_text, b_text, a_label="test", b_label="flight"):
    """Side-by-side HTML diff table of changed lines (with context), or None
    if the texts are identical."""
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    if a_lines == b_lines:
        return None
    differ = difflib.HtmlDiff(wrapcolumn=90)
    return differ.make_table(
        a_lines, b_lines, a_label, b_label, context=True, numlines=3
    )


def image_diff(a_png, b_png):
    """Compare two screenshots; return ``(diff_png, n_changed_pixels)``.

    Images are padded to a common size first. The padding is magenta so that a
    page-length difference is itself flagged (white padding would blend into a
    typical white page background and go uncounted). The diff image is the
    test screenshot dimmed to grey with changed pixels in red.
    """
    a = Image.open(io.BytesIO(a_png)).convert("RGB")
    b = Image.open(io.BytesIO(b_png)).convert("RGB")
    size = (max(a.width, b.width), max(a.height, b.height))
    if a.size != size:
        a = _pad(a, size)
    if b.size != size:
        b = _pad(b, size)

    delta = ImageChops.difference(a, b).convert("L")
    mask = delta.point(lambda v: 255 if v > PIXEL_THRESHOLD else 0)
    n_changed = mask.histogram()[255]

    diff_img = Image.blend(a.convert("L").convert("RGB"), Image.new("RGB", size, "white"), 0.6)
    diff_img.paste(Image.new("RGB", size, (220, 30, 30)), mask=mask)

    out = io.BytesIO()
    diff_img.save(out, format="PNG")
    return out.getvalue(), n_changed


def _pad(img, size):
    padded = Image.new("RGB", size, (255, 0, 255))
    padded.paste(img, (0, 0))
    return padded


def _slug(item_id):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", item_id)


# Same Bootstrap 5.1.3 CDN build as the periscope drift trending pages, whose
# look this report follows.
_BOOTSTRAP_CSS = (
    "<link href='https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css'"
    " rel='stylesheet'"
    " integrity='sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3'"
    " crossorigin='anonymous'>"
)
_BOOTSTRAP_JS = (
    "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js'"
    " integrity='sha384-ka7Sk0Gln4gmtz2MlQnikT1wXgYsOg+OMhuP+IlRH9sENBO0LRn5q+8nbTov4+1p'"
    " crossorigin='anonymous'></script>"
)

_CSS = """
h1 { color: #990000; font-size: 1.6em; margin-top: 0.8em; }
h2 { color: #990000; font-size: 1.2em; margin-top: 1.2em; }
pre.versions { background: #f4f4f4; padding: 0.6em; display: inline-block;
               max-width: 100%; overflow-x: auto; }
/* difflib.HtmlDiff table classes */
table.diff { font-family: monospace; font-size: 0.85em; border: 1px solid #ccc; }
table.diff td { padding: 0 0.3em; vertical-align: top; white-space: pre-wrap; }
.diff_header { background-color: #e0e0e0; }
td.diff_header { text-align: right; }
.diff_next { background-color: #c0c0c0; }
.diff_add { background-color: #aaffaa; }
.diff_chg { background-color: #ffff77; }
.diff_sub { background-color: #ffaaaa; }
.blink { margin: 1em 0; }
.blink img { border: 2px solid #444; }
"""

# Three-state comparison of two content blocks (screenshots on detail pages,
# /version outputs on the index): show flight, show test, or auto-toggle
# between them every 700 ms. One blink component per page (fixed element ids).
_BLINK_JS = """
let _blinkTimer = null;
function _blinkShow(name) {
  document.getElementById('blink-test').style.display = name === 'test' ? '' : 'none';
  document.getElementById('blink-flight').style.display = name === 'flight' ? '' : 'none';
  document.getElementById('blink-label').textContent = name;
}
function setBlinkMode(mode) {
  if (_blinkTimer) { clearInterval(_blinkTimer); _blinkTimer = null; }
  if (mode !== 'toggle') { _blinkShow(mode); return; }
  let name = 'test';
  _blinkShow(name);
  _blinkTimer = setInterval(() => {
    name = name === 'test' ? 'flight' : 'test';
    _blinkShow(name);
  }, 700);
}
window.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('blink-test')) setBlinkMode('toggle');
});
"""


def _blink_html(test_html, flight_html):
    """Blink comparison of two content blocks, with a flight / test / toggle
    control (toggle, i.e. auto-blinking, is the default)."""
    buttons = []
    for mode in ("flight", "test", "toggle"):
        checked = " checked" if mode == "toggle" else ""
        buttons.append(
            f"<input type='radio' class='btn-check' name='blink-mode' "
            f"id='blink-{mode}-btn' onchange=\"setBlinkMode('{mode}')\"{checked}>"
            f"<label class='btn btn-outline-secondary btn-sm' "
            f"for='blink-{mode}-btn'>{mode}</label>"
        )
    return (
        "<div class='blink'>"
        f"<div class='btn-group' role='group'>{''.join(buttons)}</div> "
        "showing: <b id='blink-label'>test</b>"
        f"<div id='blink-test'>{test_html}</div>"
        f"<div id='blink-flight' style='display:none'>{flight_html}</div>"
        "</div>"
    )


@dataclass
class _Entry:
    item_id: str
    slug: str
    text_differs: bool
    n_changed_pixels: int
    # The differences are fully explained by expected_replacements (e.g. the
    # server's own URL in the /api examples).
    expected: bool = False
    # difflib.HtmlDiff table, or None if the texts are identical. Kept here so
    # detail pages can be written in finalize(), when prev/next are known.
    table: str = None
    # "test", "flight", or "both" when the page errored on that server; such
    # entries have nothing to compare and get no detail page.
    failed: str = None

    @property
    def differs(self):
        return self.text_differs or self.n_changed_pixels > 0


@dataclass
class DiffReport:
    """Collects per-page comparison results and renders the HTML report."""

    out_dir: Path
    # (substring, replacement) pairs applied to the test snapshot's text; if
    # they make it equal to the flight text, the entry's differences are
    # "expected" (e.g. each server naming its own URL in the /api examples).
    expected_replacements: list = field(default_factory=list)
    versions: dict = field(default_factory=dict)
    entries: list = field(default_factory=list)

    def __post_init__(self):
        self.out_dir = Path(self.out_dir)
        # Start clean so the report never mixes runs.
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        (self.out_dir / "items").mkdir(parents=True)

    @property
    def index_path(self):
        return self.out_dir / "index.html"

    def set_versions(self, server, text):
        """Record a server's /version output for the report header."""
        self.versions[server] = text

    def add(self, item_id, test_snap, flight_snap):
        """Compare two snapshots of one page/stage and add them to the report."""
        slug = _slug(item_id)
        item_dir = self.out_dir / "items" / slug
        item_dir.mkdir(parents=True, exist_ok=True)

        (item_dir / "test.png").write_bytes(test_snap.png)
        (item_dir / "flight.png").write_bytes(flight_snap.png)

        diff_png, n_changed = image_diff(test_snap.png, flight_snap.png)
        (item_dir / "diff.png").write_bytes(diff_png)

        table = text_diff_table(test_snap.text, flight_snap.text)
        expected_text = test_snap.text
        for old, new in self.expected_replacements:
            expected_text = expected_text.replace(old, new)
        self.entries.append(
            _Entry(
                item_id=item_id,
                slug=slug,
                text_differs=table is not None,
                n_changed_pixels=n_changed,
                expected=table is not None and expected_text == flight_snap.text,
                table=table,
            )
        )

    def add_failure(self, item_id, failed):
        """Record a page that errored on one or both servers ("test",
        "flight", or "both"); it appears on the index but has no detail
        page."""
        self.entries.append(
            _Entry(
                item_id=item_id,
                slug=_slug(item_id),
                text_differs=False,
                n_changed_pixels=0,
                failed=failed,
            )
        )

    def finalize(self):
        # Detail pages are written here, not in add(), so each one can link to
        # its prev/next neighbor. Failed entries have no detail page.
        entries = [e for e in self.entries if not e.failed]
        for prev, entry, nxt in zip(
            [None] + entries[:-1], entries, entries[1:] + [None]
        ):
            item_dir = self.out_dir / "items" / entry.slug
            (item_dir / "index.html").write_text(self._detail_html(entry, prev, nxt))
        self.index_path.write_text(self._index_html())
        return self.index_path

    # -- rendering ----------------------------------------------------------

    def _page(self, title, body):
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(title)}</title>{_BOOTSTRAP_CSS}"
            f"<style>{_CSS}</style></head>"
            f"<body><div class='container-md'><h1>{html.escape(title)}</h1>{body}</div>"
            f"<script>{_BLINK_JS}</script>{_BOOTSTRAP_JS}</body></html>"
        )

    def _index_html(self):
        parts = []
        if self.versions:
            parts.append("<h2>Server versions</h2>")
            pres = {
                server: f"<pre class='versions'><b>{html.escape(server)}</b>\n"
                f"{html.escape(text)}</pre>"
                for server, text in self.versions.items()
            }
            if set(pres) == {"test", "flight"}:
                parts.append(_blink_html(pres["test"], pres["flight"]))
            else:
                parts.extend(pres.values())
        n_expected = sum(e.differs and e.expected for e in self.entries)
        n_diff = sum(e.differs and not e.expected for e in self.entries)
        n_failed = sum(bool(e.failed) for e in self.entries)
        notes = f", {n_expected} expected" if n_expected else ""
        notes += f", {n_failed} failed" if n_failed else ""
        parts.append(
            f"<h2>Compared pages ({n_diff} of {len(self.entries)} differ"
            f"{notes})</h2>"
        )
        parts.append(
            "<table class='table table-striped w-auto'><tr><th>Page</th><th>Text</th>"
            "<th>Pixels changed</th><th>Status</th></tr>"
        )
        for e in self.entries:
            if e.failed:
                status = f"<span class='text-danger fw-bold'>{e.failed} failed</span>"
                parts.append(
                    f"<tr><td>{html.escape(e.item_id)}</td>"
                    f"<td>&mdash;</td><td>&mdash;</td><td>{status}</td></tr>"
                )
                continue
            if not e.differs:
                status = "<span class='text-success'>identical</span>"
            elif e.expected:
                status = "<span class='text-primary fw-bold'>expected diff</span>"
            else:
                status = "<span class='text-danger fw-bold'>differs</span>"
            text_status = "differs" if e.text_differs else "same"
            parts.append(
                f"<tr><td><a href='items/{e.slug}/index.html'>"
                f"{html.escape(e.item_id)}</a></td>"
                f"<td>{text_status}</td><td>{e.n_changed_pixels}</td>"
                f"<td>{status}</td></tr>"
            )
        parts.append("</table>")
        return self._page("kadi-apps test vs flight diff report", "".join(parts))

    def _detail_html(self, entry, prev, nxt):
        nav = []
        if prev:
            nav.append(
                f"&larr; <a href='../{prev.slug}/index.html'>"
                f"{html.escape(prev.item_id)}</a>"
            )
        nav.append("<a href='../../index.html'>index</a>")
        if nxt:
            nav.append(
                f"<a href='../{nxt.slug}/index.html'>"
                f"{html.escape(nxt.item_id)}</a> &rarr;"
            )
        parts = [f"<p>{' | '.join(nav)}</p>"]

        blink = _blink_html(
            "<img class='img-fluid' src='test.png'>",
            "<img class='img-fluid' src='flight.png'>",
        )
        text_diff = entry.table if entry.table else "<p>Rendered text is identical.</p>"
        pixels = "<img class='img-fluid border' src='diff.png'>"
        side_by_side = (
            "<div class='row'>"
            "<div class='col-md-6'><figure><figcaption>test</figcaption>"
            "<img class='img-fluid border' src='test.png'></figure></div>"
            "<div class='col-md-6'><figure><figcaption>flight</figcaption>"
            "<img class='img-fluid border' src='flight.png'></figure></div>"
            "</div>"
        )
        panes = [
            ("blink", "Blink", blink),
            ("text", "Text diff", text_diff),
            ("pixels", f"Pixel diff ({entry.n_changed_pixels} px)", pixels),
            ("side", "Side by side", side_by_side),
        ]
        tabs = ["<ul class='nav nav-tabs' role='tablist'>"]
        content = ["<div class='tab-content pt-3'>"]
        for i, (pane_id, label, pane) in enumerate(panes):
            active = " active" if i == 0 else ""
            tabs.append(
                "<li class='nav-item' role='presentation'>"
                f"<button class='nav-link{active}' data-bs-toggle='tab' "
                f"data-bs-target='#{pane_id}' type='button' role='tab'>"
                f"{label}</button></li>"
            )
            content.append(
                f"<div class='tab-pane fade{' show active' if i == 0 else ''}' "
                f"id='{pane_id}' role='tabpanel'>{pane}</div>"
            )
        tabs.append("</ul>")
        content.append("</div>")
        parts.extend(tabs + content)
        return self._page(f"diff: {entry.item_id}", "".join(parts))
