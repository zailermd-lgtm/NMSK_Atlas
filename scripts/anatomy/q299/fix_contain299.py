"""Q299 Part B fix: pull back inside the body the structures that the Q250 skin guard could not.

    python3 scripts/anatomy/q299/fix_contain299.py plan  [--src build/q297] [--tol 5]
    python3 scripts/anatomy/q299/fix_contain299.py build [--src build/q297] [--out /dev/shm/q299/pre]

WHY this is a fix and not a cosmetic nudge.  Q250 warped the Z-Anatomy body onto the Visible Human female's skeleton and
ran a skin guard that was meant to pull every vertex back inside the skin.  Its own report records what happened: 5,724
vertices pulled back, but "1,057 beyond 6 mm only counted: ambiguous nearest skin".  The guard could not decide inside
from outside, because the Z skin is ~250 OPEN patches with no closed envelope -- the same defect that made Q297 discard
a ray-parity containment test.  So the guard silently gave up on exactly the vertices that are furthest out, and the
external pudendal vessels of the groin ended up 21 mm in front of the skin of the mons pubis, where the owner saw them.
Q299 builds a body mask that passes validation (scripts/anatomy/q299/contain299.py) and re-runs the guard with it.

WHAT IS MOVED, AND WHAT IS NOT.  Nothing is sculpted and no vertex is invented: a vertex that lies outside the body mask
is moved to the nearest point of this page's own skin / outer-tissue surface and `INSET` mm further in along the same
line, and the displacement is spread over the mesh with a Gaussian of `SIGMA` mm so the mesh stays smooth (the same
kernel Q250 used).  Vertices already inside are not moved.
  * BONE is never moved.  A bone outside the skin is a registration residual or a limit of the subject's own
    segmentation (Q293 fingers, Q297 fingertips, her supine back); moving it would falsify the skeleton.
  * The OCULAR SURFACE is exempt: the cornea, iris, sclera and the chambers of the eyeball sit in the palpebral fissure
    and are genuinely not covered by skin -- the Z pages carry no conjunctiva or eyelid-margin mesh, so "outside the
    skin mask" is the correct answer there, not a defect.  (6 structures per Z page, 5.0-6.6 mm; Base M has no other
    offender at all, which is itself the control: the male page's external pudendal vessels end inside the external
    genital skin that the female pages no longer have.)
  * The two Imaging pages are not touched here: their geometry comes from a different builder, and their offenders
    (her merged finger label, three Q203 void-filling muscle pieces, the rule-based dorsal nerve of the penis) are
    reported in docs/OPEN_ITEMS_FOR_OWNER.md instead.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/zanatomy"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q237"))
import contain299 as CT  # noqa: E402
import pelvis_cards299 as PCARD  # noqa: E402
import core as C  # noqa: E402
from scripts.zanatomy import q205_pages as P5  # noqa: E402

ZKEYS = ["base_m", "base_f", "comb_m", "comb_f"]
DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas",
       "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
STEM = {"base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female",
        "comb_m": "atlas_viewer_zan_male_fitted", "comb_f": "atlas_viewer_zan_female"}
REPORT = REPO / "data/derived/Q299_containment_fix.json"
INSET, SIGMA, PASSES = 1.0, 8.0, 3
# mesh guard: refuse the move rather than damage the mesh.  (Q250 already accepts, and badges, 226 structures with
# > 2 % flipped triangles, so the bar here is set above that; nothing in Q299 trips it, which is the point of stating it.)
MAX_FLIPPED_FRAC, MAX_DIHEDRAL_CHANGE_DEG, MIN_CLOSED_VOL_CM3 = 0.03, 8.0, 0.01
OCULAR = ("cornea", "iris", "sclera", "chamber_of_eyeball", "lens_of_eye", "eyeball", "vitreous", "pupil",
          "ciliary", "choroid", "retina", "conjunctiva")


def exempt(sid, sys_):
    if sys_ == "bone":
        return "bone: a bone outside the skin is a registration residual or a limit of the subject's own segmentation; moving it would falsify the skeleton"
    if any(w in sid for w in OCULAR):
        return "ocular surface: the cornea / iris / sclera / chambers sit in the palpebral fissure and are genuinely not covered by skin; these pages carry no conjunctiva or eyelid-margin mesh"
    return None


def smooth_field(V, src, disp_src, sigma=SIGMA):
    """Spread the displacement of the moved vertices (`src` = their positions, `disp_src` = their own targets minus
    their positions, same length) over the whole mesh with a compactly supported Gaussian:
    D_i = (sum_j w_ij d_j / sum_j w_ij) * max_j w_ij,  w = exp(-r^2 / 2 sigma^2), r <= 3 sigma.
    The factor max_j w_ij makes the field decay to zero away from the moved vertices, so the rest of the mesh keeps
    its shape; at a moved vertex it is 1, so that vertex takes (almost exactly) the local average target, which is
    what keeps a tube a tube instead of collapsing its ring onto one skin point."""
    D = np.zeros_like(V)
    tree = cKDTree(src)
    lists = tree.query_ball_point(V, 3.0 * sigma, workers=-1)
    s2 = 2.0 * sigma * sigma
    for i, lst in enumerate(lists):
        if not lst:
            continue
        j = np.asarray(lst)
        r2 = ((src[j] - V[i]) ** 2).sum(1)
        w = np.exp(-r2 / s2)
        D[i] = (w[:, None] * disp_src[j]).sum(0) / w.sum() * float(w.max())
    return D


def pull_inside(V, F, g, body, skin_tree, bones=None, bone_tree=None):
    """One structure: pull every vertex outside the body mask back in.  Returns (V2, stats)."""
    V2 = V.astype(float).copy()
    moved_total = np.zeros(len(V), bool)
    hist = []
    for _ in range(PASSES):
        ins = g.inside(body, V2)
        out = np.nonzero(~ins)[0]
        if not len(out):
            break
        d, j = skin_tree.query(V2[out], workers=-1)
        q = skin_tree.data[j]
        u = q - V2[out]
        n = np.linalg.norm(u, axis=1)
        n[n < 1e-9] = 1e-9
        u = u / n[:, None]
        target = q + u * INSET
        disp_out = target - V2[out]
        V2 = V2 + smooth_field(V2, V2[out].copy(), disp_out)
        moved_total[out] = True
        hist.append(dict(n_outside=int(len(out)), max_out_mm=round(float(d.max()), 2)))
    # bone guard: pulling a structure IN must not push it into a bone. A vertex that ended up inside the (one-voxel
    # eroded) bone mask is moved back out to the nearest bone surface plus 0.3 mm.
    pushed = 0
    if bones and bone_tree is not None:
        lo, hi = V2.min(0), V2.max(0)
        hit = np.zeros(len(V2), bool)
        for b in bones:                                  # per-bone masks (contain299.BoneBox), never one global mask
            if (b.hi < lo).any() or (b.lo > hi).any():
                continue
            hit |= b.inside(V2)
        pen = np.nonzero(hit)[0]
        if len(pen):
            d, j = bone_tree.query(V2[pen], workers=-1)
            q = bone_tree.data[j]
            u = V2[pen] - q
            n = np.linalg.norm(u, axis=1); n[n < 1e-9] = 1e-9
            V2[pen] = q + (u / n[:, None]) * 0.3
            pushed = int(len(pen))
    ins = g.inside(body, V2)
    rem = np.nonzero(~ins)[0]
    dr = skin_tree.query(V2[rem], workers=-1)[0] if len(rem) else np.zeros(0)
    dsp = np.linalg.norm(V2 - V, axis=1)
    st = dict(n_vertices=int(len(V)), n_moved=int((dsp > 1e-6).sum()), n_outside_source=int(moved_total.sum()),
              displacement_mean_mm=round(float(dsp[dsp > 1e-6].mean()), 2) if (dsp > 1e-6).any() else 0.0,
              displacement_max_mm=round(float(dsp.max()), 2),
              outside_after_n=int(len(rem)), outside_after_max_mm=round(float(dr.max()), 2) if len(rem) else 0.0,
              bone_guard_pushed_out=pushed, passes=hist)
    return V2, st


def mesh_stats(V, F):
    import trimesh
    m = trimesh.Trimesh(V, F, process=False)
    a = np.degrees(m.face_adjacency_angles) if len(m.face_adjacency) else np.zeros(1)
    return dict(area_mm2=round(float(m.area), 1), volume_cm3=round(abs(float(m.volume)) / 1000.0, 4),
                mean_dihedral_deg=round(float(a.mean()), 1))


def flipped(V0, V1, F):
    n0 = np.cross(V0[F[:, 1]] - V0[F[:, 0]], V0[F[:, 2]] - V0[F[:, 0]])
    n1 = np.cross(V1[F[:, 1]] - V1[F[:, 0]], V1[F[:, 2]] - V1[F[:, 0]])
    d = (n0 * n1).sum(1)
    return int((d <= 0).sum()), len(F)


def analyse(key, src, tol):
    os_src = Path(src) if Path(src).is_absolute() else REPO / src
    import os
    os.environ["Q237_SRC_" + key] = str(os_src / DIR[key])
    B = CT.build(key, 2.0)
    val = CT.validate(B)
    g, body, st = B["g"], B["body"], B["skin_tree"]
    todo, skipped = [], []
    for x in B["S"]:
        V, F = x["v"], x["f"]
        ins = g.inside(body, V)
        if ins.all():
            continue
        d = st.query(V[~ins], workers=-1)[0]
        mx = float(d.max())
        if mx <= tol:
            continue
        why = exempt(x["id"], x["sys"])
        rec = dict(id=x["id"], sys=x["sys"], out_max_mm=round(mx, 2), out_n=int((~ins).sum()), n_vertices=int(len(V)))
        if why:
            rec["exempt"] = why
            skipped.append(rec)
        else:
            todo.append(rec)
    return B, val, sorted(todo, key=lambda r: -r["out_max_mm"]), sorted(skipped, key=lambda r: -r["out_max_mm"])


def run(mode, src="build/q297", out="/dev/shm/q299/pre", tol=5.0, keys=None):
    keys = keys or ZKEYS
    src_p = Path(src) if Path(src).is_absolute() else REPO / src
    rep = {"pages": {}}
    if REPORT.exists():                      # keep the pages this run does not touch
        try:
            rep = json.loads(REPORT.read_text())
        except Exception:
            rep = {"pages": {}}
    rep.update({"_README": ["Q299 containment fix; scripts/anatomy/q299/fix_contain299.py"],
                "src": str(src), "tol_mm": tol, "inset_mm": INSET, "sigma_mm": SIGMA, "passes": PASSES})
    rep.setdefault("pages", {})
    out_p = Path(out)
    if mode == "build":
        out_p.mkdir(parents=True, exist_ok=True)
        for k in ("own_m", "own_f"):
            if (out_p / DIR[k]).exists():
                shutil.rmtree(out_p / DIR[k])
            shutil.copytree(src_p / DIR[k], out_p / DIR[k])
    for key in keys:
        B, val, todo, skipped = analyse(key, src, tol)
        print(f"== {key} mask {'valid' if val['ok'] else 'INVALID: ' + '; '.join(val['reasons'])}; "
              f"to fix {len(todo)}, exempt {len(skipped)}", flush=True)
        page = dict(mask_valid=val["ok"], mask_validation=val, mask_error_band=B["error_band"],
                    to_fix=todo, exempt=skipped, fixed={})
        if mode == "build":
            g, body, st = B["g"], B["body"], B["skin_tree"]
            byid = {x["id"]: x for x in B["S"]}
            replace = {}
            for rec in todo:
                x = byid[rec["id"]]
                V0, F = x["v"].astype(float), x["f"]
                V1, s = pull_inside(V0, F, g, body, st, B["bones"], B["bone_tree"])
                fl, nf = flipped(V0, V1, F)
                a0, a1 = mesh_stats(V0, F), mesh_stats(V1, F)
                closed = a0["volume_cm3"] >= MIN_CLOSED_VOL_CM3
                s.update(out_max_before_mm=rec["out_max_mm"], flipped_tris=fl, tris=nf,
                         flipped_frac=round(fl / nf, 5),
                         area_before_mm2=a0["area_mm2"], area_after_mm2=a1["area_mm2"],
                         area_ratio=round(a1["area_mm2"] / a0["area_mm2"], 3),
                         volume_before_cm3=a0["volume_cm3"], volume_after_cm3=a1["volume_cm3"],
                         volume_ratio=round(a1["volume_cm3"] / a0["volume_cm3"], 3) if closed else None,
                         volume_note=None if closed else ("the mesh is not a closed solid (several open tubes), so its "
                                                          "signed volume is not meaningful and no ratio is quoted"),
                         dihedral_before_deg=a0["mean_dihedral_deg"], dihedral_after_deg=a1["mean_dihedral_deg"])
                if s["flipped_frac"] > MAX_FLIPPED_FRAC or abs(a1["mean_dihedral_deg"] - a0["mean_dihedral_deg"]) > MAX_DIHEDRAL_CHANGE_DEG:
                    s["refused"] = (f"the pull-in would damage this mesh ({100 * s['flipped_frac']:.2f} % of triangles flipped, "
                                    f"mean dihedral {a0['mean_dihedral_deg']:.1f} -> {a1['mean_dihedral_deg']:.1f} deg): "
                                    f"NOT moved, reported instead")
                    page.setdefault("refused", {})[rec["id"]] = s
                    print("   REFUSED", rec["id"], s["refused"], flush=True)
                    continue
                page["fixed"][rec["id"]] = s
                replace[rec["id"]] = (V1, F)
                print(f"   {rec['id'][:46]:46s} out {rec['out_max_mm']:6.2f} -> {s['outside_after_max_mm']:5.2f} mm | "
                      f"moved {s['n_moved']:5d}/{s['n_vertices']:5d} max disp {s['displacement_max_mm']:5.2f} | "
                      f"area x{s['area_ratio']:.3f} vol x{s['volume_ratio'] if s['volume_ratio'] is not None else float('nan'):.3f} flipped {fl} bonepush {s['bone_guard_pushed_out']}", flush=True)
            # write the page
            d_in, d_out = src_p / DIR[key], out_p / DIR[key]
            if d_out.exists():
                shutil.rmtree(d_out)
            d_out.mkdir(parents=True)
            for f in d_in.iterdir():
                if not f.name.startswith(STEM[key]) and f.name != "index.html":
                    shutil.copy2(f, d_out / f.name)
            man, blob = P5.load_page(d_in, STEM[key])
            ids_in_page = {m["id"] for m in man["meshes"]}
            meta = {}
            rp = {}
            # Part A: the measured pelvic-proportion statements (card text only, no geometry)
            pelvis_notes = PCARD.notes().get(key, {})
            for sid, note in pelvis_notes.items():
                if sid not in ids_in_page:
                    print("   WARNING pelvis note for a missing id:", sid)
                    continue
                m = next(x for x in man["meshes"] if x["id"] == sid)
                rec = json.loads(json.dumps(m.get("rec") or {}))
                rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                meta[sid] = (m["name"], rec)
            page["pelvis_cards"] = sorted(pelvis_notes)
            for sid, (V1, F) in replace.items():
                m = next(x for x in man["meshes"] if x["id"] == sid)
                rec = json.loads(json.dumps(m.get("rec") or {}))
                rec["procedural_badge"] = ((rec.get("procedural_badge") + " || ") if rec.get("procedural_badge") else "") + badge(key, sid, page["fixed"][sid])
                rp[sid] = (V1, F, rec)
            order = [m["id"] for m in man["meshes"]]
            page["fixed_indices"] = {sid: order.index(sid) for sid in rp}
            man2, _ = P5.save_page(d_out, STEM[key], man, blob, replace=rp, meta=meta)
            shutil.copy2(d_out / f"{STEM[key]}.html", d_out / "index.html")
            page["meshes"] = len(man2["meshes"])
        rep["pages"][key] = page
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    print("report", REPORT)


def badge(key, sid, s):
    return (f"Q299 containment fix: {s['n_outside_source']} of {s['n_vertices']} vertices of this mesh lay OUTSIDE this page's "
            f"own body (up to {s['out_max_before_mm']:.1f} mm in front of the nearest skin surface) and were pulled back in. "
            f"Each such vertex was moved to the nearest point of this page's own skin / subcutaneous surface and {INSET:.1f} mm "
            f"further in along the same line; the displacement was spread over the mesh with a {SIGMA:.0f} mm Gaussian, so "
            f"{s['n_moved']} vertices moved in all, by {s['displacement_mean_mm']:.1f} mm on average and {s['displacement_max_mm']:.1f} mm at most. "
            f"Nothing was sculpted and no vertex was invented: this is the skin guard of Q250 re-run against a body mask that "
            f"passes validation (Q250's own guard could not decide inside from outside against ~250 open skin patches and "
            f"recorded 1,057 such vertices as 'only counted'). Surface area x{s['area_ratio']:.3f}, enclosed volume "
            + (f"x{s['volume_ratio']:.3f}" if s['volume_ratio'] is not None else "not quoted (" + s['volume_note'] + ")")
            + f", {s['flipped_tris']} of {s['tris']} triangles flipped, mean dihedral "
            + f"{s['dihedral_before_deg']:.1f} -> {s['dihedral_after_deg']:.1f} deg. Furthest point outside after the fix: "
            f"{s['outside_after_max_mm']:.2f} mm (the body mask's own error band is p95 1.4 / max 8.3 mm). "
            + (f"{s['bone_guard_pushed_out']} vertices that the pull-in would have driven into a bone were pushed back out to 0.3 mm "
               f"off the bone surface. " if s['bone_guard_pushed_out'] else "")
            + ("THIS IS A LARGE SHAPE CHANGE: the structure lost more than a tenth of its enclosed volume, because the sculpted "
               "HuBMAP HRA breast object this page carries does not fit this page's chest skin. See docs/OPEN_ITEMS_FOR_OWNER.md: "
               "the alternatives are to re-run the Q250 chest-skin raise or to drop the HRA breast objects and keep only her own "
               "CT breast label (`breast_ct_l` / `breast_ct_r`, which is inside the body)." if (s['volume_ratio'] or 1) < 0.9 else ""))


def rig(key, fresh, out=None):
    """The moved structures are SKINNED, so their per-vertex skinning weights -- which make_pose_rig derives from the
    vertex positions -- have to come from a fresh run on the NEW page. Every other entry of the committed rig is kept
    byte for byte, the way Q292 and Q295 did it: only the replaced structures' entries are substituted."""
    import base64, zlib
    rep = json.loads(REPORT.read_text())["pages"][key]
    idx = sorted(rep["fixed_indices"].values())
    cp = REPO / f"data/anatomy/pose_rig_{key}.json"
    dst = Path(out) if out else cp
    A = json.loads(cp.read_text()); F = json.loads(Path(fresh).read_text())
    assert A["rig"]["count"] == F["rig"]["count"], (A["rig"]["count"], F["rig"]["count"])
    assert A["rig"]["nv"] == F["rig"]["nv"], "vertex counts changed: the fix must not add or drop a vertex"
    assert [x[0] for x in A["rig"]["segs"]] == [x[0] for x in F["rig"]["segs"]], "segment lists differ"
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"]))
    wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))

    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)

    rig = json.loads(json.dumps(A["rig"]))
    fsk = {e[0]: e for e in F["rig"]["skin"]}
    frg = {i: seg for seg, lst in F["rig"]["rigid"] for i in lst}
    # (entry, source blob) in the committed order, so unchanged chunks are copied byte for byte
    items = [(e, wa) for e in rig["skin"]]
    nsk = nrg = 0
    for i in idx:
        items = [(e, b) for e, b in items if e[0] != i]
        for g in rig["rigid"]:
            if i in g[1]:
                g[1] = [x for x in g[1] if x != i]
        if i in fsk:
            items.append((list(fsk[i]), wf)); nsk += 1
        else:
            seg = frg[i]
            for g in rig["rigid"]:
                if g[0] == seg:
                    g[1] = sorted(g[1] + [i]); break
            else:
                rig["rigid"].append([seg, [i]])
            nrg += 1
    rig["rigid"] = sorted([g for g in rig["rigid"] if g[1]])
    items.sort(key=lambda t: t[0][0])
    packed = bytearray(); out = []
    for e, src in items:
        e = list(e); s0 = e[4]; chunk = bytes(src[s0:s0 + seglen(e)])
        e[4] = len(packed); packed.extend(chunk); out.append(e)
    rig["skin"] = out
    rig["notes"] = A["rig"]["notes"] + (f"; Q299: {len(idx)} replaced geometries (the containment fix) take their "
                                        f"entries from a fresh run on the new page ({nsk} skinned, {nrg} rigid); "
                                        f"every other entry as committed")
    o = dict(A); o["rig"] = rig
    o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    dst.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(key, "rig", rig["count"], "skinned", len(rig["skin"]), "replaced skinned", nsk, "rigid", nrg,
          "weights", len(wa), "->", len(packed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "build", "rig"])
    ap.add_argument("--fresh", default="")
    ap.add_argument("--rig-out", default="")
    ap.add_argument("--src", default="build/q297")
    ap.add_argument("--out", default="/dev/shm/q299/pre")
    ap.add_argument("--tol", type=float, default=5.0)
    ap.add_argument("--pages", default="")
    a = ap.parse_args()
    if a.mode == "rig":
        for k in (a.pages.split(",") if a.pages else ZKEYS):
            f = a.fresh.replace("KEY", k) if a.fresh else f"/dev/shm/q299/fresh/pose_rig_{k}.json"
            if json.loads(REPORT.read_text())["pages"].get(k, {}).get("fixed_indices"):
                rig(k, f, a.rig_out.replace("KEY", k) if a.rig_out else None)
            else:
                print(k, "no replaced geometry: rig untouched")
    else:
        run(a.mode, a.src, a.out, a.tol, a.pages.split(",") if a.pages else None)
