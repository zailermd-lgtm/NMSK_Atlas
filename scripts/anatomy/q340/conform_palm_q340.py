#!/usr/bin/env python3
"""Q340: Base pages, both hands -- the superficial palmar arch layer and the vessels / sheaths that dip into the hand bones.

    python3 scripts/anatomy/q340/conform_palm_q340.py --page-dir DIR             # dry run: measure, report, write nothing
    python3 scripts/anatomy/q340/conform_palm_q340.py --page-dir DIR --write     # and write the page files in DIR

What is wrong (Q338 audit, re-measured here, data/derived/Q340_palm_report.json):
  (a) the Z-Anatomy superficial palmar arch, superficial venous palmar arch and common palmar digital arteries lie DEEP to the
      flexor tendons (inside the flexor tendons' column, at the level of the deep flexor tendons and lumbricals). Gray's Anatomy
      (1918, p. 598): "The superficial volar arch is covered by the skin, the Palmaris brevis, and the palmar aponeurosis. It lies
      upon the transverse carpal ligament, the Flexor digiti quinti brevis and Opponens digiti quinti, the tendons of the Flexor
      digitorum sublimis, the Lumbricales, and the divisions of the median and ulnar nerves."  p. 663: "The superficial and deep volar
      arterial arches are each accompanied by a pair of venae comitantes which constitute respectively the superficial and deep volar
      venous arches".  p. 598: the common volar digital arteries "proceed downward on the second, third, and fourth Lumbricales".
  (b) Z meshes dipping into hand bones (deep / superficial venous palmar arch, palmar metacarpal arteries, deep palmar arch, the
      cruciform part of the fibrous digital sheaths, the extensor digiti minimi sheath).  Gray p. 595: the deep volar arch "lies upon the
      carpal extremities of the metacarpal bones and on the Interossei"; the volar metacarpal arteries "run distally upon the Interossei".

The conform (a documented, rule-driven move of the real source meshes; their shape is the source's):
  (a) per hand and vessel family (arterial: superficial palmar arch + common palmar digital arteries + the palm segments of the
      proper palmar digital arteries; venous: superficial venous palmar arch + the palm segments of the palmar digital veins), in the
      palm frame of lib340 (metacarpal plane, palmar normal n): ONE lift along n per 1 mm (t, r) column of the palm plane (field2d), so
      every point of a column moves alike and the vessel's cross-section moves rigidly.  Per column the lift is what puts the vessel's
      lowest vertex CLEAR mm above the highest of the flexor tendons (FDS, FDP, FPL and its sheath, the digital synovial sheaths), the
      lumbricals, FDMB / ODM and the common palmar digital nerves; capped so its highest vertex stays CLEAR + ROOF_SMOOTH mm under the
      palmar aponeurosis / palm skin (where the layer is too thin, the roof wins); filled harmonically between columns; held at zero
      at every junction with a vessel that is not moved (ulnar / radial artery at the wrist, ulnar veins) and on the in-finger and
      thumb parts of the digital vessels, tapered by smoothstep over TAPER mm and never rising faster than SLOPE mm per mm; Lipschitz-
      clamped (GRAD) and Gaussian-smoothed so no triangle flips.  A family ships only if every member passes the guards.
  (b) each listed structure: its vertices inside a hand bone (watertight bone meshes) leave it by patches (per bone, linked within
      3 mm), each along ONE direction (the depth-weighted mean outward bone normal) by the line-searched distance to BONE_CLEAR mm
      outside every bone, as a column field in the plane normal to that direction, faded out along it over FALL mm (push_out_of_bone).
Guards (Q213 / Q333): vertex / triangle counts unchanged (the pose rig contract), flipped triangles <= 0.5 %, stretched (area x0.5 / x2)
<= before + 12 %; no guarded group (flexor tendons, lumbricals, digital nerves, digital synovial sheaths, palmar aponeurosis and palm
skin in the palm, bone) holds MORE of the structure's vertices after than before with a new entrant that moved > 0.25 mm; for (b) none
left > 1.5 mm inside a bone.  A stage ships only if it passes on BOTH hands (the hands stay mirror images).  Every replaced file is
first copied beside itself as `<name>.q340` (never overwriting an existing copy); a page that already carries a Q340 note is refused.
Deterministic (no random state).
"""
from __future__ import annotations

import argparse, base64, json, re, shutil, sys, time
from pathlib import Path

import numpy as np
import trimesh
from scipy import sparse
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (REPO, REPO / "scripts" / "zanatomy", HERE):
    sys.path.insert(0, str(p))
import build_zan_atlas_viewer as B                                    # noqa: E402  pack_mesh / split_blob
from scripts.transfer.q213_inbone import flipped_pct, stretched_pct  # noqa: E402  Q213 triangle guards
import lib340 as L                                                    # noqa: E402  palm frame, height maps, Q338 Page
A = L.A

OUT = REPO / "data/derived/Q340_palm_report.json"
CLEAR, XS, TAPER, JOIN, BONE_CLEAR, SLOPE, GRAD, FALL, ROOF_SMOOTH = 0.5, 2.5, 6.0, 1.5, 0.3, 1.0, 1.5, 8.0, 1.0
FLOOR = ["zan_humero_ulnar_head_of_flexor_digitorum_superficialis", "flexor_digitorum_profundus", "flexor_pollicis_longus",
         "zan_tendon_sheath_of_flexor_pollicis_longus", "zan_synovial_sheaths_of_digits_of_hand", "zan_lumbrical_muscles_of_hand",
         "flexor_digiti_minimi_brevis_hand", "opponens_digiti_minimi",
         "zan_common_palmar_digital_branches_of_median_nerve", "zan_common_palmar_digital_branches_of_ulnar_nerve"]
