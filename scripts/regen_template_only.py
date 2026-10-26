#!/usr/bin/env python3
"""Q271: the "template-only regen" of the six viewer pages as ONE command (no geometry recomputed), with the verification built in.

Since Q262 every UI round rebuilt the pages by chaining eight scripts by hand, and Q270 found that one of them (set_titles) had silently
dropped out of the chain between Q264 and Q268. This script runs the whole chain, in the established order, with the established flags:

    scripts/regen_cut_q218.sh <page>                 current template + the source page's own data literals, geo files byte for byte, siblings copied
    scripts/clinical/stage_clinical_files.py --ultrasound   current clinical/imaging_tool.js + ultrasound_tool.js (+ tissue tables), pasted into the page
    scripts/set_titles_q231.py                       the unified <title> / h1 / h2 names (the builders still write the raw wording)
    scripts/anatomy/q236/make_abbrevs.py --inject    abbreviation table   (committed data, no recompute)
    scripts/anatomy/q240/make_calibre.py --inject    calibre table        (committed data, no recompute)
    scripts/anatomy/q241/make_pose_rig.py --inject   pose rig             (committed data, no recompute)
    scripts/anatomy/q284/build_moments.py --inject   moment arms          (committed data, no recompute)
    scripts/anatomy/q237/build_sidecar.py            symmetry_q237.json
    scripts/anatomy/q256/build_plexus_sidecar.py     plexus_groups.json
    index.html = the page

and then VERIFIES the output against a reference page dir (default: the source dir, i.e. the previous build; `--ref` a dir of downloaded
live pages): every `<script id="nmsk-*">` block, the own pages' `bundle-json` / `bundle-b64` blocks and the Z pages' `window.__ANATOMY_*__`
literals must be byte-identical (the reference page may carry the artifact service's document skeleton, it is removed first); every sibling
file (geo txt, clinical_*, parts_data.json, plexus_groups.json, symmetry_q237.json) must be byte-identical unless named in `--expect-changed`;
the page's <title> / h1 must carry the Q231 unified name; index.html must equal the page. Also checks that no tracked data/ file changed
(the make_abbrevs / make_calibre default actions rebuild tracked tables -- the Q264 / Q267 `--help` accident). Exit 1 with a diff summary otherwise.

    python3 scripts/regen_template_only.py all --out /dev/shm/q271                              # sources build/q265, reference = the sources
    python3 scripts/regen_template_only.py base_m own_f --src build/q265 --out /dev/shm/q271 --ref /path/to/live --expect-changed index.html
    python3 scripts/regen_template_only.py all --out /dev/shm/q271 --ref /path/to/live --verify-only   # compare an existing output, no build

PAGE = own_m own_f zan_m zan_f base_f base_m | all.  --out must be under /dev/shm unless --allow-disk is given (the disk has been in a crisis
band for many rounds).  --src ROOT holds <page dir>/ per page (the regen_cut_q218 layout: viewer_m_hr, viewer_f_hr, viewer_zan_vhm,
viewer_zan_female, viewer_base_female, viewer_zan_atlas); --ref ROOT likewise.  --expect-changed takes sibling names (comma or repeat);
`index.html` there means "the page's non-data lines may differ"; a block id (`nmsk-imaging-inline`, the pasted clinical code) may be named too.  PARTS_SIDECAR=0 in the environment is
passed through to regen_cut_q218.sh (copy the source's parts_data.json instead of rebuilding it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from platform_wrap import unwrap  # noqa: E402
import rebuild_html_from_built as rz  # noqa: E402  (the Z pages' data-literal regexes)
import set_titles_q231 as titles  # noqa: E402

PAGES = ["own_m", "own_f", "zan_m", "zan_f", "base_f", "base_m"]
DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "zan_m": "viewer_zan_vhm", "zan_f": "viewer_zan_female",
       "base_f": "viewer_base_female", "base_m": "viewer_zan_atlas"}
SYM_KEY = {"own_m": "own_m", "own_f": "own_f", "zan_m": "comb_m", "zan_f": "comb_f", "base_f": "base_f", "base_m": "base_m"}  # q237 core.PAGES keys
DEFAULT_SRC = "build/q265"
BLOCK_RE = re.compile(r'<script[^>]*\bid="(nmsk-[^"]+|bundle-json|bundle-b64)"[^>]*>.*?</script>', re.S)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def run(cmd, env=None):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=REPO, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = r.stdout.strip().splitlines()[-3:]
    for ln in tail:
        print("   ", ln[:300])
    if r.returncode:
        sys.exit(f"step failed ({r.returncode}): {' '.join(str(c) for c in cmd)}\n{r.stdout[-3000:]}")


def page_html(d: Path) -> Path:
    c = sorted(d.glob("atlas_viewer*.html"))
    if len(c) != 1:
        sys.exit(f"{d}: expected one atlas_viewer*.html, found {len(c)}")
    return c[0]


def tracked_data_status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--", "data"], cwd=REPO, stdout=subprocess.PIPE, text=True).stdout


def build(p: str, src_root: Path, out: Path):
    src = src_root / DIR[p]
    if not src.is_dir():
        sys.exit(f"{p}: source dir {src} missing")
    dst = out / DIR[p]
    before = tracked_data_status()
    env = {"Q218_OUT": str(out), f"SRC_{p}": str(src)}
    if os.environ.get("PARTS_SIDECAR"):
        env["PARTS_SIDECAR"] = os.environ["PARTS_SIDECAR"]
    run(["bash", "scripts/regen_cut_q218.sh", p], env)
    run(["python3", "scripts/clinical/stage_clinical_files.py", "--ultrasound", str(dst)])
    run(["python3", "scripts/set_titles_q231.py", str(dst)])
    run(["python3", "scripts/anatomy/q236/make_abbrevs.py", "--inject", str(dst)])
    run(["python3", "scripts/anatomy/q240/make_calibre.py", "--inject", str(dst)])
    run(["python3", "scripts/anatomy/q241/make_pose_rig.py", "--inject", str(dst)])
    run(["python3", "scripts/anatomy/q284/build_moments.py", "--inject", str(dst)])
    html = page_html(dst)
    run(["python3", "scripts/anatomy/q237/build_sidecar.py", SYM_KEY[p], str(dst), "-o", str(dst / "symmetry_q237.json")])
    run(["python3", "scripts/anatomy/q256/build_plexus_sidecar.py", "--html", str(html), "-o", str(dst / "plexus_groups.json")])
    (dst / "index.html").write_bytes(html.read_bytes())
    after = tracked_data_status()
    if after != before:
        sys.exit(f"{p}: tracked data/ files changed during the build (a default action rebuilt a committed table?):\n{after}")


def blocks(html: str) -> dict[str, str]:
    out = {m.group(1): m.group(0) for m in BLOCK_RE.finditer(html)}
    for k, rx in rz.LIT_RE.items():  # Z pages: window.__ANATOMY_BIN__ / _FILES__ / _MANIFEST__ (absent on own pages)
        m = rx.search(html)
        if m:
            out["__ANATOMY_" + k] = m.group(0)
    return out


def only_generated_differs(a: Path, b: Path) -> bool:
    try:
        da, db = json.loads(a.read_text()), json.loads(b.read_text())
    except Exception:
        return False
    if not (isinstance(da, dict) and isinstance(db, dict)):
        return False
    da.pop("generated", None); db.pop("generated", None)
    return da == db


def verify(p: str, out: Path, ref_root: Path, expect: set[str]) -> list[str]:
    d, r = out / DIR[p], ref_root / DIR[p]
    bad = []
    if not r.is_dir():
        return [f"reference dir {r} missing"]
    html = page_html(d)
    new = html.read_text(encoding="utf-8")
    if (d / "index.html").read_bytes() != html.read_bytes():
        bad.append("index.html != " + html.name)
    name = titles.PREFIX + titles.NAMES[html.name]
    if f"<title>{name}</title>" not in new:
        bad.append(f"<title> is not '{name}'")
    if not re.search(r"<h1[^>]*>" + re.escape(name) + r"</h1>", new):
        bad.append(f"h1 is not '{name}'")
    ref_page = r / "index.html" if (r / "index.html").exists() else page_html(r)
    old = unwrap(ref_page.read_text(encoding="utf-8"))
    bn, bo = blocks(new), blocks(old)
    for k in sorted(set(bn) | set(bo)):
        if k in expect:   # e.g. nmsk-imaging-inline / nmsk-ultrasound-inline, the pasted clinical code, in a round that changed it
            continue
        if k not in bn:
            bad.append(f"data block {k}: only in the reference page")
        elif k not in bo:
            bad.append(f"data block {k}: only in the new page")
        elif bn[k] != bo[k]:
            bad.append(f"data block {k}: differs ({len(bo[k])} -> {len(bn[k])} bytes)")
    if "index.html" not in expect and new != old:
        bad.append("page html differs outside the data blocks (name it in --expect-changed if that is this round's change)")
    sib = lambda root: {f.name for f in root.iterdir() if f.is_file() and f.name != "index.html" and not f.name.endswith(".html")}  # geo txt + json + js
    ref_sib, new_sib = sib(r), sib(d)
    for n in sorted(ref_sib | new_sib):
        if n in expect:
            continue
        if n not in new_sib:
            bad.append(f"sibling {n}: only in the reference")
        elif n not in ref_sib:
            bad.append(f"sibling {n}: only in the new output")
        elif sha(d / n) != sha(r / n):
            hint = " (only the 'generated' date differs)" if only_generated_differs(d / n, r / n) else ""
            bad.append(f"sibling {n}: differs ({(r / n).stat().st_size} -> {(d / n).stat().st_size} bytes){hint}")
    n_blocks = len(bn)
    print(f"{p} ({DIR[p]}): {n_blocks} data blocks, {len(ref_sib)} reference siblings checked" + (f", expected-changed: {sorted(expect)}" if expect else ""))
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pages", nargs="+", help="own_m own_f zan_m zan_f base_f base_m | all")
    ap.add_argument("--src", default=DEFAULT_SRC, help=f"root of the source page dirs (default {DEFAULT_SRC})")
    ap.add_argument("--out", required=True, help="output root (must be under /dev/shm unless --allow-disk)")
    ap.add_argument("--ref", help="root of the reference page dirs to verify against (default: --src)")
    ap.add_argument("--expect-changed", action="append", default=[], help="sibling names / block ids allowed to differ (comma-separated or repeated); index.html = the page's non-data lines")
    ap.add_argument("--allow-disk", action="store_true")
    ap.add_argument("--verify-only", action="store_true", help="skip the build, verify an existing --out")
    a = ap.parse_args(argv)
    pages = PAGES if a.pages == ["all"] else a.pages
    for p in pages:
        if p not in DIR:
            ap.error(f"unknown page '{p}' ({' '.join(PAGES)} | all)")
    out = Path(a.out).resolve()
    if not a.allow_disk and not str(out).startswith("/dev/shm/"):
        ap.error(f"--out {out} is not under /dev/shm (pass --allow-disk to build on disk)")
    src_root = (REPO / a.src).resolve() if not Path(a.src).is_absolute() else Path(a.src)
    ref_root = Path(a.ref).resolve() if a.ref else src_root
    expect = {x.strip() for v in a.expect_changed for x in v.split(",") if x.strip()}
    if not a.verify_only:
        for p in pages:
            build(p, src_root, out)
    problems = {}
    for p in pages:
        bad = verify(p, out, ref_root, expect)
        if bad:
            problems[p] = bad
    for p, bad in problems.items():
        print(f"FAIL {p} ({DIR[p]}) vs {ref_root / DIR[p]}:")
        for b in bad:
            print("   ", b)
    if problems:
        print(f"REGEN_TEMPLATE_ONLY_FAIL {len(problems)}/{len(pages)} pages")
        return 1
    print(f"REGEN_TEMPLATE_ONLY_OK {len(pages)} pages identical to {ref_root} (data blocks, siblings, Q231 titles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
