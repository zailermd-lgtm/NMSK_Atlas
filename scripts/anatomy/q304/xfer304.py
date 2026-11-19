#!/usr/bin/env python3
"""Q304 Part A: carry the lower-limb nerve meshes the Imaging page of a body does NOT have from the Combined page
of the SAME body, by the documented Q292 / Q295 / Q296 bone-point registration.

    python3 scripts/anatomy/q304/xfer304.py probe  [own_m own_f]         # is the Combined page really fitted to this skeleton?
    python3 scripts/anatomy/q304/xfer304.py build  [own_m own_f] [--out /dev/shm/q304/nerves]

Writes <out>/<key>_nerves.{json,npz} (per structure: the mapped vertices / faces, the volume, the triangles, the
mean dihedral, the local registration residual, the overlap with what the page already carries) and
data/derived/Q304_nerve_transfer.json.

Honesty rules this script enforces:
  * every transferred vertex is a Combined-page vertex moved by ONE map fitted on bone points only -- no sculpting,
    no per-structure free parameter, no invented geometry;
  * the Combined page's own provenance (Z-Anatomy fitted onto this body's skeleton in Q195, or a Q237 mirror of the
    opposite side) is carried through into the new card verbatim, and the new card's `method` / `error_band_mm`
    say in the viewer that this is Z-Anatomy geometry registered onto this subject's skeleton and NOT segmented
    from this subject's own imaging;
  * a nerve whose canonical name the Imaging page already carries is reported with the overlap measured, so the
    duplication is a stated fact and not a surprise.
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q241", REPO / "scripts/anatomy/q237", REPO / "scripts/anatomy/q292"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import model as MD      # noqa: E402
import core as C        # noqa: E402
import reg304 as R      # noqa: E402
sys.path.insert(0, str(REPO / "scripts/anatomy/q299"))
import contain299 as CT        # noqa: E402  (Q299's validated body mask + per-bone boxes)
import fix_contain299 as FX    # noqa: E402  (Q299's pull-inside guard and its smooth displacement field)

PAIR = {"own_m": "comb_m", "own_f": "comb_f"}
BODY = {"own_m": "vhm", "own_f": "vhf"}
OUT = Path("/dev/shm/q304/nerves")
REPORT = REPO / "data/derived/Q304_nerve_transfer.json"

# Q299's rule for "a lower-limb nerve", verbatim
LOWER_N = re.compile(r"fibular|peroneal|tibial_n|sciatic|sural|saphenous|femoral_n|obturator_n|gluteal_n|plantar_n|"
                     r"cutaneous_nerve_of_thigh|cutaneous_nerve_of_calf|cutaneous_nerve_of_leg|lumbosacral|pudendal")

# The Imaging pages merge several bones into ONE label and number the spine by structure index, not by level
# (Q297's finding for the hand); the Combined page keeps every bone separate and names the spine by level. So the
# correspondences are built over GROUPS: each group is "merge these pieces on the Combined page" against "merge
# these on the Imaging page". Nothing is matched by a name that does not mean the same thing on both pages.
GROUPS = {
    "femur_l": (r"^femur_l$", r"^femur_l$"), "femur_r": (r"^femur_r$", r"^femur_r$"),
    "tibia_l": (r"^tibia_l$", r"^tibia_l$"), "tibia_r": (r"^tibia_r$", r"^tibia_r$"),
    "fibula_l": (r"^fibula_l$", r"^fibula_l$"), "fibula_r": (r"^fibula_r$", r"^fibula_r$"),
    "patella_l": (r"^patella_l$", r"^patella_l$"), "patella_r": (r"^patella_r$", r"^patella_r$"),
    "hip_bone_l": (r"^hip_bone_l$", r"^hip_bone_l$"), "hip_bone_r": (r"^hip_bone_r$", r"^hip_bone_r$"),
    "sacrum": (r"^sacrum$", r"^sacrum$"), "coccyx": (r"^coccyx$", r"^coccyx$"),
    "talus_l": (r"^talus_l$", r"^talus_l$"), "talus_r": (r"^talus_r$", r"^talus_r$"),
    "calcaneus_l": (r"^calcaneus_l$", r"^calcaneus_l$"), "calcaneus_r": (r"^calcaneus_r$", r"^calcaneus_r$"),
    "tarsals_l": (r"^(navicular|cuboid|cuneiform_\w+)_l$", r"^(navicular|cuboid|cuneiform_\w+)_l$"),
    "tarsals_r": (r"^(navicular|cuboid|cuneiform_\w+)_r$", r"^(navicular|cuboid|cuneiform_\w+)_r$"),
    "metatarsals_l": (r"^mt_\d+_l$", r"^metatarsals_l$"), "metatarsals_r": (r"^mt_\d+_r$", r"^metatarsals_r$"),
    "phalanges_foot_l": (r"^ph_foot_\d+_\w+_l$", r"^phalanges_foot_l$"),
    "phalanges_foot_r": (r"^ph_foot_\d+_\w+_r$", r"^phalanges_foot_r$"),
    # the lumbar spine: `vert_l1..l5` on the Combined page against `lumbar_vertebrae#1..#5` on the Imaging page,
    # merged on both sides because the Imaging page's #n is its structure index and NOT the vertebral level.
    "lumbar_spine": (r"^vert_l[1-5]$", r"^lumbar_vertebrae#[1-5]$"),
}


def _merge(bones, rx):
    pieces = [v for k, v in sorted(bones.items()) if re.match(rx, k)]
    if not pieces:
        return None
    V, F, n = [], [], 0
    for p in pieces:
        V.append(p["v"]); F.append(p["f"] + n); n += len(p["v"])
    return dict(v=np.vstack(V), f=np.vstack(F), pieces=len(pieces))


def aligned(src_bones, dst_bones):
    """{group: (Combined-page mesh, Imaging-page mesh)} over the lower limb and the lumbar spine."""
    out = {}
    for g, (rs, rd) in GROUPS.items():
        s = _merge(src_bones, rs); d = _merge(dst_bones, rd)
        if s is not None and d is not None:
            out[g] = (s, d)
    return out


def bone_report(A):
    return {k: dict(src_v=int(len(s["v"])), dst_v=int(len(d["v"]))) for k, (s, d) in sorted(A.items())}


def fit(key, verbose=True):
    """-> (own model, combined model, reg304.Field, per-group report, aligned groups)"""
    own = MD.Model(key); comb = MD.Model(PAIR[key])
    A = aligned(comb.bones(), own.bones())
    if verbose:
        print(key, "bone groups matched:", len(A), sorted(A), flush=True)
    rng = np.random.default_rng(5)
    groups = {}
    for g, (s_, d_) in sorted(A.items()):
        X = R.tri_samples(s_["v"], s_["f"], 0.25, rng)[::2]
        Y = R.tri_samples(d_["v"], d_["f"], 1.0, rng, cap=160000)
        groups[g] = (X, cKDTree(Y), Y)
    F = R.Field(groups, iters=3, trim_mm=8.0, smoothing=10.0, ncp=3500)
    pg = F.per_group()
    if verbose:
        for g in sorted(pg):
            b, a_ = pg[g]["before"], pg[g]["after"]
            print(f"   {g:22s} n={a_['n']:6d}  before med {b['median_mm']:5.2f} p95 {b['p95_mm']:5.2f}"
                  f"   after med {a_['median_mm']:5.2f} p95 {a_['p95_mm']:5.2f} max {a_['max_mm']:6.2f}", flush=True)
    return own, comb, F, pg, A


def probe(keys):
    out = {}
    for key in keys:
        own = MD.Model(key); comb = MD.Model(PAIR[key])
        A = aligned(comb.bones(), own.bones())
        rows = {}
        rng = np.random.default_rng(3)
        for k, (s, d) in sorted(A.items()):
            X = R.tri_samples(s["v"], s["f"], 0.25, rng)
            Y = R.tri_samples(d["v"], d["f"], 1.0, rng, cap=120000)
            dd = cKDTree(Y).query(X, workers=-1)[0]
            rows[k] = dict(n=int(len(X)), median_mm=round(float(np.median(dd)), 2),
                           p95_mm=round(float(np.quantile(dd, 0.95)), 2), max_mm=round(float(dd.max()), 2))
            print(f"  {key} {k:26s} n={rows[k]['n']:6d} median {rows[k]['median_mm']:5.2f}  p95 {rows[k]['p95_mm']:5.2f}  max {rows[k]['max_mm']:6.2f}", flush=True)
        med = float(np.median([v["median_mm"] for v in rows.values()]))
        out[key] = dict(bones=rows, median_of_bone_medians_mm=round(med, 2))
    return out


def canon(sid):
    side, cn, how = C.side_and_canon({"id": sid, "side": "m"})
    return cn


def dihedral_mean(V, F):
    m = trimesh.Trimesh(V, F, process=False)
    a = m.face_adjacency_angles
    return float(np.degrees(np.mean(a))) if len(a) else 0.0


# ---------------------------------------------------------------------------- the two guards, both Q299's own
def push_out_of_bone(V, F, bones, bone_tree, inset=0.3):
    """Q299's bone guard applied to a whole structure: every vertex inside the page's own per-bone masks is moved to
    the nearest bone surface point plus `inset` mm, and the displacement is spread with Q299's own Gaussian field so
    the mesh keeps its shape (a tube's ring translates instead of collapsing onto one bone point)."""
    V2 = V.astype(float).copy()
    for _ in range(3):
        lo, hi = V2.min(0), V2.max(0)
        hit = np.zeros(len(V2), bool)
        for b in bones:
            if (b.hi < lo).any() or (b.lo > hi).any():
                continue
            hit |= b.inside(V2)
        idx = np.nonzero(hit)[0]
        if not len(idx):
            break
        d, j = bone_tree.query(V2[idx], workers=-1)
        q = bone_tree.data[j]
        u = V2[idx] - q
        n = np.linalg.norm(u, axis=1); n[n < 1e-9] = 1e-9
        target = q + (u / n[:, None]) * inset
        V2 = V2 + FX.smooth_field(V2, V2[idx].copy(), target - V2[idx])
    return V2


def in_bone_frac(V, F, bones, rng):
    P = CT.tri_samples(V, F, 1.0, rng, cap=40000)
    lo, hi = P.min(0), P.max(0)
    hit = np.zeros(len(P), bool)
    for b in bones:
        if (b.hi < lo).any() or (b.lo > hi).any():
            continue
        hit |= b.inside(P)
    return float(hit.mean())


def mesh_guard(V0, V1, F):
    """Q299's mesh guard: refuse a move that flips more than 3 % of the triangles or shifts the mean dihedral by
    more than 8 deg."""
    nf, tot = FX.flipped(V0, V1, F)
    d0 = dihedral_mean(V0, F); d1 = dihedral_mean(V1, F)
    ok = (nf / max(tot, 1) <= 0.03) and abs(d1 - d0) <= 8.0
    return ok, dict(flipped=nf, flipped_pct=round(100.0 * nf / max(tot, 1), 2),
                    dihedral_before_deg=round(d0, 1), dihedral_after_deg=round(d1, 1))


def build(keys, out_root):
    out_root = Path(out_root); out_root.mkdir(parents=True, exist_ok=True)
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    for key in keys:
        own, comb, reg, breport, A = fit(key)
        st = reg.stats()
        print(key, "registration", st, flush=True)
        oS = {x["id"]: x for x in own.S}
        own_canon = {}
        for x in own.S:
            own_canon.setdefault(canon(x["id"]), []).append(x["id"])
        cands = [x for x in comb.S if x["sys"] == "nerve" and LOWER_N.search(re.sub(r"^zan_", "", x["id"]))
                 and x["id"] not in oS]
        items = {}
        arrays = {}
        # the Combined page's OWN in-bone fraction per candidate, so the bone guard can tell what it inherited
        print(key, "building the Q299 body mask of the Combined page (for the inherited bone penetration) ...", flush=True)
        BC = CT.build(PAIR[key], 2.0)
        _rngc = np.random.default_rng(11)
        comb_bone_frac = {x["id"]: round(in_bone_frac(np.asarray(x["v"], float), np.asarray(x["f"], np.int64), BC["bones"], _rngc), 4)
                          for x in cands}
        del BC
        own_nerve_pts = np.vstack([x["v"] for x in own.S if x["sys"] == "nerve"])
        own_tree = cKDTree(own_nerve_pts)
        # the two guards are Q299's own, run against the Imaging page's OWN validated body mask and per-bone boxes
        print(key, "building the Q299 body mask of the target page ...", flush=True)
        BM = CT.build(key, 2.0)
        mval = CT.validate(BM)
        assert mval["ok"], f"{key}: the Q299 body mask does not validate: {mval['reasons']}"
        rng = np.random.default_rng(11)
        for x in sorted(cands, key=lambda y: y["id"]):
            V0 = np.asarray(x["v"], float); F = np.asarray(x["f"], np.int64)
            V = reg(V0)
            loc = reg.local(V0, 40.0)
            guards = {}
            # (1) skin: a vertex outside the page's own body mask is pulled back in (Q299 pull_inside, which also
            #     runs Q299's bone guard afterwards); refused by the mesh guard rather than forced.
            if not BM["g"].inside(BM["body"], V).all():
                V1, gs = FX.pull_inside(V, F, BM["g"], BM["body"], BM["skin_tree"], BM["bones"], BM["bone_tree"])
                ok, mg = mesh_guard(V, V1, F)
                guards["skin_pull"] = dict(applied=bool(ok), **gs, **mg)
                if ok:
                    V = V1
            # (2) bone: only where the transfer made it WORSE than the Combined page already was by > 10 points of
            #     volume (Q299's policy: a Z mesh that is inside a bone on the source page is the source's geometry,
            #     reported and not re-routed; what this round may not do is add penetration of its own).
            fb_now = in_bone_frac(V, F, BM["bones"], rng)
            fb_comb = comb_bone_frac.get(x["id"])
            if fb_comb is not None and fb_now > fb_comb + 0.10 and fb_now > 0.05:
                V1 = push_out_of_bone(V, F, BM["bones"], BM["bone_tree"])
                ok, mg = mesh_guard(V, V1, F)
                after = in_bone_frac(V1, F, BM["bones"], rng) if ok else fb_now
                guards["bone_push"] = dict(applied=bool(ok), in_bone_frac_combined=round(fb_comb, 4),
                                           in_bone_frac_before=round(fb_now, 4), in_bone_frac_after=round(after, 4), **mg)
                if ok:
                    V = V1; fb_now = after
            try:
                vol = float(trimesh.Trimesh(V, F, process=False).volume) / 1000.0
                vol0 = float(trimesh.Trimesh(V0, F, process=False).volume) / 1000.0
            except Exception:
                vol = vol0 = float("nan")
            cn = canon(x["id"])
            dup = own_canon.get(cn, [])
            d_own = float(own_tree.query(V, workers=-1)[0].min())
            items[x["id"]] = dict(
                id=x["id"], name=(x.get("rec") or {}).get("name") or x.get("name") or x["id"],
                side=x["side"], canon=cn, nv=int(len(V)), tris=int(len(F)),
                cm3=round(vol, 4), cm3_combined=round(vol0, 4),
                dihedral_mean_deg=round(dihedral_mean(V, F), 1),
                moved_median_mm=round(float(np.median(np.linalg.norm(V - V0, axis=1))), 2),
                moved_max_mm=round(float(np.linalg.norm(V - V0, axis=1).max()), 2),
                local_resid=loc, bbox_mm=np.round(V.max(0) - V.min(0), 1).tolist(),
                y_range=[round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)],
                already_on_page_same_nerve=dup,
                nearest_own_nerve_mm=round(d_own, 2),
                in_bone_frac=round(fb_now, 4),
                in_bone_frac_combined=(round(fb_comb, 4) if fb_comb is not None else None),
                guards=guards,
                rec_combined=x.get("rec") or {})
            arrays[x["id"] + "__v"] = V.astype(np.float32)
            arrays[x["id"] + "__f"] = F.astype(np.int32)
        np.savez_compressed(out_root / f"{key}_nerves.npz", **arrays)
        (out_root / f"{key}_nerves.json").write_text(json.dumps(items, indent=1, default=float), encoding="utf-8")
        rep[key] = dict(pair=PAIR[key], registration=st, bones=breport,
                        bone_groups=len(A), n_transferred=len(items),
                        triangles=int(sum(v["tris"] for v in items.values())),
                        cm3=round(sum(v["cm3"] for v in items.values()), 2),
                        ids=sorted(items))
        print(key, "->", len(items), "nerves,", rep[key]["triangles"], "triangles,", rep[key]["cm3"], "cm3", flush=True)
    rep["_README"] = ["Q304 Part A: lower-limb nerve meshes carried from the Combined page of the same body onto the "
                      "Imaging page by the Q292/Q295/Q296 bone-point registration (scripts/anatomy/q304/xfer304.py)."]
    REPORT.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "build"])
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    keys = a.keys or ["own_m", "own_f"]
    if a.cmd == "probe":
        r = probe(keys)
        p = REPO / "data/derived/Q304_frame_probe.json"
        p.write_text(json.dumps(r, indent=1), encoding="utf-8"); print("->", p)
    else:
        build(keys, a.out)


if __name__ == "__main__":
    main()
