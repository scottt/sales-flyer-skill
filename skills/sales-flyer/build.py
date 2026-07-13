#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fonttools[woff]>=4.55",
#     "jinja2>=3.1",
#     "playwright>=1.49",
#     "pyyaml>=6.0",
# ]
# ///
"""Build sales flyers from a YAML content file.

Outputs (into --outdir):
  <name>.pdf            A4 print/email flyer, one page per `pages` entry
  <name>-print.html     the rendered A4 HTML (inspect or hand-tweak)
  <name>-card-N.png     square messaging-app cards (default 1040x1040, LINE spec)
  <name>-cards.html     the rendered card HTML

Runs on Windows, macOS and Linux with no system libraries: Chromium is
downloaded into a uv-managed environment on first run.

Usage:
    uv run build.py content/example-neuralplay.yaml
    uv run build.py my.yaml --outdir out --only pdf
"""

from __future__ import annotations

import argparse
import base64
import io
import platform
import re
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"

# Keys a flyer cannot be built without. Optional keys (trust, callout, steps,
# faq, badges, every *_mobile variant) are absent-tolerant in the templates.
REQUIRED = ["brand", "hero", "value_props", "jobs", "stats", "pricing", "cta"]


def validate(data: dict, source: Path) -> None:
    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        raise SystemExit(f"{source}: missing required key(s): {', '.join(missing)}")
    for i, s in enumerate(data["stats"], 1):
        if not s.get("value"):
            raise SystemExit(f"{source}: stats[{i}] has no 'value'")
    for i, p in enumerate(data["pricing"], 1):
        if not p.get("price"):
            raise SystemExit(f"{source}: pricing[{i}] ({p.get('tier', '?')}) has no 'price' — "
                             "a flyer without a number is a brochure, not sales material")