ROOF = ["palmar_aponeurosis", "zan_skin_palm"]
FAMILIES = {   # moved meshes -> per mesh, the unmoved structures it JOINS (taper anchors; a mere crossing is not a junction)
    "arterial": (["zan_superficial_palmar_arch", "zan_common_palmar_digital_arteries", "zan_proper_palmar_digital_arteries"],
                 {"zan_superficial_palmar_arch": ["zan_ulnar_artery", "zan_radial_artery"], "zan_common_palmar_digital_arteries": [],
                  "zan_proper_palmar_digital_arteries": []}),
    "venous": (["zan_superficial_venous_palmar_arch", "zan_palmar_digital_veins"],
               {"zan_superficial_venous_palmar_arch": ["zan_ulnar_veins"], "zan_palmar_digital_veins": []}),
}
# the digital vessels move only where they lie in the palm: their in-finger part (on a phalanx of fingers 2-5) and everything of the
# thumb is held in place -- the junction "at the finger bases" -- and the field tapers to zero toward it
DIVE_FAMILIES, DIVE = {"venous"}, 3.0
HOLD_IN_FINGERS = {"zan_proper_palmar_digital_arteries", "zan_palmar_digital_veins"}
IN_BONE = ["zan_deep_venous_palmar_arch", "zan_superficial_venous_palmar_arch", "zan_palmar_metacarpal_arteries", "zan_deep_palmar_arch",
           "zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand", "zan_tendon_sheath_of_extensor_digiti_minimi_manus"]
GUARD = {   # structure groups whose interior a moved vessel must not newly enter (column-extent test, lib340.HMap.inside)
    "flexor tendons": ["zan_humero_ulnar_head_of_flexor_digitorum_superficialis", "flexor_digitorum_profundus", "flexor_pollicis_longus"],
    "lumbricals": ["zan_lumbrical_muscles_of_hand"],
    "digital nerves": ["zan_common_palmar_digital_branches_of_median_nerve", "zan_common_palmar_digital_branches_of_ulnar_nerve",
                       "zan_proper_palmar_digital_branches_of_median_nerve", "zan_proper_palmar_digital_branches_of_ulnar_nerve",
                       "ulnar_n_superficial_branch", "ulnar_n_deep_branch", "recurrent_branch_of_median_n"],
    "digital synovial sheaths": ["zan_synovial_sheaths_of_digits_of_hand", "zan_tendon_sheath_of_flexor_pollicis_longus"],
    "Z common flexor sheath (reported)": ["zan_common_flexor_tendon_sheath"],
}
LIT = {"files": re.compile(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", re.M),
       "manifest": re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)}
GRAY = ("Gray's Anatomy of the Human Body, 20th ed. (1918), p. 598 (en.wikisource.org, Page:Anatomy_of_the_Human_Body_(1918).djvu/598, "
        "OCR text layer)")
GRAY_V = "Gray 1918 p. 663 (Page:Anatomy_of_the_Human_Body_(1918).djvu/663)"
GRAY_D = "Gray 1918 p. 595 (Page:Anatomy_of_the_Human_Body_(1918).djvu/595)"
KAUR = "Kaur et al. 2023, Cureus 15:e35144, doi:10.7759/cureus.35144 (dissection: skin, palmar aponeurosis reflected, then the arch)"


# ------------------------------------------------------------------ page I/O (as scripts/anatomy/q333/fix_chest_wall_q333.py, any Base page)
def stem_of(d: Path):
    s = [p.name[:-5] for p in d.glob("atlas_viewer_*.html")]
    assert len(s) == 1, f"{d}: expected one atlas_viewer_*.html, found {s}"
    return s[0]


def pages_of(d: Path, stem):
    return [p for p in (d / f"{stem}.html", d / "index.html") if p.exists()]


def read_page(d: Path, stem):
    t = pages_of(d, stem)[0].read_text(encoding="utf-8")
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


def write_page(d: Path, stem, man_old, man_new, blob_new, old_files):
    pages = pages_of(d, stem)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert LIT["manifest"].search(t).group(1) == ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, stem)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q340")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q340")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + ser_manifest(man_new) + ";", t, count=1)
        t2 = LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def badge_add(rec, text):
    rec = json.loads(json.dumps(rec or {}))
    b = rec.get("procedural_badge") or ""
    rec["procedural_badge"] = (b + (" " if b else "") + text).strip()
    return rec


