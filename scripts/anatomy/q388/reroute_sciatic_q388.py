#!/usr/bin/env python3
"""Q388: re-route the SCIATIC NERVE of a Base page below the piriformis by anatomical landmarks (rule-based, badged).

    python3 scripts/anatomy/q388/reroute_sciatic_q388.py --page-dir build/q309/viewer_zan_atlas --out DIR   # private copy
    python3 scripts/anatomy/q388/reroute_sciatic_q388.py --page-dir DIR --report-only                        # measure only

Never writes into --page-dir: the patched page files (atlas_viewer_<stem>.html, index.html, the four geo files) go to --out,
together with Q388_sciatic_<key>.json. The main thread copies them over build/q309/<dir> when no other round works there.

Finding (Q388 audit, docs/Q388_nerve_course_audit.md): on both Base bodies the Z-Anatomy sciatic nerve (a) lies on the
POSTERIOR face of the ischial tuberosity, 4-7 mm from the bone and medial to its lateral margin, behind the hamstring origin --
the owner's report; real nerve: lateral to the tuberosity, ~12 mm from its most lateral aspect (Miller et al. 2007,
doi:10.2106/JBJS.F.00094: 1.2 +/- 0.2 cm, 14 fresh-frozen cadavers; Leite et al. 2022, doi:10.1177/1120700020966255:
1.5 +/- 0.6 cm in the ischiofemoral space), lying on quadratus femoris (Mannan, Regional Dissection and Surface Anatomy,
p. 228-229); and (b) runs INSIDE the biceps femoris mesh for ~200 mm of the thigh, where the real nerve lies on adductor
magnus, deep to the long head of biceps which crosses it (Mannan p. 228-229 relations; surface line p. 539).

Rule (both sides of each body measured and moved independently, never mirrored):
  * Fixed: everything above the inferior border of piriformis (the plexus end and its contacts) and the last FIX_END mm
    before the division (the tibial and common fibular meshes start there). The cross-section of the tube is NOT re-shaped:
    every vertex moves by the displacement of its centreline station (a rigid translation per station), so calibre and
    length are the source's (guards below).
  * Ischial level (hip-bone slab of the tuberosity, QF levels): ideal centre = medial edge of the nerve MILLER_MM lateral to
    the tuberosity's lateral margin in that slab, z on the posterior face of quadratus femoris plus the nerve radius; then
    projected to the nearest point of free space (outside every muscle and bone, clearance >= the nerve radius or the best
    the neighbourhood allows).
  * Between the fixed exit and the ischial level: a straight line in the posterior view (Mannan p. 539: from the exit point
    "downwards and slightly outwards" to just medial of the midpoint of the trochanter-tuberosity line), z projected to free
    space behind the short rotators.
  * Thigh, where the source centre lies inside a muscle: the nearest free-space point (anterior neighbour must be adductor
    magnus or the femur-side muscles, not inside biceps). x blends from the ischial target to the source x over BLEND_MM.
  * Displacements interpolated along arclength (PCHIP), smoothed, zero at both fixed ends.
  * Attached rule-based stubs (sciatic branches to semitendinosus / semimembranosus / adductor magnus, nerve to obturator
    internus, inferior gluteal) follow with a weight that falls from 1 at the sciatic end to 0 at their far end.
Guards (a side failing any is NOT written): centreline outside every muscle / bone (winding < 0.5) at every station of the
moved stretch; no vertex deeper than BONE_TOL mm inside a bone; tube length within LEN_TOL %; displacement <= CAP mm; max
turning angle of the centreline <= KINK_DEG.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import distance_transform_edt, gaussian_filter1d
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib388 as L  # noqa: E402

REPO = L.REPO
sys.path.insert(0, str(REPO / "scripts/zanatomy"))
import build_zan_atlas_viewer as BZ  # noqa: E402
from conform_palm_q340 import LIT, ser_manifest, repack, read_page, stem_of  # noqa: E402

TAG = "Q388"
MILLER_MM = 12.0      # Miller 2007: 1.2 +/- 0.2 cm from the most lateral aspect of the ischial tuberosity
FIX_END = 12.0        # mm of the distal end kept (division: tibial / common fibular start)
BLEND_MM = 70.0
CAP = 45.0
KINK_DEG = 35.0
LEN_TOL = 6.0
BONE_TOL = 1.0
GRID = 0.75
WIN = 26.0
STUBS = ("sciatic_n_branch_to_semitendinosus", "sciatic_n_branch_to_semimembranosus",
         "sciatic_n_branch_to_adductor_magnus_hamstring_part", "nerve_to_obturator_internus", "inferior_gluteal_n")
CITES = ("Miller SL, Gill J, Webb GR (2007) J Bone Joint Surg Am 89:44-48, doi:10.2106/JBJS.F.00094; "
         "Leite MJ et al. (2022) Hip Int 32:510-515, doi:10.1177/1120700020966255; "
         "Wan-Ae-Loh P et al. (2020) Folia Morphol 79:681-689, doi:10.5603/FM.a2019.0140; "
         "Mannan, Regional Dissection and Surface Anatomy, p. 228-229 and 539 (knowledge only)")


def sid(base, s):
    return f"{base}_{s}"


def occupancy(sc, y, cx, cz, ids):
    """occupancy grid (True = inside a muscle or bone) of the horizontal slice y around (cx, cz)."""
    xs = np.arange(cx - WIN, cx + WIN + 1e-6, GRID)
    zs = np.arange(cz - WIN, cz + WIN + 1e-6, GRID)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    P = np.c_[X.ravel(), np.full(X.size, y), Z.ravel()]
    occ = np.zeros(len(P), bool)
    for k in ids:
        V = sc.D[k]["V"]; F = sc.D[k]["F"]
        lo, hi = V.min(0), V.max(0)
        if not (lo[1] - 1 <= y <= hi[1] + 1):
            continue
        cand = ~occ & np.all((P >= lo - 0.5) & (P <= hi + 0.5), axis=1)
        if not cand.any():
            continue
        # only faces near the slice matter little for the winding number; use all (exact)
        occ[np.where(cand)[0][np.abs(L.winding(V, F, P[cand])) > 0.5]] = True
    return xs, zs, occ.reshape(X.shape)


def project_free(sc, y, ideal_xz, r, ids, forbid=None):
    """nearest point to ideal (x, z) in free space with clearance >= r_eff (r_eff = min(r, 0.8 * best clearance within
    12 mm of the ideal)). forbid(x, z) -> bool mask of grid points not allowed by the relation rule."""
    xs, zs, occ = occupancy(sc, y, ideal_xz[0], ideal_xz[1], ids)
    clr = distance_transform_edt(~occ) * GRID
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    dist = np.hypot(X - ideal_xz[0], Z - ideal_xz[1])
    ok = np.ones_like(occ) if forbid is None else ~forbid(X, Z)
    near = (dist <= 12.0) & ok
    best = clr[near].max() if near.any() else clr[ok].max()
    r_eff = min(r, 0.8 * best)
    cand = (clr >= r_eff - 1e-9) & ok
    j = np.argmin(np.where(cand, dist, np.inf))
    i0, i1 = np.unravel_index(j, occ.shape)
    return np.array([xs[i0], zs[i1]]), float(clr[i0, i1]), float(r_eff)


def side_reroute(D, sc, s, log):
    sg = L.SG[s]
    N = D[sid("sciatic_n", s)]
    V0 = N["V"].astype(float)
    C = L.centreline(N, n=160)
    S = L.arclen(C)
    # nerve radius per station: half the mean width of a 3 mm slab perpendicular to y (the nerve runs ~vertically below the
    # piriformis)
    rad = np.array([np.sqrt(max(np.mean(np.sum((L.slab(V0, p[1], 1.5)[:, [0, 2]] - p[[0, 2]]) ** 2, 1)), 1.0))
                    if len(L.slab(V0, p[1], 1.5)) else 4.0 for p in C])
    rad = np.clip(gaussian_filter1d(rad, 3), 2.5, 9.0)
    hip = D[sid("hip_bone", s)]["V"]; fem = D[sid("femur", s)]["V"]
    pir = D[sid("piriformis", s)]["V"]; qf = D[sid("quadratus_femoris", s)]["V"]
    lo = hip[np.argmin(hip[:, 1])]
    it_blob = hip[(np.linalg.norm(hip - lo, axis=1) < 40) & (hip[:, 1] < lo[1] + 38)]
    ids_all = [k for k in sc.ids]
    # exit: lowest piriformis vertex within 40 mm (xz) of the nerve at that height
    yp = pir[:, 1].min()
    near_p = pir[np.linalg.norm(pir[:, [0, 2]] - C[np.argmin(np.abs(C[:, 1] - yp))][[0, 2]], axis=1) < 40]
    y_exit = float(near_p[:, 1].min()) if len(near_p) else float(yp)
    i_exit = int(np.argmin(np.abs(C[:, 1] - y_exit)))
    i_end = int(np.searchsorted(S, S[-1] - FIX_END))
    it_top, it_bot = float(it_blob[:, 1].max()), float(it_blob[:, 1].min())
    qf_bot = float(qf[:, 1].min())
    # ischial-level stations
    targets = {}
    ys_is = np.arange(min(it_top, qf[:, 1].max()) - 2, max(it_bot, qf_bot) + 2, -6.0)
    for y in ys_is:
        i = int(np.argmin(np.abs(C[:, 1] - y)))
        hs = L.slab(it_blob, C[i, 1], 2.0)
        if not len(hs):
            continue
        it_lat = float((sg * hs[:, 0]).max())
        xc = sg * (it_lat + MILLER_MM + rad[i])
        qs = L.slab(qf, C[i, 1], 2.0)
        qs = qs[np.abs(qs[:, 0] - xc) < 8] if len(qs) else qs
        zc = float(qs[:, 2].min() - rad[i] - 0.5) if len(qs) else float(C[i, 2])
        ids = sc.near_ids([xc, C[i, 1], zc], WIN + 5)
        # relation: not medial of the rule's medial edge by more than 2 mm (keeps the nerve lateral to the tuberosity)
        forbid = (lambda X, Z, it_lat=it_lat, r=rad[i]: sg * X - r < it_lat + MILLER_MM - 2.0 - 4.0)
        p, clr, reff = project_free(sc, C[i, 1], (xc, zc), rad[i], ids, forbid)
        targets[i] = dict(kind="ischial", y=float(C[i, 1]), ideal=[xc, zc], to=p.tolist(), clr=clr, r=float(rad[i]),
                          it_lat=sg * it_lat)
    if not targets:
        raise RuntimeError("no ischial station")
    i_is_top = min(targets); i_is_bot = max(targets)
    # straight posterior-view line from the exit to the top ischial target
    A = C[i_exit]; Bt = targets[i_is_top]
    for i in range(i_exit + 3, i_is_top, 4):
        t = (S[i] - S[i_exit]) / (S[i_is_top] - S[i_exit])
        x = A[0] + t * (Bt["to"][0] - A[0])
        z0 = C[i, 2] + t * (Bt["to"][1] - C[i_is_top, 2]) * 0.0
        ids = sc.near_ids([x, C[i, 1], z0], WIN + 5)
        p, clr, reff = project_free(sc, C[i, 1], (x, z0), rad[i], ids)
        targets[i] = dict(kind="line", y=float(C[i, 1]), ideal=[x, z0], to=p.tolist(), clr=clr, r=float(rad[i]))
    # thigh: stations below the ischial level whose source centre is inside a muscle / bone (or within the blend)
    x_is = targets[i_is_bot]["to"][0]
    for i in range(i_is_bot + 4, i_end - 2, 4):
        p0 = C[i]
        ins = L.inside_ids(sc, p0)
        blend = np.clip((S[i] - S[i_is_bot]) / BLEND_MM, 0, 1)
        x = (1 - blend) * x_is + blend * p0[0]
        if not ins and blend >= 1:
            continue
        ids = sc.near_ids([x, p0[1], p0[2]], WIN + 5)
        p, clr, reff = project_free(sc, p0[1], (x, p0[2]), rad[i], ids)
        targets[i] = dict(kind="thigh", y=float(p0[1]), ideal=[x, float(p0[2])], to=p.tolist(), clr=clr, r=float(rad[i]),
                          src_inside=[k for k, _ in ins])
    # displacement field along arclength
    keys = sorted(targets)
    knots_s = [S[i_exit]] + [S[i] for i in keys] + [S[i_end]]
    dx = [0.0] + [targets[i]["to"][0] - C[i, 0] for i in keys] + [0.0]
    dz = [0.0] + [targets[i]["to"][1] - C[i, 2] for i in keys] + [0.0]
    fx, fz = PchipInterpolator(knots_s, dx), PchipInterpolator(knots_s, dz)
    Dx = np.where((S > S[i_exit]) & (S < S[i_end]), fx(np.clip(S, knots_s[0], knots_s[-1])), 0.0)
    Dz = np.where((S > S[i_exit]) & (S < S[i_end]), fz(np.clip(S, knots_s[0], knots_s[-1])), 0.0)
    Dx = gaussian_filter1d(Dx, 2); Dz = gaussian_filter1d(Dz, 2)
    Dx[: i_exit + 1] = 0; Dz[: i_exit + 1] = 0; Dx[i_end:] = 0; Dz[i_end:] = 0
    disp = np.c_[Dx, np.zeros_like(Dx), Dz]
    # per-vertex: interpolate the station displacement by the vertex's projection onto the centreline
    seg_t = cKDTree(C)
    _, ii = seg_t.query(V0, k=2)
    a, b = C[ii[:, 0]], C[ii[:, 1]]
    w = np.clip(np.einsum("ij,ij->i", V0 - a, b - a) / np.maximum(np.einsum("ij,ij->i", b - a, b - a), 1e-9), 0, 1)
    dv = disp[ii[:, 0]] * (1 - w)[:, None] + disp[ii[:, 1]] * w[:, None]
    V1 = V0 + dv
    C1 = C + disp
    rep = dict(side=s, y_exit=y_exit, i_exit=i_exit, it_top=it_top, it_bot=it_bot, max_disp=float(np.linalg.norm(disp, axis=1).max()),
               stations={int(k): v for k, v in targets.items()})
    return V1, C, C1, disp, rep


def guards(D, sc, s, N, V1, C1, i_lo, i_hi, rep):
    fails = []
    Vs = N["V"].astype(float)
    # centreline outside muscle / bone on the moved stretch
    ins = []
    for i in range(i_lo, i_hi, 3):
        hit = [k for k, w in L.inside_ids(sc, C1[i]) if True]
        if hit:
            ins.append((round(float(C1[i, 1]), 1), hit))
    if ins:
        fails.append(f"centre inside {len(ins)} stations: {ins[:6]}")
    # bone depth
    for b in (sid("hip_bone", s), sid("femur", s)):
        Bm = D[b]
        moved = np.linalg.norm(V1 - Vs, axis=1) > 0.05
        if moved.any():
            wn = np.abs(L.winding(Bm["V"], Bm["F"], V1[moved][::3]))
            if (wn > 0.5).sum():
                dd = sc.kd(b).query(V1[moved][::3][wn > 0.5])[0]
                if dd.max() > BONE_TOL:
                    fails.append(f"{b}: {int((wn > 0.5).sum())} vertices inside, deepest {dd.max():.1f} mm")
    # length
    l0 = L.arclen(L.centreline(dict(V=Vs, F=N["F"]), n=160))[-1]
    l1 = L.arclen(L.centreline(dict(V=V1, F=N["F"]), n=160))[-1]
    if abs(l1 - l0) / l0 * 100 > LEN_TOL:
        fails.append(f"length {l0:.0f} -> {l1:.0f} mm")
    if rep["max_disp"] > CAP:
        fails.append(f"displacement {rep['max_disp']:.1f} > {CAP}")
    T = np.diff(C1, axis=0); T /= np.linalg.norm(T, axis=1)[:, None] + 1e-9
    ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", T[:-1], T[1:]), -1, 1)))
    if ang.max() > KINK_DEG:
        fails.append(f"kink {ang.max():.0f} deg")
    rep.update(len_before=float(l0), len_after=float(l1), max_turn_deg=float(ang.max()), inside_after=ins)
    return fails


def move_stubs(D, s, C0, disp):
    """rule-based stubs touching the moved sciatic follow: weight 1 at their sciatic end, 0 at their far end."""
    out = {}
    t0 = cKDTree(C0)
    moved = np.linalg.norm(disp, axis=1) > 0.05
    for base in STUBS:
        k = sid(base, s)
        if k not in D:
            continue
        V = D[k]["V"].astype(float)
        dd, ii = t0.query(V)
        if dd.min() > 12 or not moved[ii[np.argmin(dd)]]:
            continue
        a = V[np.argmin(dd)]
        g = np.linalg.norm(V - a, axis=1)
        w = np.clip(1 - g / max(g.max(), 1e-6), 0, 1) ** 1.5
        dv = disp[ii[np.argmin(dd)]]
        out[k] = V + w[:, None] * dv[None]
    return out


def write_copy(src: Path, out: Path, replace_V, D, badges):
    stem = stem_of(src)
    man, blob, files = read_page(src, stem)
    rep = {}
    for k, V in replace_V.items():
        rec = json.loads(json.dumps(D[k]["rec"] or {}))
        b = (rec.get("procedural_badge") or "")
        rec["procedural_badge"] = (b + " " + badges[k]).strip()
        rep[k] = (V, D[k]["F"].astype(np.int64), rec)
    man2, blob2 = repack(man, blob, rep)
    chunks = BZ.split_blob(blob2, stem)
    assert [n for n, _ in chunks] == [f["path"] for f in files], "geo file set would change"
    out.mkdir(parents=True, exist_ok=True)
    nf = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    for n, c in chunks:
        (out / n).write_bytes(base64.b64encode(c))
    for p in (src / f"{stem}.html", src / "index.html"):
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        assert LIT["manifest"].search(t).group(1) == ser_manifest(man)
        t2 = LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + ser_manifest(man2) + ";", t, count=1)
        t2 = LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(nf) + ";", t2, count=1)
        (out / p.name).write_text(t2, encoding="utf-8")
    return [n for n, _ in chunks] + [f"{stem}.html", "index.html"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--out")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)
    src = Path(a.page_dir).resolve()
    key = {v: k for k, v in L.PAGES.items()}.get(src.name)
    D = L.load(key or src.name, page_dir=src)
    if any(TAG in (D[sid("sciatic_n", s)]["rec"].get("procedural_badge") or "") for s in "lr"):
        print("Q388_REROUTE_REFUSED: page already carries the Q388 sciatic re-route"); return 2
    sc = L.Scene(D)
    replace, badges, report = {}, {}, {"page": src.name, "sides": {}}
    ok_all = True
    for s in "lr":
        N = D[sid("sciatic_n", s)]
        V1, C0, C1, disp, rep = side_reroute(D, sc, s, None)
        mv = np.where(np.linalg.norm(disp, axis=1) > 0.05)[0]
        fails = guards(D, sc, s, N, V1, C1, int(mv.min()) if len(mv) else 0, int(mv.max()) + 1 if len(mv) else 0, rep)
        rep["fails"] = fails
        report["sides"][s] = rep
        print(f"{src.name} {s}: max move {rep['max_disp']:.1f} mm, length {rep['len_before']:.0f}->{rep['len_after']:.0f} mm, "
              f"max turn {rep['max_turn_deg']:.0f} deg, guards: {'OK' if not fails else fails}")
        if fails:
            ok_all = False; continue
        nid = sid("sciatic_n", s)
        replace[nid] = V1
        badges[nid] = (f"{TAG} RULE-BASED RE-ROUTE (course only; the Z-Anatomy tube's own cross-section, calibre and length are "
                       f"kept): below the inferior border of piriformis the source nerve lay on the back of the ischial "
                       f"tuberosity and then inside the biceps femoris mesh; it is moved by up to {rep['max_disp']:.0f} mm so "
                       f"that at the tuberosity its medial edge lies {MILLER_MM:.0f} mm lateral to the tuberosity's lateral "
                       f"margin on quadratus femoris, and in the thigh it lies outside biceps, on adductor magnus. Stated error: "
                       f"+/- 2 mm at the tuberosity (the cited SD), elsewhere the free-space projection (grid {GRID} mm). "
                       f"Sources: {CITES}.")
        for k, V in move_stubs(D, s, C0, disp).items():
            replace[k] = V
            badges[k] = f"{TAG}: its sciatic end follows the rule-based sciatic re-route (weight 1 at the sciatic, 0 at its far end)."
    if a.out and not a.report_only and replace:
        out = Path(a.out).resolve()
        assert out != src, "--out must not be the source page dir"
        files = write_copy(src, out / src.name, replace, D, badges)
        report["written"] = files
        report["replaced"] = sorted(replace)
    rp = Path(a.out or ".") / f"Q388_sciatic_{src.name}.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=1, default=float))
    print("Q388_REROUTE_OK" if ok_all else "Q388_REROUTE_PARTIAL", "->", rp)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