def render_html(template_name: str, data: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=False,  # content is authored by the flyer owner, not untrusted input
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(template_name).render(**data)


# --------------------------------------------------------------------------
# Font embedding.
#
# Headless Chromium does not reliably resolve system CJK fonts, and even when it
# does, output would differ between a Linux box and a Windows laptop. So we find
# a real font file, subset it to just the glyphs this flyer uses (a few hundred,
# not the 20k+ in a full CJK face), and inline it as base64 woff2. Renders are
# then byte-identical everywhere and depend on no installed fonts.
# --------------------------------------------------------------------------

# Fallback font files per platform, used when fontconfig isn't available.
PLATFORM_FONTS = {
    "Windows": [
        (r"C:\Windows\Fonts\msjh.ttc", 0),      # Microsoft JhengHei (TC)
        (r"C:\Windows\Fonts\msyh.ttc", 0),      # Microsoft YaHei (SC)
        (r"C:\Windows\Fonts\segoeui.ttf", 0),
    ],
    "Darwin": [
        ("/System/Library/Fonts/PingFang.ttc", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
    ],
}


def find_font_file(family: str, bold: bool = False) -> tuple[str, int] | None:
    """Locate a font file + TTC index for `family`, preferring fontconfig."""
    pattern = f"{family}:bold" if bold else family
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}\t%{index}", pattern],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        path, _, idx = out.partition("\t")
        if path and Path(path).exists():
            return path, int(idx or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass

    for path, idx in PLATFORM_FONTS.get(platform.system(), []):
        if Path(path).exists():
            return path, idx
    return None


def subset_font_datauri(font_path: str, index: int, text: str) -> str | None:
    """Subset a font to `text` and return it as a base64 woff2 data URI."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(font_path, fontNumber=index, lazy=True)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.desubroutinize = True
        opts.drop_tables += ["DSIG"]
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text=text)
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        font.close()
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001 — any font failure falls back gracefully
        print(f"  ! could not subset {font_path}: {exc}", file=sys.stderr)
        return None


def build_font_face(data: dict) -> str:
    """Return a <style> block of @font-face rules with the font inlined, or ''."""
    # Every character that can appear in the output — subset to exactly these.
    text = "".join(str(v) for v in _walk_strings(data))
    text += "0123456789.,%$/×—–…()（）：、。「」ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    text += "abcdefghijklmnopqrstuvwxyz✓"

    family = data.get("font_family") or _first_family(data.get("font", ""))
    if not family:
        return ""

    faces = []
    for weight, bold in ((400, False), (700, True)):
        located = find_font_file(family, bold=bold)
        if not located:
            continue
        b64 = subset_font_datauri(*located, text)
        if b64:
            faces.append(
                "@font-face{font-family:'FlyerFont';font-style:normal;"
                f"font-weight:{weight};"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
            )
    if not faces:
        print(f"  ! no font file found for '{family}' — falling back to system fonts",
              file=sys.stderr)
        return ""
    print(f"  embedded '{family}' ({len(faces)} weight(s), {len(set(text))} glyphs)")
    return "<style>" + "".join(faces) + "</style>"


def _first_family(font_stack: str) -> str:
    """'\"Noto Sans CJK TC\", sans-serif' -> 'Noto Sans CJK TC'"""
    first = font_stack.split(",")[0].strip()
    return re.sub(r'^["\']|["\']$', "", first)


def _walk_strings(node):
    """Yield every string in a nested dict/list structure."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)


def ensure_chromium() -> None:
    """Install the Chromium browser Playwright needs (idempotent, cached)."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
        return
    except PlaywrightError:
        pass

    print("==> Downloading Chromium (first run only)...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )


def build_pdf(html: str, out_pdf: Path, html_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    html_path.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # file:// so relative assets (embedded fonts, images) resolve
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(out_pdf),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    print(f"  wrote {out_pdf}")


def build_cards(html: str, out_prefix: Path, html_path: Path, size: int) -> list[Path]:
    """Screenshot each .card element to an exact size x size PNG."""
    from playwright.sync_api import sync_playwright

    html_path.write_text(html, encoding="utf-8")
    written: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size})
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        cards = page.query_selector_all(".card")
        if not cards:
            raise SystemExit("No .card elements found in the cards template.")
        for i, card in enumerate(cards, 1):
            out = out_prefix.with_name(f"{out_prefix.name}-card-{i}.png")
            card.screenshot(path=str(out))
            written.append(out)
            print(f"  wrote {out}")
        browser.close()
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("content", type=Path, help="YAML content file")
    ap.add_argument("--outdir", type=Path, default=Path("out"), help="output directory (default: out)")
    ap.add_argument(
        "--only",
        choices=["pdf", "cards"],
        help="build only the A4 PDF, or only the square cards (default: both)",
    )
    ap.add_argument("--card-size", type=int, default=1040, help="square card px (default: 1040, LINE spec)")
    ap.add_argument(
        "--no-embed-font",
        action="store_true",
        help="use system fonts instead of inlining a subset (smaller HTML, non-portable output)",
    )
    args = ap.parse_args()

    if not args.content.exists():
        raise SystemExit(f"Content file not found: {args.content}")

    data = yaml.safe_load(args.content.read_text(encoding="utf-8"))
    validate(data, args.content)
    name = data.get("name") or args.content.stem
    args.outdir.mkdir(parents=True, exist_ok=True)
    prefix = args.outdir / name

    ensure_chromium()

    print("==> Embedding fonts")
    data["font_face"] = "" if args.no_embed_font else build_font_face(data)
    # Templates use FlyerFont first, then the YAML stack as a fallback.
    data["font_css"] = (
        f"'FlyerFont', {data['font']}" if data["font_face"] else data["font"]
    )

    if args.only != "cards":
        print("==> Building A4 PDF")
        build_pdf(
            render_html("print.html.j2", data),
            prefix.with_suffix(".pdf"),
            prefix.with_name(f"{name}-print.html"),
        )

    if args.only != "pdf":
        print(f"==> Building {args.card_size}x{args.card_size} cards")
        build_cards(
            render_html("cards.html.j2", data),
            prefix,
            prefix.with_name(f"{name}-cards.html"),
            args.card_size,
        )

    print("==> Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