# ------------------------------------------------------------------ geometry helpers
def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def field2d(ab, req, cap=None, junc=(), zero_pts=None, slope=None, taper=None, decay=1.0, mask_mm=6.0, cell=1.0, iters=2500, sigma=2.5, grad=None):
    """a scalar move field on a 1 mm grid of 2-D coordinates `ab` (the plane normal to the move direction), so every point of a column
    moves by the same amount: the map x -> x + L(a, b) u has Jacobian determinant 1 and cannot flip a triangle.
    req: per point minimum (max per cell); cap: per point maximum (min per cell, eroded one cell); junc: [(centre ab, r0)] where L = 0,
    with w = smoothstep((d - r0) / taper) and L <= slope (d - r0) around them; the requirement is filled between (harmonic when decay = 1,
    else decayed), Gaussian-smoothed (sigma cells) over the vessel's own footprint (cells within mask_mm of a point), then sampled bilinearly."""
    from scipy import ndimage as ndi
    lo = np.floor(ab.min(0) / cell) - int(mask_mm / cell) - 3
    I = (np.floor(ab / cell) - lo).astype(int)
    sh = I.max(0) + int(mask_mm / cell) + 4
    R = np.zeros(sh); np.maximum.at(R, (I[:, 0], I[:, 1]), np.maximum(req, 0))
    occ = np.zeros(sh, bool); occ[I[:, 0], I[:, 1]] = True
    mask = ndi.distance_transform_edt(~occ) <= mask_mm / cell
    gx, gy = np.meshgrid(np.arange(sh[0]), np.arange(sh[1]), indexing="ij")
    G = (np.stack([gx, gy], -1) + lo + 0.5) * cell
    dist = np.full(sh, 1e6)
    for c, r0 in junc:
        dist = np.minimum(dist, np.maximum(np.linalg.norm(G - np.asarray(c), axis=-1) - r0, 0.0))
    if zero_pts is not None and zero_pts.any():          # held points (a vessel's in-finger part): their cells are zero too
        Z = np.zeros(sh, bool); Z[I[zero_pts, 0], I[zero_pts, 1]] = True
        dist = np.minimum(dist, ndi.distance_transform_edt(~Z) * cell)
    w = smoothstep(dist / taper) if taper else np.ones(sh)
    Rw = R * w
    if slope:
        Rw = np.minimum(Rw, slope * dist)
    fm = mask.astype(float); den = ndi.uniform_filter(fm, 3, mode="constant")
    Lg = Rw.copy()
    for _ in range(iters):
        avg = ndi.uniform_filter(Lg * fm, 3, mode="constant") / np.maximum(den, 1e-9)
        Lg = np.maximum(Rw, decay * avg) * fm
        Lg[dist <= 0] = 0.0
    if slope:
        Lg = np.minimum(Lg, slope * dist)
    if cap is not None:
        C = np.full(sh, np.inf); np.minimum.at(C, (I[:, 0], I[:, 1]), cap)
        C = ndi.grey_erosion(np.where(np.isfinite(C), C, 1e6), size=5) - ROOF_SMOOTH   # room for the final smoothing's overshoot
        # where the layer is thinner than the vessel needs, the roof wins: the vessel stays CLEAR under the aponeurosis / skin
        Lg = np.minimum(Lg, np.maximum(C, 0))
    Lg = Lg * w
    # Lipschitz clamp (never raises L): |dL/da|, |dL/db| <= GRAD, so |grad L| <= GRAD sqrt 2 < 2 -- with |grad L| < 2 no triangle of any
    # orientation can flip under x -> x + L u (its normal n' . n >= 1 - |grad L| / 2 > 0)
    for _ in range(4 * max(sh)):
        Lp = np.pad(Lg, 1, mode="edge")
        nbm = np.minimum.reduce([Lp[:-2, 1:-1], Lp[2:, 1:-1], Lp[1:-1, :-2], Lp[1:-1, 2:]])
        L2 = np.minimum(Lg, nbm + (grad or GRAD) * cell)
        if np.allclose(L2, Lg):
            break
        Lg = L2
    # last, a Gaussian over the footprint: smooth at the scale of the triangles (a long thin side-wall triangle sees the field's curvature)
    Lg = ndi.gaussian_filter(Lg * fm, sigma, mode="constant") / np.maximum(ndi.gaussian_filter(fm, sigma, mode="constant"), 1e-9) * fm
    return ndi.map_coordinates(Lg, ((ab / cell) - lo - 0.5).T, order=1, mode="nearest")


def cross_section(V, vals, fn, rad=XS):
    """per vertex: fn (max / min) of vals over the vertices of the same mesh within rad mm (the vessel's cross-section)"""
    tr = cKDTree(V)
    nb = tr.query_ball_point(V, rad)
    return np.array([fn(vals[n]) for n in nb])


class BoneSet:
    def __init__(self, bones):
        self.b = bones

    def signed(self, P):
        """signed distance to the nearest hand bone surface (+ inside), and the outward normal there; points far from every bone -> -inf"""
        P = np.asarray(P, float)
        s = np.full(len(P), -np.inf); nrm = np.zeros_like(P); name = np.array([""] * len(P), dtype=object)
        for k, t in self.b.items():
            lo, hi = t.bounds
            m = np.all((P > lo - 3) & (P < hi + 3), axis=1)
            if not m.any():
                continue
            idx = np.where(m)[0]
            Q, d, tri = trimesh.proximity.closest_point(t, P[idx])
            ins = t.contains(P[idx])
            sd = np.where(ins, d, -d)
            better = sd > s[idx]
            ii = idx[better]
            s[ii] = sd[better]; nrm[ii] = t.face_normals[tri[better]]; name[ii] = k
        return s, nrm, name


