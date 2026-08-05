"""Capture / compare / report machinery for the test-vs-flight diff tests.

``capture`` snapshots a rendered page (visible text + full-page screenshot)
with the version footer masked, since the deployed versions always differ
between servers. ``DiffReport`` collects one entry per compared page/stage and
writes a static HTML report to ``diff-results/``: an index flagging which
entries differ, and a detail page per entry with a side-by-side text diff, a
pixel-diff image, and a blink toggle between the two screenshots (the manual
"flip between browser tabs" check, automated).
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


_CSS = """
body { font-family: sans-serif; margin: 1.5em; color: #222; }
h1 { font-size: 1.4em; } h2 { font-size: 1.1em; margin-top: 1.5em; }
table.index { border-collapse: collapse; }
table.index td, table.index th { border: 1px solid #ccc; padding: 0.3em 0.8em; text-align: left; }
.status-identical { color: #2a7a2a; }
.status-differs { color: #b03030; font-weight: bold; }
pre.versions { background: #f4f4f4; padding: 0.6em; display: inline-block;
               vertical-align: top; margin-right: 2em; }
/* difflib.HtmlDiff table classes */
table.diff { font-family: monospace; font-size: 0.85em; border: 1px solid #ccc; }
table.diff td { padding: 0 0.3em; vertical-align: top; white-space: pre-wrap; }
.diff_header { background-color: #e0e0e0; }
td.diff_header { text-align: right; }
.diff_next { background-color: #c0c0c0; }
.diff_add { background-color: #aaffaa; }
.diff_chg { background-color: #ffff77; }
.diff_sub { background-color: #ffaaaa; }
.shots img { max-width: 45%; border: 1px solid #ccc; vertical-align: top; }
.shots .full { max-width: 92%; }
.blink { margin: 1em 0; }
.blink img { max-width: 92%; border: 2px solid #444; }
"""

_BLINK_JS = """
function startBlink() {
  const img = document.getElementById('blink-img');
  const label = document.getElementById('blink-label');
  const srcs = [img.dataset.test, img.dataset.flight];
  const names = ['test', 'flight'];
  let i = 0;
  if (window._blinkTimer) { clearInterval(window._blinkTimer); window._blinkTimer = null;
                            label.textContent = '(stopped)'; return; }
  window._blinkTimer = setInterval(() => {
    i = 1 - i; img.src = srcs[i]; label.textContent = names[i];
  }, 700);
}
"""


@dataclass
class _Entry:
    item_id: str
    slug: str
    text_differs: bool
    n_changed_pixels: int

    @property
    def differs(self):
        return self.text_differs or self.n_changed_pixels > 0


@dataclass
class DiffReport:
    """Collects per-page comparison results and renders the HTML report."""

    out_dir: Path
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
        entry = _Entry(
            item_id=item_id,
            slug=slug,
            text_differs=table is not None,
            n_changed_pixels=n_changed,
        )
        self.entries.append(entry)
        (item_dir / "index.html").write_text(self._detail_html(entry, table))

    def finalize(self):
        self.index_path.write_text(self._index_html())
        return self.index_path

    # -- rendering ----------------------------------------------------------

    def _page(self, title, body):
        return (
            f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
            f"<body><h1>{html.escape(title)}</h1>{body}</body></html>"
        )

    def _index_html(self):
        parts = []
        if self.versions:
            parts.append("<h2>Server versions</h2>")
            for server, text in self.versions.items():
                parts.append(
                    f"<pre class='versions'><b>{html.escape(server)}</b>\n"
                    f"{html.escape(text)}</pre>"
                )
        n_diff = sum(e.differs for e in self.entries)
        parts.append(
            f"<h2>Compared pages ({n_diff} of {len(self.entries)} differ)</h2>"
        )
        parts.append(
            "<table class='index'><tr><th>Page</th><th>Text</th>"
            "<th>Pixels changed</th><th>Status</th></tr>"
        )
        for e in self.entries:
            status = (
                "<span class='status-differs'>differs</span>"
                if e.differs
                else "<span class='status-identical'>identical</span>"
            )
            text_status = "differs" if e.text_differs else "same"
            parts.append(
                f"<tr><td><a href='items/{e.slug}/index.html'>"
                f"{html.escape(e.item_id)}</a></td>"
                f"<td>{text_status}</td><td>{e.n_changed_pixels}</td>"
                f"<td>{status}</td></tr>"
            )
        parts.append("</table>")
        return self._page("kadi-apps test vs flight diff report", "".join(parts))

    def _detail_html(self, entry, table):
        parts = ["<p><a href='../../index.html'>&larr; back to index</a></p>"]

        parts.append("<h2>Text diff</h2>")
        parts.append(table if table else "<p>Rendered text is identical.</p>")

        parts.append("<h2>Blink comparison</h2>")
        parts.append(
            "<div class='blink'>"
            "<button onclick='startBlink()'>start / stop blink</button> "
            "showing: <b id='blink-label'>test</b><br>"
            "<img id='blink-img' src='test.png' "
            "data-test='test.png' data-flight='flight.png'>"
            "</div>"
            f"<script>{_BLINK_JS}</script>"
        )

        parts.append(
            f"<h2>Pixel diff ({entry.n_changed_pixels} pixels changed)</h2>"
            "<div class='shots'><img class='full' src='diff.png'></div>"
        )

        parts.append(
            "<h2>Side by side</h2>"
            "<div class='shots'>"
            "<figure style='display:inline-block'><figcaption>test</figcaption>"
            "<img src='test.png'></figure>"
            "<figure style='display:inline-block'><figcaption>flight</figcaption>"
            "<img src='flight.png'></figure>"
            "</div>"
        )
        return self._page(f"diff: {entry.item_id}", "".join(parts))
