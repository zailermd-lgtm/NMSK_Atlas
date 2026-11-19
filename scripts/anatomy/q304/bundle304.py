#!/usr/bin/env python3
"""Q304: rebuild an own-page viewer BUNDLE from a built Imaging page, so structures can be added to the CURRENT page.

    python3 scripts/anatomy/q304/bundle304.py own_m own_f [--src build/q303] [--out /dev/shm/q304/bundle]

WHY THIS EXISTS. Q299 recorded that the two Imaging pages could not be touched because "their geometry comes from
the bundle builder and only build/q293/bundle_own_* is on disk, which predates the Q295 fat additions, so it needs
that chain re-run". It does not. `scripts/build_viewer_html.py --bundle DIR --external-bin` writes the bundle's
`bundle.json` verbatim into the page's `<script id="bundle-json">` (with only `</` escaped to `<\\/`, which a literal
"</script>" would otherwise end the element on) and the bundle's `bundle.bin` as the sibling `<stem>_geo_NN.txt`
files, base64 of consecutive 6 MB chunks. Both directions are lossless, so the bundle of the page that ships IS
recoverable from the page that ships -- and the recovery is PROVED rather than assumed: `verify` re-renders the page
from the recovered bundle with the same builder and requires every geo file and the `bundle-json` block to come out
byte-identical to the page it was recovered from.
"""
from __future__ import annotations

import argparse, base64, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

DIR = {"own_m": ("viewer_m_hr", "atlas_viewer_male.html"), "own_f": ("viewer_f_hr", "atlas_viewer_female.html")}
BLOCK = re.compile(r'<script id="bundle-json" type="application/json">(.*?)</script>', re.S)


def recover(page_dir: Path, stem_html: str, out: Path):
    h = (page_dir / stem_html).read_text(encoding="utf-8")
    payload = BLOCK.search(h).group(1)
    j = json.loads(payload.replace("<\\/", "</"))
    stem = stem_html[:-5]
    geo = sorted(page_dir.glob(f"{stem}_geo_*.txt"))
    raw = b"".join(base64.b64decode(p.read_text(encoding="ascii")) for p in geo)
    want = sum(int(e["nv"]) * 6 + int(e["nf"]) * 6 for e in j["structures"])
    assert len(raw) == want, f"{page_dir}: geometry {len(raw)} bytes, the manifest wants {want}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "bundle.json").write_text(payload.replace("<\\/", "</"), encoding="utf-8")
    (out / "bundle.bin").write_bytes(raw)
    (out / "bundle.b64").write_text(base64.b64encode(raw).decode("ascii"), encoding="ascii")
    for p in page_dir.glob("clinical_*"):
        (out / p.name).write_bytes(p.read_bytes())
    return dict(structures=len(j["structures"]), bytes=len(raw), geo_files=len(geo),
                sha256=hashlib.sha256(raw).hexdigest()[:16])


def verify(key, src, out):
    """re-render the page from the recovered bundle and require byte-identical geometry files + bundle-json block"""
    import subprocess
    dn, hn = DIR[key]
    page = REPO / src / dn
    bdir = Path(out) / f"bundle_{key}"
    info = recover(page, hn, bdir)
    chk = Path(out) / f"check_{key}"
    chk.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir),
                        "-o", str(chk / hn), "--external-bin"], capture_output=True, text=True, cwd=REPO)
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    stem = hn[:-5]
    same_geo, bad = True, []
    a = sorted(page.glob(f"{stem}_geo_*.txt")); b = sorted(chk.glob(f"{stem}_geo_*.txt"))
    if [p.name for p in a] != [p.name for p in b]:
        same_geo = False; bad.append(f"geo file names differ: {[p.name for p in a]} vs {[p.name for p in b]}")
    for x, y in zip(a, b):
        if x.read_bytes() != y.read_bytes():
            same_geo = False; bad.append(f"{x.name} differs")
    ba = BLOCK.search((page / hn).read_text(encoding="utf-8")).group(0)
    bb = BLOCK.search((chk / hn).read_text(encoding="utf-8")).group(0)
    same_json = ba == bb
    print(f"{key}: {info['structures']} structures, {info['bytes']} geometry bytes in {info['geo_files']} files; "
          f"geo byte-identical {same_geo}; bundle-json block byte-identical {same_json}"
          + ("" if not bad else " | " + "; ".join(bad[:4])), flush=True)
    return same_geo and same_json, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--src", default="build/q303")
    ap.add_argument("--out", default="/dev/shm/q304/bundle")
    a = ap.parse_args()
    ok = True
    rep = {}
    for key in (a.keys or list(DIR)):
        good, info = verify(key, a.src, a.out)
        rep[key] = dict(ok=good, **info)
        ok &= good
    p = REPO / "data/derived/Q304_bundle_recovery.json"
    p.write_text(json.dumps(dict(src=a.src, pages=rep), indent=1), encoding="utf-8")
    print("->", p, "| all byte-identical:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