def push_out_of_bone(V, F, bs, clear=BONE_CLEAR, rounds=3, step=0.1, fall=FALL):
    """vertices inside a hand bone (or closer than `clear`) leave it by a locally RIGID, flip-free move.  The violators are grouped into
    patches (per bone, linked within 3 mm); a patch moves along ONE direction u, the depth-weighted mean outward normal of that bone at its
    violators, by the line-searched distance that puts each violator `clear` mm outside every bone.  The move is a column field in the
    plane normal to u (field2d: every point of a column along u moves alike, decayed 15 % per mm around the requirement, Lipschitz-clamped,
    Gaussian-smoothed), faded out along u over `fall` mm beyond the patch so the rest of the mesh stays where it is."""
    D = np.zeros_like(V); patches = []
    s0, _, _ = bs.signed(V)
    cand = np.where(s0 > -3.0 - XS)[0]
    for r in range(rounds):
        P = V + D
        s = np.full(len(V), -np.inf); nrm = np.zeros_like(V); nm = np.array([""] * len(V), dtype=object)
        s[cand], nrm[cand], nm[cand] = bs.signed(P[cand])
        viol = np.where(s > -clear)[0]
        if not len(viol):
            break
        for bone in sorted(set(nm[viol])):
            vb = viol[nm[viol] == bone]
            pairs = cKDTree(P[vb]).query_pairs(3.0, output_type="ndarray")
            Gp = sparse.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(vb), len(vb)))
            nc, lab = sparse.csgraph.connected_components(Gp, directed=False)
            for c in range(nc):
                vi = vb[lab == c]
                depth = s[vi] + clear
                u = (nrm[vi] * depth[:, None]).sum(0); u /= np.linalg.norm(u) + 1e-12
                need = np.zeros(len(vi))
                for _ in range(int((depth.max() + 6.0) / step) + 1):
                    q, _, _ = bs.signed(P[vi] + np.outer(need, u))
                    go = q > -clear
                    if not go.any():
                        break
                    need[go] += step
                e1 = np.cross(u, [1.0, 0, 0] if abs(u[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1)
                cc = P[vi].mean(0)
                z = (P - cc) @ u; zr = np.abs(z[vi]).max()
                ab = np.c_[(P - cc) @ e1, (P - cc) @ e2]
                rad = np.linalg.norm(ab[vi] - ab[vi].mean(0), axis=1).max() + 12.0
                near = np.where((np.abs(z) < zr + fall) & (np.linalg.norm(ab - ab[vi].mean(0), axis=1) < rad))[0]
                req = np.zeros(len(V)); req[vi] = need
                Lf = field2d(ab[near], req[near], decay=0.9, mask_mm=4.0, sigma=2.0, iters=300, grad=0.8)
                g = smoothstep(1.0 - (np.abs(z[near]) - zr) / fall)
                D[near] += np.outer(Lf * g, u)
                patches.append(dict(round=r, bone=bone, violators=int(len(vi)), direction=[round(float(x), 3) for x in u],
                                    move_mm=round(float(need.max()), 2)))
    s = np.full(len(V), -np.inf); s[cand], _, _ = bs.signed((V + D)[cand])
    return V + D, s, patches


def stats(D):
    n = np.linalg.norm(D, axis=1) if D.ndim == 2 else np.abs(D)
    return dict(max_mm=round(float(n.max()), 2), p95_mm=round(float(np.percentile(n, 95)), 2), median_mm=round(float(np.median(n)), 2),
                moved_gt0_5mm=int((n > 0.5).sum()))


# ------------------------------------------------------------------ per side
class Side:
    def __init__(self, pg, s, V):
        self.pg, self.s, self.V = pg, s, V          # V: id -> (v, f) from the page manifest
        self.P = L.Palm(pg, s)
        self.ids = {}

    def k(self, base):
        return L.sid(self.pg, base, self.s)

    def mesh(self, base):
        k = self.k(base)
        return self.V[k] if k else None

    def hmap(self, bases, override=None):
        ms = []
        for b in bases:
            k = self.k(b)
            if k:
                ms.append(override[k] if override and k in override else self.V[k])
        return L.HMap(self.P, ms) if ms else None


def measure_layers(sd: Side, cur):
    """per moved mesh: where its vertices sit relative to the tendon / nerve floor and the aponeurosis / skin roof (mid palm)"""
    Hf, Hr = sd.hmap(FLOOR), sd.hmap(ROOF)
    out = {}
    for fam, (moved, _) in FAMILIES.items():
        for b in moved:
            k = sd.k(b); v = cur[k][0]
            X = sd.P.trh(v); top, _ = Hf.at(X); _, bot = Hr.at(X)
            has = np.isfinite(top)
            above = X[:, 2] > top                       # palmar to everything of the floor in its column
            out[k] = dict(vertices=len(v), with_floor=int(has.sum()), above_floor_pct=round(100 * float(above[has].mean()), 1),
                          below_floor=int((~above & has).sum()),
                          above_roof=int((np.isfinite(bot) & (X[:, 2] > bot)).sum()),
                          h_p5_p50_p95=[round(float(x), 1) for x in np.percentile(X[:, 2], [5, 50, 95])])
    # the Q338 numbers: heights above the metacarpal plane in the palm (t between the metacarpal bases and heads)
    lo, hi = min(sd.P.mc_t[:4]), max(sd.P.mc_t[4:])
    ref = {}
    for b in ["zan_humero_ulnar_head_of_flexor_digitorum_superficialis", "flexor_digitorum_profundus", "palmar_aponeurosis"]:
        k = sd.k(b); X = sd.P.trh(cur[k][0]); m = (X[:, 0] > lo) & (X[:, 0] < hi)
        ref[k] = [round(float(x), 1) for x in np.percentile(X[m, 2], [5, 50, 95])]
    out["_reference_h_p5_p50_p95"] = ref
    out["_palm_frame"] = dict(plane_rms_mm=round(sd.P.plane_rms, 2), metacarpal_t_range_mm=[round(lo, 1), round(hi, 1)])
    return out


def palm_depth(sd: Side, cur):
    """verify_hand_q338.palm_depth on the given geometry: fraction of superficial-arch points (mid palm) palmar / dorsal to the flexor tendons"""
    pg, s = sd.pg, sd.s
    B_ = pg.M.bones(); J = {j["id"]: j for j in pg.rig["joints"]}
    w = np.array(J["wrist_" + s]["c"])
    d_h = L.HF.unit(np.vstack([B_["mc_%d_%s" % (f, s)]["v"] for f in range(2, 6)]).mean(0) - w)
    p = pg.H[s].fingers[3][0]["p"]; p = L.HF.unit(p - (p @ d_h) * d_h); r = L.HF.unit(np.cross(p, d_h))
    tpr = lambda Q: np.c_[(Q - w) @ d_h, (Q - w) @ p, (Q - w) @ r]
    fl = np.vstack([cur[sd.k(n)][0] for n in ("flexor_digitorum_profundus", "zan_humero_ulnar_head_of_flexor_digitorum_superficialis", "flexor_pollicis_longus")])
    F = tpr(fl); tr = cKDTree(F[:, [0, 2]])
    res = {}
    for b in ("zan_superficial_palmar_arch", "zan_superficial_venous_palmar_arch", "zan_common_palmar_digital_arteries"):
        X = tpr(cur[sd.k(b)][0]); X = X[(X[:, 0] > 15) & (X[:, 0] < 95)]
        above = below = n = 0
        for q in X:
            ii = tr.query_ball_point(q[[0, 2]], 4.0)
            if len(ii) >= 3:
                n += 1; above += q[1] > F[ii, 1].max(); below += q[1] < F[ii, 1].min()
        res[sd.k(b)] = dict(points=n, palmar_to_tendons_pct=round(100 * above / max(1, n), 1), dorsal_to_tendons_pct=round(100 * below / max(1, n), 1))
    return res


def penetration(sd: Side, cur, keys, masks=None):
    """vertices of each key inside each GUARD group (column extent) / above the aponeurosis / skin bottom (palm only) / inside a bone;
    with `masks` (a dict) the per-vertex booleans are kept there too"""
    res = {}
    H = {g: sd.hmap(bs, cur) for g, bs in GUARD.items()}
    Hr = {"palmar aponeurosis": sd.hmap(["palmar_aponeurosis"], cur), "palm skin": sd.hmap(["zan_skin_palm"], cur)}
    bs = BoneSet(A.bones_of_hand(sd.pg, sd.s))
    for k in keys:
        X = sd.P.trh(cur[k][0]); r = {}; mk = {}
        for g, h in H.items():
            if h is not None:
                mk[g] = h.inside(X)
        palm = X[:, 0] <= max(sd.P.mc_t[4:]) + 5.0          # the roof tests only in the palm (the column test is not valid in the fingers)
        for g, h in Hr.items():
            _, bot = h.at(X)
            mk["above " + g] = palm & np.isfinite(bot) & (X[:, 2] > bot + 0.3)
        s, _, nm = bs.signed(cur[k][0])
        mk["in bone > 0.5 mm"] = s > 0.5; mk["in bone > 1.5 mm"] = s > 1.5
        r = {g: int(m.sum()) for g, m in mk.items()}
        r["deepest in bone mm"] = round(float(max(s.max(), 0)), 2)
        r["bones"] = sorted(set(nm[s > 1.5]))
        res[k] = r
        if masks is not None:
            masks[k] = mk
    return res


def junctions(sd: Side, cur0, cur1):
    """distance of each moved mesh's junction vertices (within JOIN mm of an unmoved partner, or of the other moved mesh) to that partner,
    before -> after (median / max mm)"""
    out = {}
    for fam, (moved, partners) in FAMILIES.items():
        for b in moved:
            k = sd.k(b)
            for pb in partners[b] + [m for m in moved if m != b]:
                pk = sd.k(pb)
                if not pk:
                    continue
                v0 = cur0[k][0]; v1 = cur1[k][0]
                t0 = trimesh.Trimesh(*cur0[pk], process=False); t1 = trimesh.Trimesh(*cur1[pk], process=False)
                d0 = trimesh.proximity.closest_point(t0, v0)[1]
                c = d0 < JOIN
                if not c.any():
                    continue
                d1 = trimesh.proximity.closest_point(t1, v1[c])[1]
                out[f"{k} ~ {pk}"] = dict(junction_vertices=int(c.sum()), before_median_mm=round(float(np.median(d0[c])), 2),
                                          before_max_mm=round(float(d0[c].max()), 2), after_median_mm=round(float(np.median(d1)), 2),
                                          after_max_mm=round(float(d1.max()), 2))
    return out


def conform_family(sd: Side, fam, cur):
    """(a) the lift field of one vessel family -> {id: new v}, report"""
    moved, partners = FAMILIES[fam]
    keys = [sd.k(b) for b in moved]
    Hf, Hr = sd.hmap(FLOOR), sd.hmap(ROOF)
    Vs = [cur[k][0] for k in keys]
    offs = np.cumsum([0] + [len(v) for v in Vs])
    V = np.vstack(Vs)
    X = sd.P.trh(V)
    top, _ = Hf.at(X); _, bot = Hr.at(X)
    lo = np.where(np.isfinite(top), top + CLEAR - X[:, 2], 0.0)            # lift needed to clear the floor
    hi = np.where(np.isfinite(bot), bot - CLEAR - X[:, 2], np.inf)         # lift allowed under the roof
    # per cross-section (each mesh on its own)
    req = np.zeros(len(V)); cap = np.full(len(V), np.inf)
    for i in range(len(keys)):
        sl = slice(offs[i], offs[i + 1])
        req[sl] = np.maximum(cross_section(V[sl], lo[sl], np.max), 0)
        cap[sl] = cross_section(V[sl], hi[sl], np.min)
    if fam in DIVE_FAMILIES:   # the requirement comes from the vessel's main strand: a column's vertices more than DIVE mm below its top
        Ic = np.floor(X[:, :2]).astype(int); key = Ic[:, 0] * 100003 + Ic[:, 1]           # (a dive toward the deep arch) do not drive it
        order = np.argsort(key); ks = key[order]; hs = X[order, 2]
        starts = np.r_[0, np.nonzero(np.diff(ks))[0] + 1]
        colmax = np.maximum.reduceat(hs, starts)
        top_v = np.empty(len(X)); top_v[order] = np.repeat(colmax, np.diff(np.r_[starts, len(ks)]))
        req = np.where(X[:, 2] >= top_v - DIVE, req, 0.0)
    anchors = np.zeros(len(V), bool); anchor_rep = {}
    for i, b in enumerate(moved):
        sl = slice(offs[i], offs[i + 1])
        for pb in partners[b]:
            pk = sd.k(pb)
            if not pk:
                continue
            tp = trimesh.Trimesh(*cur[pk], process=False)
            d = trimesh.proximity.closest_point(tp, V[sl])[1]
            a = d < JOIN; anchors[sl] |= a
            if a.any():
                anchor_rep[f"{keys[i]} ~ {pk}"] = int(a.sum())
    # the field lives in the palm plane (t, r): every point of a column is lifted alike (no flipped triangle can arise); junction patches
    # (centroid c, radius r0, in the plane) hold it at zero, tapered by smoothstep over TAPER mm and never steeper than SLOPE
    ai = np.where(anchors)[0]; junc = []; jpatch = []
    if len(ai):
        pairs = cKDTree(V[ai]).query_pairs(3.0, output_type="ndarray")
        Gp = sparse.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(ai), len(ai)))
        nc, lab = sparse.csgraph.connected_components(Gp, directed=False)
        for c in range(nc):
            Pc = X[ai[lab == c], :2]; cc = Pc.mean(0); r0 = min(float(np.linalg.norm(Pc - cc, axis=1).max()), 4.0)
            junc.append((cc, r0))
            jpatch.append(dict(vertices=int((lab == c).sum()), radius_mm=round(r0, 2), at_t_r_mm=[round(float(x), 1) for x in cc]))
    hold = np.zeros(len(V), bool)
    for i, b in enumerate(moved):
        if b in HOLD_IN_FINGERS:
            sl = slice(offs[i], offs[i + 1])
            Lc = sd.pg.H[sd.s].locate(V[sl])
            hold[sl] = (Lc["finger"] == 1) | ((Lc["dist"] < 15) & ((Lc["seg"] > 0) | (Lc["t"] > 0.0)))
    L_ = field2d(X[:, :2], req, cap=np.where(hold, np.inf, cap), junc=junc, zero_pts=hold | anchors, slope=SLOPE, taper=TAPER)
    conflict = req > cap
    D = np.outer(L_, sd.P.n)
    new = {k: V[offs[i]:offs[i + 1]] + D[offs[i]:offs[i + 1]] for i, k in enumerate(keys)}
    rep = dict(meshes=keys, anchors=anchor_rep, junction_patches=jpatch, held_in_fingers=int(hold.sum()), slope=SLOPE, clear_mm=CLEAR, taper_mm=TAPER,
               required_lift=stats(req), displacement=stats(L_),
               per_mesh={k: stats(L_[offs[i]:offs[i + 1]]) for i, k in enumerate(keys)},
               conflict_vertices_gap_too_small=int(conflict.sum()),
               still_below_floor_in_taper=int(((X[:, 2] + L_) < top - 0.05)[np.isfinite(top)].sum()))
    return new, rep


