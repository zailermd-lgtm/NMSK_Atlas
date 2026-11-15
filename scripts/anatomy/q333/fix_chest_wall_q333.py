#!/usr/bin/env python3
"""Q333: Base · Female, right-side (+X) anterior chest -- the costal cartilages show through the pectoralis major.

    python3 scripts/anatomy/q333/fix_chest_wall_q333.py --page-dir DIR             # dry run: measure, report, write nothing
    python3 scripts/anatomy/q333/fix_chest_wall_q333.py --page-dir DIR --write     # and write the page files in DIR

What is wrong (measured on the page, data/derived/Q333_chest_wall_report.json): Q292 placed her CT breast onto the Base chest
wall and then thinned the Z-Anatomy layers under it (scripts/anatomy/q292/build_q292.py, `compress_under`: every vertex the breast
entered moved toward the wall to 1 mm behind the breast, never closer than 0.5 mm to the wall). The breast was first to be pushed
4 mm out of the Base chest wall (WALL_GAP, "keeping 4 mm for the pectoral layer"). On the right that push did not finish: Q292's
own report records `out_of_rib_cage_2: still_violating 236, max_inside_mm 5.66` (left: 0). The cause is in lib292.push_dir: its
smoothing pass re-imposes only the vertices violating in the CURRENT round, so a vertex pushed out in round 1 decays back by
0.85^8 per later round and re-enters the wall. With the right breast still up to 5.7 mm inside the wall, the thinning had nowhere
to put the pectoral layer: the sternocostal head ended 150 vertices inside the breast and with its anterior surface behind the
costal cartilages over ~11 cm2 of the lower medial chest (left side: under 1 cm2; Base · Male: ~0). On the page that is the
pale-blue cartilage / intercostal-membrane plates and red gaps seen through the right breast region.

The repair, Q292's own rule finished with its own parameters (nothing invented, nothing sculpted):
  1. her breast (breast_ct_<side>) is pushed out of the Base chest wall to Q292's WALL_GAP (4 mm) along the wall's outward
     gradient, by push_dir_keep -- lib292.push_dir with the one fix above (a vertex once required to move keeps its requirement);
     the fibroglandular mesh is carried with it (lib292.carry) and kept inside the breast (lib292.push_out, 0.5 mm, as Q292);
  2. on each listed superficial layer of that side, the vertices within 30 mm of the breast that lie inside the chest wall are
     pushed out to Q292's floor (0.5 mm, lib292.push_out; vertices farther from the breast locked), then Q292's own
     lib292.compress_under is re-run against the corrected breast (1 mm behind it, never closer than 0.5 mm to the wall), and the
     floor is imposed once more where compress_under's smoothing drew vertices back into the wall (an anterior-surface-only
     variant of these pushes folded 0.6-0.9 % of the pectoralis / rectus faces and was dropped);
  3. a structure ships only if the front-view poke-through of the wall through it does not rise and the number of its vertices
     inside the breast does not rise; otherwise it keeps its bytes. Vertex count and topology never change (the pose rig only
     checks counts), nothing is added or deleted, every replaced file is first copied beside itself as `<name>.q333`
     (never overwriting an existing copy). The card text of each changed structure gets a Q333 sentence.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (REPO, REPO / "scripts" / "zanatomy", REPO / "scripts" / "anatomy" / "q292", REPO / "scripts" / "anatomy" / "q219"):
    sys.path.insert(0, str(p))
import build_zan_atlas_viewer as B  # noqa: E402  pack_mesh / split_blob (the builder's own layout)
import lib292 as L                  # noqa: E402  Q292's SDF / push_out / compress_under / carry / neighbour_matrix
from scripts.transfer.q213_inbone import flipped_pct, stretched_pct  # noqa: E402  Q213's triangle guards

STEM = "atlas_viewer_base_female"
OUT = REPO / "data/derived/Q333_chest_wall_report.json"
# Q292's own constants and selection (scripts/anatomy/q292/build_q292.py)
WALL_RE = re.compile(r'_rib_[lr]$|costal_cartilage|^sternum$|^zan_xiphoid|intercostal_(muscles|membrane)|lobe_of_.*lung|^zan_pleura$|transversus_thoracis')
WALL_GAP, FLOOR, LAYER_NEAR = 4.0, 0.5, 30.0
# superficial layers that lie ON the chest wall (the intercostal nerves / vessels that Q292 also touched live IN the wall: excluded)
LAYERS = ["zan_sternocostal_head_of_pectoralis_major_muscle_{s}", "zan_abdominal_part_of_pectoralis_major_muscle_{s}",
          "external_oblique_{s}", "rectus_abdominis_{s}", "serratus_anterior_{s}", "pectoral_fascia_{s}", "zan_pectoral_fascia_{s}",
          "zan_investing_abdominal_fascia_{s}"]
VIEW_WALL_RE = re.compile(r'costal_cartilage|_rib_[lr]$|intercostal_(muscles|membrane)|^sternum$|xiphoid')   # what shows from the front
LIT = {"files": re.compile(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", re.M),
       "manifest": re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)}


# ------------------------------------------------------------------ page I/O (as scripts/anatomy/q319/ship_q319.py)
def pages_of(d: Path):
    return [p for p in (d / f"{STEM}.html", d / "index.html") if p.exists()]


def read_page(d: Path):
    t = pages_of(d)[0].read_text(encoding="utf-8")
    man = json.loads(LIT["manifest"].search(t).group(1))
    files = json.loads(LIT["files"].search(t).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    return man, blob, files


def dec(m, blob):
    q = np.frombuffer(blob, np.uint16, m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
    f = np.frombuffer(blob, np.uint16, m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
    return np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"]), f


def ser_manifest(man):
    return json.dumps(man, separators=(",", ":")).replace("</", "<\\/")


def repack(man, blob, replace):
    """ship_q319.repack_bytes without additions: untouched meshes keep their own bytes"""
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        n = dict(m)
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n.update(fields); n["rec"] = rec
            chunks.append(packed); off += len(packed)
        else:
            pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]; idx = blob[m["io"]: m["io"] + m["ic"] * 6]
            n["vo"], n["io"] = off, off + len(pos)
            chunks += [pos, idx]; off += len(pos) + len(idx)
        meshes.append(n)
    man2 = dict(man); man2["meshes"] = meshes
    return man2, b"".join(chunks)


def write_page(d: Path, man_old, man_new, blob_new, old_files):
    pages = pages_of(d)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():   # the builder's serialisation, proven on the unmodified page before anything is written
        assert LIT["manifest"].search(t).group(1) == ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, STEM)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q333")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q333")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + ser_manifest(man_new) + ";", t, count=1)
        t2 = LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


# ------------------------------------------------------------------ geometry
def push_dir_keep(V, F, sdf, dirfn, margin, max_disp, rounds=6, smooth_iters=8, step=0.5, decay=0.85):
    """lib292.push_dir with one fix: `fixed` / `req` accumulate over the rounds, so a vertex pushed out in an earlier round keeps
    its displacement instead of decaying back into the wall during the later rounds' smoothing (Q292's right-breast failure)."""
    A, deg = L.neighbour_matrix(len(V), F)
    D = np.zeros_like(V); fixed = np.zeros(len(V), bool); req = np.zeros_like(V)
    for r in range(rounds):
        P = V + D; s = sdf.at(P); viol = np.nonzero(s > -margin)[0]
        if not len(viol):
            break
        dv = dirfn(P[viol]); need = np.zeros(len(viol))
        for _ in range(int(max_disp / step) + 1):
            go = sdf.at(P[viol] + dv * need[:, None]) > -margin
            if not go.any():
                break
            need[go] += step
        D[viol] += dv * need[:, None]; fixed[viol] = True; req[fixed] = D[fixed]
        for _ in range(smooth_iters):
            Dn = (A @ D) / deg[:, None]
            D = np.where(fixed[:, None], np.where((np.linalg.norm(Dn, axis=1) > np.linalg.norm(req, axis=1))[:, None], Dn, req), decay * Dn)
        n = np.linalg.norm(D, axis=1); big = n > max_disp; D[big] *= (max_disp / n[big])[:, None]
    P = V + D; s = sdf.at(P); n = np.linalg.norm(D, axis=1)
    return P, dict(rounds=r + 1, still_violating=int((s > -margin + 0.25).sum()), max_inside_mm=round(float(s.max()), 2),
                   moved_gt1mm=int((n > 1).sum()), disp_max_mm=round(float(n.max()), 2), disp_p95_mm=round(float(np.percentile(n, 95)), 2))


def front_grid(meshes, fn=max, G=2.0):
    """2 mm front-view depth map (+Z is anterior on this page): the front-most (max) or back-most (min) z per column"""
    H = {}
    for v, f in meshes:
        t = trimesh.Trimesh(v, f, process=False)
        p, _ = trimesh.sample.sample_surface(t, max(20000, int(t.area / 0.5)), seed=1)
        for a, b, z in zip(np.floor(p[:, 0] / G).astype(int), np.floor(p[:, 1] / G).astype(int), p[:, 2]):
            H[(a, b)] = fn(H.get((a, b), z), z)
    return H


def poke_px(Hs, Hw, sg, tol=1.0, G=2.0):
    """columns on this side (|x| > 15 mm, y 330-540) where the wall's front is more than `tol` mm in front of the structure's front"""
    return int(sum(1 for k, z in Hs.items() if sg * k[0] * G > 15 and 330 / G < k[1] < 540 / G and k in Hw and Hw[k] > z + tol))


def badge_add(rec, text):
    rec = json.loads(json.dumps(rec or {}))
    b = rec.get("procedural_badge") or ""
    rec["procedural_badge"] = (b + (" " if b else "") + text).strip()
    return rec


def run_side(s, man, blob, log):
    sg = -1 if s == "l" else 1
    ms = {m["id"]: m for m in man["meshes"]}
    G = {k: dec(ms[k], blob) for k in ms if WALL_RE.search(k)}
    rep = {"side": s}
    out = {}
    # ---- 1. her breast out of the Base chest wall to WALL_GAP
    bk, gk = f"breast_ct_{s}", f"breast_fgt_ct_{s}"
    V, F = dec(ms[bk], blob); FV, FF = dec(ms[gk], blob)
    lo, hi = V.min(0) - 75, V.max(0) + 75
    sw = L.SDF([G[k] for k in G if (G[k][0].max(0) > lo).all() and (G[k][0].min(0) < hi).all()], lo, hi, fill=True)
    d0 = sw.at(V)
    rep["breast_before"] = dict(vertices=len(V), in_wall_gt0_5mm=int((d0 > 0.5).sum()), within_wall_gap=int((d0 > -WALL_GAP + 0.25).sum()),
                                max_inside_mm=round(float(d0.max()), 2), volume_cm3=round(L.mesh_volume(V, F), 1))
    if rep["breast_before"]["within_wall_gap"]:
        V1, R = push_dir_keep(V, F, sw, lambda Q: -sw.grad(Q), margin=WALL_GAP, max_disp=15)
        FV1 = L.carry(V, V1, FV)
        sbi = L.SDF([(V1, F)], V1.min(0) - 25, V1.max(0) + 25); sbi.d = -sbi.d; sbi.g = -sbi.g
        FV1, RF = L.push_out(FV1, FF, sbi, margin=0.5, max_disp=20)
        R.update(volume_after_cm3=round(L.mesh_volume(V1, F), 1), fgt_kept_inside=RF,
                 fgt_volume_cm3=[round(L.mesh_volume(FV, FF), 2), round(L.mesh_volume(FV1, FF), 2)])
        rep["breast_push"] = R
        out[bk] = (V1, F, f"Q333: pushed out of the Base chest wall to the 4 mm gap Q292 reserves for the pectoral layer, which Q292's own push "
                          f"had left unfinished on this side ({rep['breast_before']['within_wall_gap']} vertices inside that gap, up to "
                          f"{rep['breast_before']['max_inside_mm']} mm inside the wall): max move {R['disp_max_mm']} mm, p95 {R['disp_p95_mm']} mm, "
                          f"volume {rep['breast_before']['volume_cm3']} -> {R['volume_after_cm3']} cm3.")
        out[gk] = (FV1, FF, f"Q333: carried with her breast when it was pushed out of the Base chest wall (max move "
                            f"{round(float(np.linalg.norm(FV1 - FV, axis=1).max()), 2)} mm); kept inside the breast.")
        V = V1
        log(f"  {s}: breast pushed out of the wall: {R}")
    else:
        log(f"  {s}: breast already clear of the wall gap; not moved")
    # ---- 2. the superficial layers on that wall
    sb = L.SDF([(V, F)], lo, hi)
    sb_old = L.SDF([dec(ms[bk], blob)], lo, hi)
    tb = cKDTree(V)
    Hw = front_grid([dec(ms[k], blob) for k in ms if VIEW_WALL_RE.search(k) and (k.endswith("_" + s) or k == "sternum")])
    rep["layers"] = {}
    for tmpl in LAYERS:
        k = tmpl.format(s=s)
        if k not in ms:
            continue
        v, f = dec(ms[k], blob)
        dist, _ = tb.query(v)
        far = dist >= LAYER_NEAR                                       # only the part of the layer near her breast moves (Q292 touched only that)
        v1, i1 = L.push_out(v, f, sw, margin=FLOOR, max_disp=10, lock=far)
        v2, i2 = L.compress_under(v1, f, sb, sw)
        # compress_under's smoothing can draw a vertex back into the wall: impose the floor once more
        v2, i3 = L.push_out(v2, f, sw, margin=FLOOR, max_disp=10, lock=far) if ((sw.at(v2) > -FLOOR) & ~far).any() else (v2, None)
        hb, ha = front_grid([(v, f)]), front_grid([(v2, f)])
        r = dict(vertices_free=int((~far).sum()),
                 poke_through_px_before=poke_px(hb, Hw, sg), poke_through_px_after=poke_px(ha, Hw, sg),
                 inside_breast_before=int((sb_old.at(v) > 0.5).sum()), inside_breast_after=int((sb.at(v2) > 0.5).sum()),
                 disp_max_mm=round(float(np.linalg.norm(v2 - v, axis=1).max()), 2),
                 disp_p95_mm=round(float(np.percentile(np.linalg.norm(v2 - v, axis=1), 95)), 2),
                 volume_cm3=[round(L.mesh_volume(v, f), 2), round(L.mesh_volume(v2, f), 2)], push_out=i1, compress=i2, floor_again=i3)
        r.update(flipped_pct=round(flipped_pct(v, v2, f), 2), stretched_pct=[round(stretched_pct(v, v, f), 1), round(stretched_pct(v, v2, f), 1)])
        moved = r["disp_max_mm"] > 0.05
        ok = (moved and r["poke_through_px_after"] <= r["poke_through_px_before"] and r["inside_breast_after"] <= r["inside_breast_before"]
              and r["flipped_pct"] <= 0.5 and r["stretched_pct"][1] <= r["stretched_pct"][0] + 12.0)   # Q213's limits
        r["ships"] = bool(ok)
        rep["layers"][k] = r
        log(f"  {s}: {k}: poke {r['poke_through_px_before']} -> {r['poke_through_px_after']} px, in breast {r['inside_breast_before']} -> "
             f"{r['inside_breast_after']}, max move {r['disp_max_mm']} mm, flipped {r['flipped_pct']} %, stretched {r['stretched_pct']} -> {'SHIPS' if ok else 'kept'}")
        if ok:
            out[k] = (v2, f, f"Q333: the part of this layer that Q292's thinning had left behind the costal cartilages / ribs (seen through it "
                             f"from the front over {r['poke_through_px_before'] * 4} mm2) put back in front of the chest wall (Q292's 0.5 mm floor) "
                             f"and re-thinned under her corrected breast with Q292's own rule: max move {r['disp_max_mm']} mm, "
                             f"volume {r['volume_cm3'][0]} -> {r['volume_cm3'][1]} cm3.")
    return rep, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--side", action="append", choices=["l", "r"], help="default: r (the side with the defect)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir)
    man, blob, files = read_page(d)
    done = [m["id"] for m in man["meshes"] if "Q333:" in ((m.get("rec") or {}).get("procedural_badge") or "")]
    if done:
        print(f"Q333 already applied to this page ({len(done)} structures carry the Q333 note, e.g. {done[0]}); nothing done")
        return 0
    rep = {"schema": "nmsk.q333.chest_wall.v1", "round": "Q333", "generated": time.strftime("%Y-%m-%d"), "page_dir": str(d),
           "written": bool(a.write), "sides": {}}
    replace = {}
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    for s in (a.side or ["r"]):
        r, out = run_side(s, man, blob, print)
        rep["sides"][s] = r
        for k, (v, f, note) in out.items():
            replace[k] = (v, f, badge_add(recs[k], note))
    rep["geometry_changed"] = sorted(replace)
    man2, blob2 = repack(man, blob, replace)
    for m0, m1 in zip(man["meshes"], man2["meshes"]):      # vertex / triangle counts never change (pose rig contract)
        assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
    assert len(blob2) == len(blob)
    if a.write:
        rep["files_changed"] = write_page(d, man, man2, blob2, files)
        print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *.q333)")
    Path(a.json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(f"Q333 {'WRITTEN' if a.write else 'DRY RUN'}: {len(replace)} structures changed -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
