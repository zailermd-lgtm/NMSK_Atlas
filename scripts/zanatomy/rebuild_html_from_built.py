#!/usr/bin/env python3
"""Q197: re-render a BUILT Z-Anatomy page with a newer viewer/zan_atlas.template.html WITHOUT recomputing geometry.

build_zan_atlas_viewer.render_html() fills three placeholders of the template (__BIN_B64__, __BIN_FILES_JSON__,
__MANIFEST_JSON__) and, per manifest["variant"], applies a wording block (vhf = female fitted, vhm = Z male fitted,
native_female = base female, none = Z male base). Everything else in the page is the template. So a built page is
(template, wording, three data literals) and this script takes the three data literals back out of the built HTML as
raw text (no JSON round trip, so they stay byte-identical), copies the geo files it names, and fills the NEW template
the same way the builder does (it imports the builder's own wording tables -- no second copy).

    python3 scripts/zanatomy/rebuild_html_from_built.py BUILT.html -o build/q197/<page>/<name>.html \
        [--template viewer/zan_atlas.template.html] [--old-template OLD.html]

--old-template re-renders with the template the page was built from and requires a byte-identical page (the proof
that the extraction + wording path is lossless); the new page's data literals are always compared with the built
page's and the geo files with cmp semantics before the script reports success.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
import build_zan_atlas_viewer as B  # noqa: E402  (wording tables + render path of the builder)

LIT_RE = {
    "bin": re.compile(r'^window\.__ANATOMY_BIN__=(".*?");$', re.M | re.S),
    "files": re.compile(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", re.M),
    "manifest": re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M),
}
VARIANT_RE = re.compile(r'"variant":"([a-z_]+)"')


def extract_data(html: str) -> dict:
    """The three data literals of a built page, as raw text."""
    out = {}
    for k, rx in LIT_RE.items():
        m = list(rx.finditer(html))
        if len(m) != 1:
            raise SystemExit(f"built page: expected exactly one {k} literal, found {len(m)}")
        out[k] = m[0].group(1)
    return out


def variant_of(manifest_literal: str):
    m = VARIANT_RE.search(manifest_literal)   # top-level key of the manifest; no mesh record carries one
    return m.group(1) if m else None


def render(template: str, data: dict) -> str:
    """Same fill order and wording selection as build_zan_atlas_viewer.render_html()."""
    variant = variant_of(data["manifest"])
    if variant == "vhf":
        template = B.apply_vhf_wording(template)
    elif variant == "vhm":
        template = B.apply_vhf_wording(template, B.VHM_WORDING)
    elif variant == "native_female":
        template = B.apply_vhf_wording(template, B.NATIVE_FEMALE_WORDING)
    for ph in ("__MANIFEST_JSON__", "__BIN_FILES_JSON__", "__BIN_B64__"):
        if template.count(ph) != 1:
            raise SystemExit(f"template: placeholder {ph} must occur exactly once")
    # str.replace with a callable-free literal would be fine (the builder does the same); a lambda keeps backslashes verbatim
    html = template.replace("__MANIFEST_JSON__", data["manifest"], 1)
    html = html.replace("__BIN_FILES_JSON__", data["files"], 1)
    html = html.replace('"__BIN_B64__"', data["bin"], 1)
    return html


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("built", help="existing built page (its geo files are read from the same directory)")
    ap.add_argument("-o", "--out", required=True, help="output html (new directory; geo files are copied next to it)")
    ap.add_argument("--template", default=str(REPO / "viewer" / "zan_atlas.template.html"))
    ap.add_argument("--old-template", default=None, help="re-render with this template and require a byte-identical page")
    args = ap.parse_args(argv)

    built = Path(args.built).resolve()
    out = Path(args.out).resolve()
    if out.parent.resolve() == built.parent.resolve():
        raise SystemExit("refusing to write into the directory of the built page")
    old_html = built.read_text(encoding="utf-8")
    data = extract_data(old_html)

    if args.old_template:
        again = render(Path(args.old_template).read_text(encoding="utf-8"), data)
        if again != old_html:
            raise SystemExit("old-template re-render differs from the built page -- extraction/wording path is not lossless")
        print("old template re-render: byte-identical to the built page")

    new_html = render(Path(args.template).read_text(encoding="utf-8"), data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new_html, encoding="utf-8")

    new_data = extract_data(new_html)
    for k in data:
        if new_data[k] != data[k]:
            raise SystemExit(f"data literal {k} changed")
    import json
    files = json.loads(data["files"])
    for f in files:
        src, dst = built.parent / f["path"], out.parent / f["path"]
        shutil.copyfile(src, dst)
        if sha(src) != sha(dst) or dst.stat().st_size != src.stat().st_size:
            raise SystemExit(f"geo file {f['path']} differs after copy")
    print(f"wrote {out} ({len(new_html) / 1e6:.2f} MB, variant={variant_of(data['manifest'])}); "
          f"data literals identical; {len(files)} geo file(s) copied byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