def guard(sd, k, v0, v1, f, pen0, pen1, m0, m1, need_bone=False):
    """Q213 / Q333 triangle guards + penetration: a guarded group fails when MORE vertices lie inside it after than before AND at least one
    of them is a new entrant that moved more than 0.25 mm (so a vertex already lying on a boundary does not fail a structure for a
    sub-quarter-millimetre nudge); the lists give [before, after, new entrants]"""
    mv = np.linalg.norm(v1 - v0, axis=1) > 0.25
    new_in = {g: int((m1[g] & ~m0[g] & mv).sum()) for g in m0}
    rises = {g: [pen0[g], pen1[g], new_in[g]] for g in m0 if new_in[g] > 0}
    g = dict(flipped_pct=round(flipped_pct(v0, v1, f), 2), stretched_pct=[round(stretched_pct(v0, v0, f), 1), round(stretched_pct(v0, v1, f), 1)],
             penetration_before_after_new=rises, displacement=stats(v1 - v0))
    worse = {r for r, (b_, a_, n_) in rises.items() if "reported" not in r and a_ > b_ and n_ > 0}
    g["fails_on"] = sorted(worse)
    ok = g["flipped_pct"] <= 0.5 and g["stretched_pct"][1] <= g["stretched_pct"][0] + 12.0 and not worse
    if need_bone:
        ok = ok and pen1["in bone > 1.5 mm"] == 0
    g["ships"] = bool(ok)
    return g


