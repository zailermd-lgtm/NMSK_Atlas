#!/usr/bin/env python3
"""Q218: re-render a BUILT own-viewer page (build_viewer_html.py --external-bin) with a newer viewer/atlas_viewer.template.html
WITHOUT recomputing geometry and WITHOUT needing the bundle.json/bundle.b64 it came from.

A built own page is (template, <title>, three data literals): the bundle-json script, the (empty, external-bin) bundle-b64 script
and `var BIN_FILES = [...]`. This takes the literals back out as raw text, copies the geo files byte for byte, keeps the page's own
<title> (the female page's "(VH female)") and fills the new template with the builder's own placeholder order.

    python3 scripts/rebuild_own_html_from_built.py BUILT.html -o build/q218/<page>/<name>.html \
        [--template viewer/atlas_viewer.template.html] [--old-template OLD.html]

--old-template re-renders with the template the page was built from and requires a byte-identical page (proof that the extraction is
lossless); the new page's literals are always compared with the built page's, the geo files with cmp semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import os
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from platform_wrap import unwrap  # noqa: E402  (a build dir restored from the published artifact carries the service's skeleton)
LIT_RE = {
    "json": re.compile(r'<script id="bundle-json" type="application/json">(.*?)</script>', re.S),
    "b64": re.compile(r'<script id="bundle-b64" type="text/plain">(.*?)</script>', re.S),
    "files": re.compile(r"^var BIN_FILES = (.*);$", re.M),
}
TITLE_RE = re.compile(r"<title>(.*?)</title>")
PH = {"json": "__BUNDLE_JSON__", "b64": "__BUNDLE_B64__", "files": "__BUNDLE_BIN_FILES__"}


def extract(html: str) -> dict:
    out = {}
    for k, rx in LIT_RE.items():
        m = rx.findall(html)
        if len(m) != 1:
            raise SystemExit(f"built page: expected exactly one {k} literal, found {len(m)}")
        out[k] = m[0]
    out["title"] = TITLE_RE.search(html).group(1)
    return out


def render(template: str, data: dict) -> str:
    for ph in PH.values():
        if template.count(ph) != 1:
            raise SystemExit(f"template: placeholder {ph} must occur exactly once")
    template = template.replace("<title>NMSK Atlas Viewer</title>", f"<title>{data['title']}</title>", 1)
    # same order as build_viewer_html.py (json, bin files, b64)
    return template.replace(PH["json"], data["json"]).replace(PH["files"], data["files"]).replace(PH["b64"], data["b64"])


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("built")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--template", default=str(Path(os.environ.get("NMSK_TEMPLATE_DIR", REPO / "viewer")) / "atlas_viewer.template.html"))   # Q237: NMSK_TEMPLATE_DIR = private template copies
    ap.add_argument("--old-template", default=None)
    a = ap.parse_args(argv)
    built, out = Path(a.built).resolve(), Path(a.out).resolve()
    if out.parent == built.parent:
        raise SystemExit("refusing to write into the directory of the built page")
    old = unwrap(built.read_text(encoding="utf-8"))
    data = extract(old)
    if a.old_template:
        if render(Path(a.old_template).read_text(encoding="utf-8"), data) != old:
            raise SystemExit("old-template re-render differs from the built page -- extraction is not lossless")
        print("old template re-render: byte-identical to the built page")
    new = render(Path(a.template).read_text(encoding="utf-8"), data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new, encoding="utf-8")
    nd = extract(new)
    for k in data:
        if nd[k] != data[k]:
            raise SystemExit(f"data literal {k} changed")
    files = json.loads(data["files"])
    for f in files:
        src, dst = built.parent / f["path"], out.parent / f["path"]
        shutil.copyfile(src, dst)
        if sha(src) != sha(dst) or src.stat().st_size != dst.stat().st_size:
            raise SystemExit(f"geo file {f['path']} differs after copy")
    print(f"wrote {out} ({len(new) / 1e6:.2f} MB); data literals identical; {len(files)} geo file(s) copied byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
