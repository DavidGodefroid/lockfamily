#!/usr/bin/env python3
"""Render the GitHub social preview (1280x640 PNG) of every Lock Family repo.

    python3 tools/social-preview/render.py                 # all ten
    python3 tools/social-preview/render.py locksql lea     # some
    python3 tools/social-preview/render.py --sheet /tmp/sheet.png

Each image is the site kit's og template (site-kit/tools/og.html) with its
placeholders filled and social.css added on top: same logo, name and tagline
as the Lock sites' og.png, at GitHub's 1280x640, on the product's colour.

The name and the tagline are read from each repository's README on
origin/main (the banner's alt text, "<name>: <tagline>", or lea's centred
h3), in the sibling clone ../<repo> (--clones to change the directory).
Run `git fetch origin` in the clones first. With --offline the copy kept in
REPOS below is used instead; without it, a README that no longer matches
that copy stops the run, so a changed tagline is noticed, not silently
drawn.

Needs Python 3.9+ and Chrome or Chromium (--chrome, or $CHROME). Nothing
else: no pip package. GitHub has no API for the upload: each PNG goes in
the repo's Settings > General > Social preview by hand.
"""
import argparse
import html
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TEMPLATE = ROOT / "site-kit" / "tools" / "og.html"
OUT = ROOT / "assets" / "social"
W, H = 1280, 640
MAX_BYTES = 1_000_000

LOCK = "A Lock of the Lock Family"
PART = "Part of the Lock Family"

# Per repository: the logo (assets/<logo>.svg), the label above the name,
# the tagline as its README states it today and the part of it set in the
# accent, the site shown bottom right, and the colours: `bg` fills the
# frame, `key` is the accent of the tagline (AA on --card, checked below).
# Provisional palette: lockfamily#72 defines the family's colours in
# site-kit/COLOUR.md; when it lands, change bg/key here and render again.
REPOS = {
    "lockfamily": dict(logo="mark", label="Open source · Apache 2.0",
                       tagline="harness security for AI agents.",
                       key="for AI agents.", site="lockfamily.dev",
                       bg="#ffc93c", key_colour="#1f4a9c"),
    "locksql": dict(logo="locksql", label=LOCK,
                    tagline="your agent writes the query, you hold the key.",
                    key="you hold the key.", site="lockfamily.dev",
                    bg="#5b8cff", key_colour="#1f4a9c"),
    "lockmq": dict(logo="lockmq", label=LOCK,
                   tagline="your agent reads the queue, you hold the key.",
                   key="you hold the key.", site="lockfamily.dev",
                   bg="#ff8f3f", key_colour="#a04000"),
    "lockfile": dict(logo="lockfile", label=LOCK,
                     tagline="your agent asks about the file. It never reads it.",
                     key="It never reads it.", site="lockfamily.dev",
                     bg="#35c26f", key_colour="#1c6b3a"),
    "lockhttp": dict(logo="lockhttp", label=LOCK,
                     tagline="your agent browses. You hold the key.",
                     key="You hold the key.", site="lockfamily.dev",
                     bg="#38bdf8", key_colour="#075f8f"),
    "locklog": dict(logo="locklog", label=LOCK,
                    tagline="your agent reads the logs, not the people in them.",
                    key="not the people in them.", site="lockfamily.dev",
                    bg="#a98bff", key_colour="#5b33b8"),
    "lockssh": dict(logo="lockssh", label=LOCK,
                    tagline="your AI agent runs the command, you hold the key.",
                    key="you hold the key.", site="lockfamily.dev",
                    bg="#ff6f61", key_colour="#a8201a"),
    "lea": dict(logo="lea", label=PART,
                tagline="Many agents. None of your machine.",
                key="None of your machine.", site="leadeck.dev",
                bg="#ff7ab8", key_colour="#a3195b"),
    "lockhub": dict(logo="mark", label=PART,
                    tagline="one hub approves for every Lock.",
                    key="for every Lock.", site="lockfamily.dev",
                    bg="#2fcbb4", key_colour="#0e6158"),
    "lockkit": dict(logo="mark", label=PART,
                    tagline="the shared Go core of every Lock.",
                    key="of every Lock.", site="lockfamily.dev",
                    bg="#b4dc4a", key_colour="#45690a"),
}

CARD = "#fffcf5"  # --card (paper): what the tagline accent sits on


def die(msg):
    sys.exit(f"render.py: {msg}")


def luminance(hex_colour):
    def chan(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readme_tagline(repo, clones):
    """(name, tagline) from <clones>/<repo> origin/main:README.md."""
    clone = clones / repo
    try:
        text = subprocess.run(
            ["git", "-C", str(clone), "show", "origin/main:README.md"],
            check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        die(f"{repo}: cannot read origin/main:README.md in {clone} ({exc}); "
            "clone it there, or pass --clones or --offline")
    head = text[:3000]
    m = re.search(r'<img alt="([^":]+): ([^"]+)" src="docs/assets/banner-light\.svg"', head)
    if m:
        return html.unescape(m.group(1)), html.unescape(m.group(2))
    m = re.search(r'<h3 align="center">([^<]+)</h3>', head)
    if m:
        return repo, html.unescape(m.group(1)).strip()
    die(f"{repo}: no banner alt text and no centred h3 in its README")


def find_chrome(arg):
    for name in filter(None, [arg, os.environ.get("CHROME"), "google-chrome",
                              "chromium", "chromium-browser", "chrome"]):
        path = shutil.which(name)
        if path:
            return path
    die("Chrome or Chromium not found (--chrome or $CHROME)")


def screenshot(chrome, page, png, width, height):
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", f"--user-data-dir={profile}",
             "--force-device-scale-factor=1", "--virtual-time-budget=3000",
             f"--window-size={width},{height}", f"--screenshot={png}",
             page.as_uri()],
            check=True, capture_output=True, timeout=120)
    if not png.exists():
        die(f"Chrome wrote no {png}")