def run_side(pg, s, V, log, deny=frozenset()):
    """(a) per vessel family, shipped only if EVERY member passes its guards (a family moves as one, so its junctions stay closed);
    then (b) per structure on the result of (a), shipped only if it passes its guards against its state before (b)"""
    sd = Side(pg, s, V)
    cur0 = dict(V); cur = dict(V)
    rep = {"side": s}
    moved_keys = [sd.k(b) for fam in FAMILIES.values() for b in fam[0]]
    inb_keys = [sd.k(b) for b in IN_BONE if sd.k(b)]
    keys = sorted(set(moved_keys + inb_keys))
    rep["layers_before"] = measure_layers(sd, cur0)
    rep["palm_depth_before"] = palm_depth(sd, cur0)
    M0 = {}
    pen0 = penetration(sd, cur0, keys, M0)
    rep["penetration_before"] = pen0
    # (a)
    rep["conform_a"] = {}; rep["guards_a"] = {}
    for fam in FAMILIES:
        new, r = conform_family(sd, fam, cur)
        trial = dict(cur); trial.update({k: (v, cur[k][1]) for k, v in new.items()})
        M1 = {}
        pen1 = penetration(sd, trial, list(new), M1)
        gs = {k: guard(sd, k, cur[k][0], new[k], cur[k][1], pen0[k], pen1[k], M0[k], M1[k]) for k in new}
        r["ships"] = all(g["ships"] for g in gs.values()) and ("a:" + fam) not in deny
        rep["conform_a"][fam] = r; rep["guards_a"].update(gs)
        if r["ships"]:
            cur = trial
        log(f"  {s} (a) {fam}: lift max {r['displacement']['max_mm']} / p95 {r['displacement']['p95_mm']} mm, gap-too-small {r['conflict_vertices_gap_too_small']}, "
            f"still below floor {r['still_below_floor_in_taper']} -> {'SHIPS' if r['ships'] else 'KEPT'}")
        for k, g in gs.items():
            log(f"      {k}: flipped {g['flipped_pct']} %, stretched {g['stretched_pct']}, new penetrations {g['penetration_before_after_new']}, move max {g['displacement']['max_mm']}"
                f" -> {'ok' if g['ships'] else 'FAILS'}")
    # (b)
    bs = BoneSet(A.bones_of_hand(pg, s))
    rep["conform_b"] = {}; rep["guards_b"] = {}
    for k in inb_keys:
        v, f = cur[k]
        s0, _, _ = bs.signed(v)
        if not (s0 > -BONE_CLEAR).any():
            continue
        v1, s1, patches = push_out_of_bone(v, f, bs, rounds=8)
        Ma, Mb = {}, {}
        pa = penetration(sd, cur, [k], Ma)[k]
        trial = dict(cur); trial[k] = (v1, f)
        pb_ = penetration(sd, trial, [k], Mb)[k]
        g = guard(sd, k, v, v1, f, pa, pb_, Ma[k], Mb[k], need_bone=True)
        rep["guards_b"][k] = g
        rep["conform_b"][k] = dict(inside_before=int((s0 > 0).sum()), inside_gt1_5_before=int((s0 > 1.5).sum()), deepest_before_mm=round(float(s0.max()), 2),
                                   inside_after=int((s1 > 0).sum()), inside_gt0_1_after=int((s1 > 0.1).sum()), inside_gt1_5_after=int((s1 > 1.5).sum()),
                                   deepest_after_mm=round(float(max(s1.max(), 0)), 2), displacement=stats(v1 - v), patches=patches, ships=g["ships"])
        base = k[:-2]
        if ("b:" + base) in deny:
            g["ships"] = False; g["denied"] = "the other side fails its guards (left and right are kept mirror images)"
        rep["conform_b"][k]["ships"] = g["ships"]
        if g["ships"]:
            cur = trial
        log(f"  {s} (b) {k}: inside {int((s0 > 0).sum())} (>1.5 mm {int((s0 > 1.5).sum())}, deepest {s0.max():.2f}) -> {int((s1 > 0.1).sum())} (deepest {max(s1.max(), 0):.2f}); "
            f"move max {g['displacement']['max_mm']} mm; flipped {g['flipped_pct']} %, stretched {g['stretched_pct']}, new penetrations {g['penetration_before_after_new']} -> {'SHIPS' if g['ships'] else 'KEPT'}")
    # measures after (what ships)
    rep["layers_after"] = measure_layers(sd, cur)
    rep["palm_depth_after"] = palm_depth(sd, cur)
    rep["penetration_after"] = penetration(sd, cur, keys)
    rep["junctions"] = junctions(sd, cur0, cur)
    rep["guards"] = {}
    changed = {}
    for k in keys:
        v0, f = cur0[k]; v1 = cur[k][0]
        if np.abs(v1 - v0).max() < 1e-6:
            continue
        rep["guards"][k] = dict(flipped_pct=round(flipped_pct(v0, v1, f), 2), stretched_pct=round(stretched_pct(v0, v1, f), 1),
                                displacement=stats(v1 - v0), ships=True)
        changed[k] = v1
    return rep, changed, cur0


