"""Q201 post-build SCOPE TRIM (byte level, no geometry is recomputed).

Same idea as scripts/zanatomy/q199_scope_trim.py, for the male page: nothing OUTSIDE the elbow / forearm / wrist / hand scope may differ from the Q195 page.  After the full build every structure
that is not (a) one of the six elbow bones, (b) a skin patch (the seam welds of the whole skin are part of Q201), (c) a structure the hook moved that is in scope (`q201_refine.make_scope`) is
put back to its Q195 mesh record (vertices, indices, bounding box, card note) byte for byte -- this also removes the sub-millimetre non-reproducibility of the upstream gap-closure scene
(Q192 / Q199 finding).  The geo files are re-packed in the builder's own layout (`build_zan_atlas_viewer.pack_mesh` offsets, `split_blob`) and the page re-rendered with the builder's `render_html`.

    python3 scripts/zanatomy/q201_scope_trim.py --built build/viewer_zan_vhm_q201 --baseline build/q197/viewer_zan_male_fitted --dump after_q201.npz
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
import build_zan_atlas_viewer as B  # noqa: E402
from scripts.zanatomy import body_ctx  # noqa: E402

body_ctx.configure("vhm")
from scripts.zanatomy import q201_refine as R  # noqa: E402
from scripts.zanatomy import q190_metrics as Mx  # noqa: E402

STEM = "atlas_viewer_zan_male_fitted"


def load_page(d: Path):
    html = (d / f"{STEM}.html").read_text(encoding="utf-8")
    i = html.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    files = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);\s*window\.__ANATOMY_MANIFEST__=", html, re.S).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    return man, blob


def keep_set(rep: dict, dump: str, regions: dict) -> set:
    """ids that may differ from the Q195 page: moved bones, skin patches the weld touched, moved structures that are in scope"""
    dm = Mx.load_dump(dump)
    by = {d["id"]: d for d in dm}
    raw = {i: d["r"] for i, d in by.items()}
    wcs, jcs, hcs = {}, {}, {}
    for side in "lr":
        wcs[side] = np.asarray(rep["chain"][side]["wrist_centre_raw"], float)
        jcs[side], hcs[side] = R.zone_centres(by, raw, side)
    scope = R.make_scope(jcs, wcs, hcs)
    keep = {k for v in rep["skin_seams"].values() for k in v["moved"]} | set(rep["bones"])
    for i in rep["moved_ids"]:
        side = "l" if (i.endswith("_l") or "_l_" in i) else ("r" if (i.endswith("_r") or "_r_" in i) else None)
        if side is None:
            continue
        if scope(side, i, raw[i], regions.get(i), jcs[side], None):
            keep.add(i)
    return keep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--built", default=str(REPO / "build" / "viewer_zan_vhm_q201"))
    ap.add_argument("--baseline", default=str(REPO / "build" / "q197" / "viewer_zan_male_fitted"))
    ap.add_argument("--dump", required=True, help="the --q201-dump-after npz of the build (raw Z source vertices)")
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q201_zan_vhm_q201_build.json"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    regions = json.loads(body_ctx.REGION_REPORT.read_text())["region_of_structure"]
    built, base = Path(a.built), Path(a.baseline)
    rep_all = json.loads(Path(a.report).read_text())
    rep = rep_all["q201"]
    keep = keep_set(rep, a.dump, regions)
    man, blob = load_page(built)
    man0, blob0 = load_page(base)
    e0 = {m["id"]: m for m in man0["meshes"]}
    revert = [m["id"] for m in man["meshes"] if m["id"] not in keep]
    differing = [i for i in revert if (lambda s, t: blob[s["vo"]: s["vo"] + s["vc"] * 6] != blob0[t["vo"]: t["vo"] + t["vc"] * 6] or s.get("rec") != t.get("rec") or s.get("min") != t.get("min"))(
        {m["id"]: m for m in man["meshes"]}[i], e0[i])]
    outside_moved = sorted(set(rep["moved_ids"]) - keep)
    print(f"{len(keep)} ids may differ; {len(revert)} structures are set to the Q195 record, {len(differing)} of them differed (hook-moved out of scope: {len(outside_moved)}, build noise: {len(differing) - len(outside_moved)})")
    if outside_moved:
        print("  hook-moved, out of scope: " + ", ".join(outside_moved))
    if a.dry_run:
        return 0
    revert = set(revert)
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        src, sb = (e0[m["id"]], blob0) if m["id"] in revert else (m, blob)
        pos = sb[src["vo"]: src["vo"] + src["vc"] * 6]
        idx = sb[src["io"]: src["io"] + src["ic"] * 6]
        n = dict(src)
        n["vo"], n["io"] = off, off + len(pos)
        meshes.append({k: n[k] for k in src})
        chunks += [pos, idx]
        off += len(pos) + len(idx)
    new_blob = b"".join(chunks)
    man2 = dict(man)
    man2["meshes"] = meshes
    tmp = built.parent / (built.name + "_trim_tmp")
    tmp.mkdir(exist_ok=True)
    bin_files = []
    for name, chunk in B.split_blob(new_blob, STEM):
        (tmp / name).write_text(base64.b64encode(chunk).decode("ascii"), encoding="ascii")
        bin_files.append({"path": name, "bytes": len(chunk), "enc": "base64"})
    (tmp / f"{STEM}.html").write_text(B.render_html(man2, new_blob, bin_files), encoding="utf-8")
    for f in built.glob(f"{STEM}*"):
        f.unlink()
    for f in tmp.iterdir():
        shutil.move(str(f), str(built / f.name))
    tmp.rmdir()
    rep["moved_ids"] = sorted(set(rep["moved_ids"]) & keep)
    rep["reverted_out_of_scope_to_q195"] = {"ids_hook_moved_out_of_scope": outside_moved, "structures_set_to_q195_record": len(revert), "structures_that_differed": len(differing),
                                            "rule": "scripts/zanatomy/q201_refine.make_scope (+ the six elbow bones and every skin patch the seam weld moved)",
                                            "tool": "scripts/zanatomy/q201_scope_trim.py (byte-level, after the last full build)"}
    Path(a.report).write_text(json.dumps(rep_all, indent=1, default=float))
    print("trimmed page written:", built, "| blob", len(blob), "->", len(new_blob), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