def png_size(path):
    with open(path, "rb") as f:
        data = f.read(24)
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        die(f"{path} is not a PNG")
    return struct.unpack(">II", data[16:24])


def page_html(name, conf, repo):
    tagline = conf["tagline"]
    tagline = tagline[0].upper() + tagline[1:]
    key = conf["key"]
    if not tagline.endswith(key):
        die(f"{repo}: key {key!r} is not the end of the tagline {tagline!r}")
    first = tagline[:-len(key)].rstrip()
    page = TEMPLATE.read_text(encoding="utf-8")
    for old, new in (
        ("{{LOCK}}", html.escape(name)),
        ("{{TAGLINE_FIRST}}", html.escape(first)),
        ("{{TAGLINE_KEY}}", html.escape(key)),
        ("{{SOURCES}}", f"github.com/DavidGodefroid/{repo}"),
        ("lockfamily.dev</span>", conf["site"] + "</span>"),
        ("A Lock of the Lock Family", html.escape(conf["label"])),
    ):
        if old not in page:
            die(f"{TEMPLATE} has no {old!r} any more: update render.py")
        page = page.replace(old, new)
    extra = (f'<link rel="stylesheet" href="social.css">'
             f'<style>:root{{--social-bg:{conf["bg"]};'
             f'--social-key:{conf["key_colour"]}}}</style></head>')
    return page.replace("</head>", extra, 1)


def render(repo, conf, chrome, clones, offline, out):
    if contrast(conf["key_colour"], CARD) < 4.5:
        die(f"{repo}: key colour {conf['key_colour']} is under 4.5:1 on {CARD}")
    name = "Lock Family" if repo == "lockfamily" else repo
    if not offline:
        name, tagline = readme_tagline(repo, clones)
        if tagline != conf["tagline"]:
            die(f"{repo}: its README now says {tagline!r}, REPOS says "
                f"{conf['tagline']!r}: update REPOS (tagline and key)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        assets = tmp / "assets"
        assets.mkdir()
        shutil.copy(ROOT / "assets" / "tokens.css", assets)
        shutil.copy(ROOT / "site-kit" / "assets" / "lock-site.css", assets)
        shutil.copytree(ROOT / "assets" / "fonts", assets / "fonts")
        shutil.copy(ROOT / "assets" / f"{conf['logo']}.svg", assets / "logo.svg")
        shutil.copy(HERE / "social.css", tmp)
        page = tmp / "og.html"
        page.write_text(page_html(name, conf, repo), encoding="utf-8")
        png = out / f"{repo}.png"
        png.unlink(missing_ok=True)
        screenshot(chrome, page, png, W, H)
    size = png_size(png)
    if size != (W, H):
        die(f"{png}: {size[0]}x{size[1]}, expected {W}x{H}")
    weight = png.stat().st_size
    if weight >= MAX_BYTES:
        die(f"{png}: {weight} bytes, GitHub wants under 1 MB")
    print(f"{png.relative_to(ROOT) if png.is_relative_to(ROOT) else png}  "
          f"{size[0]}x{size[1]}  {weight // 1024} KB")


def sheet(chrome, out, target):
    """A contact sheet of the ten images at 640x320, the size GitHub's
    guidance asks the text to stay legible at."""
    with tempfile.TemporaryDirectory() as tmp:
        cells = "".join(
            f'<img src="{(out / (repo + ".png")).resolve().as_uri()}" width="640" height="320">'
            for repo in REPOS)
        page = Path(tmp) / "sheet.html"
        page.write_text(
            "<!doctype html><meta charset=utf-8><style>body{margin:0;padding:20px;"
            "background:#fffcf5;display:grid;grid-template-columns:640px 640px;gap:20px}"
            "img{display:block}</style>" + cells, encoding="utf-8")
        rows = -(-len(REPOS) // 2)
        target = Path(target).resolve()
        target.unlink(missing_ok=True)
        screenshot(chrome, page, target, 2 * 640 + 60, rows * 340 + 20)
    print(f"{target}  contact sheet")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repos", nargs="*", help="default: all ten")
    ap.add_argument("--clones", type=Path, default=ROOT.parent,
                    help="directory of the repositories' clones (default: next to this one)")
    ap.add_argument("--offline", action="store_true",
                    help="do not read the READMEs, use the taglines kept in render.py")
    ap.add_argument("--out", type=Path, default=OUT, help="default: assets/social")
    ap.add_argument("--chrome", help="Chrome or Chromium binary")
    ap.add_argument("--sheet", metavar="PNG",
                    help="also write a contact sheet of the images in --out")
    args = ap.parse_args()
    unknown = [r for r in args.repos if r not in REPOS]
    if unknown:
        die(f"unknown repository: {', '.join(unknown)} (known: {', '.join(REPOS)})")
    chrome = find_chrome(args.chrome)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for repo in args.repos or REPOS:
        render(repo, REPOS[repo], chrome, args.clones.resolve(), args.offline, out)
    if args.sheet:
        sheet(chrome, out, args.sheet)


if __name__ == "__main__":
    main()