def note_for(k, rep_side):
    """the card sentence of one changed structure (only the stages that shipped)"""
    a = None
    for fam, r in rep_side["conform_a"].items():
        if k in r["per_mesh"] and r["ships"]:
            a = (fam, r)
    g = rep_side["guards"][k]["displacement"]
    b = rep_side["conform_b"].get(k)
    b = b if b and b["ships"] else None
    parts = []
    if a:
        lb = rep_side["layers_before"][k]; la = rep_side["layers_after"][k]
        layer = ("into the layer between the flexor tendons / lumbricals / common palmar digital nerves and the palmar aponeurosis "
                 f"({CLEAR} mm above that floor and at least {CLEAR + ROOF_SMOOTH:g} mm under the aponeurosis / palm skin; where that layer is "
                 "thinner than the vessel, the vessel stays under the aponeurosis)")
        taper = (f"tapered to zero (smoothstep over {TAPER:g} mm, rise no steeper than {SLOPE:g} mm per mm) at its junctions with the vessels "
                 "that were not moved")
        if "superficial_palmar_arch" in k or "common_palmar_digital_arteries" in k:
            what = "moved palmarward along the normal of the metacarpal plane " + layer + ", " + taper
            why = (f"{GRAY}: \"The superficial volar arch is covered by the skin, the Palmaris brevis, and the palmar aponeurosis. It lies upon the "
                   f"transverse carpal ligament, the Flexor digiti quinti brevis and Opponens digiti quinti, the tendons of the Flexor digitorum "
                   f"sublimis, the Lumbricales, and the divisions of the median and ulnar nerves\"; the common volar digital arteries \"proceed "
                   f"downward on the second, third, and fourth Lumbricales\" (also {KAUR})")
        elif "proper_palmar_digital_arteries" in k:
            what = ("its palm segments (the little finger's ulnar artery from the arch, the stems at the webs) moved palmarward with the arch and the "
                    "common palmar digital arteries they join, " + layer + "; the in-finger and thumb parts are held in place and the move tapers to "
                    f"zero toward them (smoothstep over {TAPER:g} mm)")
            why = f"the arch they spring from lies upon the flexor tendons under the palmar aponeurosis ({GRAY})"
        elif "superficial_venous_palmar_arch" in k:
            what = "moved palmarward along the normal of the metacarpal plane " + layer + ", " + taper
            why = (f"{GRAY_V}: \"The superficial and deep volar arterial arches are each accompanied by a pair of venae comitantes which constitute "
                   f"respectively the superficial and deep volar venous arches\"; the arterial arch lies upon the flexor tendons ({GRAY})")
        else:
            what = ("its palm segments (the common palmar digital veins) moved palmarward with the superficial venous arch they open into, " + layer +
                    f"; the in-finger and thumb parts are held in place and the move tapers to zero toward them (smoothstep over {TAPER:g} mm)")
            why = f"{GRAY_V}: \"the common volar digital veins ... open into the superficial\" volar venous arch"
        parts.append(f"Q340: {what}, because the Z-Anatomy source put it deep to the flexor tendons and {why}; its vertices palmar to the tendon / "
                     f"nerve floor {lb['above_floor_pct']} % -> {la['above_floor_pct']} %")
    if b:
        parts.append(("Q340: " if not a else "") + f"pushed out of the hand bones it entered in the source ({b['inside_gt1_5_before']} vertices more than 1.5 mm inside, "
                     f"deepest {b['deepest_before_mm']} mm) to {BONE_CLEAR} mm outside the bone (one rigid direction per patch, the bone's outward normal), "
                     f"because soft tissue cannot lie in bone ({GRAY_D}: the deep volar arch \"lies upon the carpal extremities of the metacarpal bones and "
                     f"on the Interossei\")")
    parts.append(f"max move {g['max_mm']} mm, p95 {g['p95_mm']} mm; the shape and mesh are the source's (vertex / triangle counts unchanged).")
    return "; ".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    stem = stem_of(d)
    man, blob, files = read_page(d, stem)
    done = [m["id"] for m in man["meshes"] if "Q340:" in ((m.get("rec") or {}).get("procedural_badge") or "")]
    if done:
        print(f"Q340 already applied to this page ({len(done)} structures carry the Q340 note, e.g. {done[0]}); nothing done")
        return 0
    pg = A.Page(str(d))
    V = {m["id"]: dec(m, blob) for m in man["meshes"]}
    for x in pg.M.S:                                       # the Q338 Page reads the same geometry
        if x["id"] in V and len(x["v"]) == len(V[x["id"]][0]):
            assert np.abs(x["v"] - V[x["id"]][0]).max() < 1e-3, x["id"]
    rep = {"schema": "nmsk.q340.palm.v1", "round": "Q340", "generated": time.strftime("%Y-%m-%d"), "page_dir": str(d), "page": stem,
           "written": bool(a.write),
           "parameters": dict(clear_mm=CLEAR, cross_section_mm=XS, taper_mm=TAPER, junction_mm=JOIN, bone_clear_mm=BONE_CLEAR, floor=FLOOR, roof=ROOF,
                              families={k: dict(moved=v[0], junctions=v[1]) for k, v in FAMILIES.items()}, in_bone=IN_BONE),
           "sources": [GRAY, GRAY_V, GRAY_D, KAUR], "sides": {}}
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    replace = {}
    # pass 1: which stages pass on each side; a stage ships only if it passes on BOTH sides (the hands stay mirror images)
    deny = set()
    for s in ("r", "l"):
        r, _, _ = run_side(pg, s, V, lambda *_: None)
        deny |= {"a:" + f for f, x in r["conform_a"].items() if not x["ships"]}
        deny |= {"b:" + k[:-2] for k, x in r["conform_b"].items() if not x["ships"]}
    rep["denied_both_sides"] = sorted(deny)
    for s in ("r", "l"):
        r, out, _ = run_side(pg, s, V, print, frozenset(deny))
        rep["sides"][s] = r
        for k, v in out.items():
            replace[k] = (v, V[k][1], badge_add(recs[k], note_for(k, r)))
            r["guards"][k]["card"] = replace[k][2]["procedural_badge"]
    rep["geometry_changed"] = sorted(replace)
    man2, blob2 = repack(man, blob, replace)
    for m0, m1 in zip(man["meshes"], man2["meshes"]):
        assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
    assert len(blob2) == len(blob)
    if a.write:
        rep["files_changed"] = write_page(d, stem, man, man2, blob2, files)
        print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *.q340)")
    jp = Path(a.json)
    allr = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
    if allr.get("schema") != "nmsk.q340.palm_report.v1":
        allr = {"schema": "nmsk.q340.palm_report.v1", "pages": {}}
    allr["pages"][stem] = rep
    jp.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
    print(f"Q340 {'WRITTEN' if a.write else 'DRY RUN'}: {len(replace)} structures changed -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
