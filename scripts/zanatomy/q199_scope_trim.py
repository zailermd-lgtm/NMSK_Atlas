"""Q199 post-build SCOPE TRIM (byte level, no geometry is recomputed).

Why: the full build moved 50 structures that are outside the elbow scope -- trunk muscles / fascia / intercostals that only touch the scapula or clavicle, and RIGHT-side shoulder structures
(the right humerus does not move) -- because the origin / insertion pull and the gap closure also looked at the shoulder-girdle bones.  The owner asked for everything outside the arms to
stay identical to v12, and the three full builds of the task were used.  So: every structure the hook moved that is NOT in scope (`q199_elbow.in_scope`) is put back to its v12 mesh
record (vertices, indices, bounding box, card note) in the built page, byte for byte; the three geometry files are re-packed in the builder's own layout (`build_zan_atlas_viewer.pack_mesh`
offsets, `split_blob`) and the page re-rendered with the builder's `render_html`.  The scope rule is also in `q199_elbow.refine_side`, so a rebuild selects the same set.

    python3 scripts/zanatomy/q199_scope_trim.py --built build/viewer_zan_female_q199 --v12 build/viewer_zan_female --dump after_q199.npz
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
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
import build_zan_atlas_viewer as B  # noqa: E402
from scripts.zanatomy import q199_elbow as E  # noqa: E402
from scripts.zanatomy import q190_metrics as Mx  # noqa: E402

STEM = "atlas_viewer_zan_female"


def load_page(d: Path):
    html = (d / f"{STEM}.html").read_text(encoding="utf-8")
    i = html.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    files = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);\s*window\.__ANATOMY_MANIFEST__=", html, re.S).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    return man, blob


def revert_set(rep: dict, dump: str, regions: dict) -> tuple[list, dict]:
    """ids the hook moved that are out of scope (bones and the welded skin patches of the arm are always in scope)"""
    dm = Mx.load_dump(dump)
    by = {d["id"]: d for d in dm}
    raw = {i: d["r"] for i, d in by.items()}
    skin = {k for v in rep["skin_seams"].values() for k in v["moved"]}
    bones = {b for b, m in rep["bones"].items()}
    info = {}
    for side in "lr":
        s = "_" + side
        smp, sel, _, _ = E.joint_pairs(raw, side, by)
        jc = E.at(raw["humerus" + s], smp["humerus"])[sel].mean(0)
        info[side] = (jc, cKDTree(E.at(raw["humerus" + s], E.bary_samples(raw["humerus" + s], by["humerus" + s]["f"], 6000, seed=5))))
    out = []
    for i in rep["moved_ids"]:
        if i in skin or i in bones:
            continue
        side = "l" if (i.endswith("_l") or "_l_" in i) else ("r" if (i.endswith("_r") or "_r_" in i) else None)
        if side is None:
            out.append(i)
            continue
        jc, ht = info[side]
        if not E.in_scope(side, i, raw[i], regions.get(i), jc, ht, humerus_moved=(side == "l")):
            out.append(i)
    return sorted(out), {k: v for k, v in rep["structures"].items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--built", default=str(REPO / "build" / "viewer_zan_female_q199"))
    ap.add_argument("--v12", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--dump", required=True, help="the --q199-dump-after npz of the build (raw Z source vertices)")
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q199_zan_female_q199_build.json"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    built, v12 = Path(a.built), Path(a.v12)
    rep_all = json.loads(Path(a.report).read_text())
    rep = rep_all["q199"]
    revert, _ = revert_set(rep, a.dump, regions)
    print(f"{len(revert)} of {len(rep['moved_ids'])} moved ids are out of scope -> back to v12:")
    print("  " + ", ".join(revert))
    if a.dry_run:
        return 0
    man, blob = load_page(built)
    man12, blob12 = load_page(v12)
    e12 = {m["id"]: m for m in man12["meshes"]}
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        src, sb = (e12[m["id"]], blob12) if m["id"] in revert else (m, blob)
        pos = sb[src["vo"]: src["vo"] + src["vc"] * 6]
        idx = sb[src["io"]: src["io"] + src["ic"] * 6]
        n = dict(src)
        n["vo"], n["io"] = off, off + len(pos)
        # keep the key order of the builder's entries
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
    for f in built.glob("atlas_viewer_zan_female*"):
        f.unlink()
    for f in tmp.iterdir():
        shutil.move(str(f), str(built / f.name))
    tmp.rmdir()
    rep["moved_ids"] = sorted(set(rep["moved_ids"]) - set(revert))
    rep["reverted_out_of_scope_to_v12"] = {"ids": revert, "rule": "scripts/zanatomy/q199_elbow.in_scope", "tool": "scripts/zanatomy/q199_scope_trim.py (byte-level, after the third full build)"}
    Path(a.report).write_text(json.dumps(rep_all, indent=1, default=float))
    print("trimmed page written:", built, "| blob", len(blob), "->", len(new_blob), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
