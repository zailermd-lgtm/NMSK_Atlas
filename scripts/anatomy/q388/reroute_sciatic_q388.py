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
    every ring moves by the displacement of its (smoothed) centreline station, so calibre, vertex / triangle counts and
    order are the source's (pose-rig contract).
  * Ideal centre per station: exit -> ischial level on a straight line (Mannan p. 539: "downwards and slightly
    outwards"), z on the posterior face of the gemelli / obturator internus (Mannan p. 228-229); at the ischial
    tuberosity the nerve's medial edge MILLER_MM lateral of the tuberosity's lateral margin, on the posterior face of
    quadratus femoris; below it a blend back to the source course over BLEND_MM (no anterior push onto adductor magnus:
    the source is already deeper under the skin than Bruhn 2009 measured).
  * A Viterbi chain through free space (cf. scripts/cryo/vhf_nerve_track.py): per station, candidates on a GRID mm slice
    grid (2-D winding number of the oriented muscle / bone sections); unary = distance to the ideal + overlap with muscle +
    12 x depth inside muscle (+ a penalty for being medial of the Miller line at the tuberosity); transition = step between
    consecutive stations (~3 mm apart), steps > 8 mm forbidden.
  * Attached rule-based stubs (sciatic branches to semitendinosus / semimembranosus / adductor magnus, nerve to obturator
    internus, inferior gluteal) follow with a weight that falls from 1 at the sciatic end to 0 at their far end.
Guards (a side failing any is NOT written): centre not deeper than CENTRE_TOL mm inside a muscle and never inside a bone
on the moved stretch; no vertex deeper than BONE_TOL mm inside a bone; tube length within LEN_TOL %; displacement <= CAP mm;
max turning angle of the smoothed centreline <= max(KINK_DEG, source + 5). A page already carrying the Q388 badge is refused.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
from pathlib import Path

import numpy as np
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
BLEND_MM = 150.0
CAP = 45.0
KINK_DEG = 35.0
LEN_TOL = 6.0
BONE_TOL = 1.0
GRID = 0.75
CENTRE_TOL = 1.5   # mm a centre may sit inside a packed muscle junction (surface sampling of the source meshes)
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
        segs = L.slice_segments(V, F, y)
        if len(segs):
            occ |= L.inside_slice(segs, P[:, [0, 2]])
    return xs, zs, occ.reshape(X.shape)


ROTATORS = ("gemellus_superior", "obturator_internus", "gemellus_inferior", "quadratus_femoris", "hip_bone")


def post_face(D, s, y, x):
    """most posterior crossing (min z) of the short lateral rotators / hip bone with the line (x, y, z)."""
    zs = []
    for base in ROTATORS:
        m = D.get(sid(base, s))
        if m is None:
            continue
        segs = L.slice_segments(m["V"], m["F"], y)
        if not len(segs):
            continue
        a, b = segs[:, 0], segs[:, 1]
        lo = np.minimum(a[:, 0], b[:, 0]); hi = np.maximum(a[:, 0], b[:, 0])
        mm = (x >= lo) & (x < hi)
        if mm.any():
            tt = (x - a[mm, 0]) / np.where(b[mm, 0] - a[mm, 0] == 0, 1, b[mm, 0] - a[mm, 0])
            zs.append((a[mm, 1] + tt * (b[mm, 1] - a[mm, 1])).min())
    return float(min(zs)) if zs else None


def section_radius(V, F, y):
    s = L.slice_segments(V, F, y)
    if not len(s):
        return np.nan
    P = s.reshape(-1, 2)
    return 0.25 * ((P[:, 0].max() - P[:, 0].min()) + (P[:, 1].max() - P[:, 1].min()))


def side_reroute(D, sc, s, log):
    sg = L.SG[s]
    N = D[sid("sciatic_n", s)]
    V0 = N["V"].astype(float)
    C = L.centreline(N, n=160)
    S = L.arclen(C)
    # nerve radius per station: half the mean width of a 3 mm slab perpendicular to y (the nerve runs ~vertically below the
    # piriformis)
    rad = np.array([section_radius(V0, N["F"], p[1]) for p in C])
    rad = np.where(np.isfinite(rad), rad, np.nanmedian(rad))
    rad = np.clip(gaussian_filter1d(rad, 3), 2.5, 9.0)
    hip = D[sid("hip_bone", s)]["V"]; fem = D[sid("femur", s)]["V"]
    pir = D[sid("piriformis", s)]["V"]; qf = D[sid("quadratus_femoris", s)]["V"]
    lo = hip[np.argmin(hip[:, 1])]
    it_blob = hip[(np.linalg.norm(hip - lo, axis=1) < 55) & (hip[:, 1] < lo[1] + 40)]
    # exit: lowest piriformis vertex within 40 mm (xz) of the nerve at that height
    yp = pir[:, 1].min()
    near_p = pir[np.linalg.norm(pir[:, [0, 2]] - C[np.argmin(np.abs(C[:, 1] - yp))][[0, 2]], axis=1) < 40]
    y_exit = float(near_p[:, 1].min()) if len(near_p) else float(yp)
    i_exit = int(np.argmin(np.abs(C[:, 1] - y_exit)))
    i_end = int(np.searchsorted(S, S[-1] - FIX_END))
    it_top, it_bot = float(it_blob[:, 1].max()), float(it_blob[:, 1].min())
    Cs = gaussian_filter1d(C, 2.0, axis=0, mode="nearest")      # the raw bin centroids zig-zag on a flat band
    # ---- the ideal centre per station (rule), then a Viterbi chain through free space (cf. scripts/cryo/vhf_nerve_track.py)
    ideal, kind, itl = {}, {}, {}
    for i in range(i_exit + 1, i_end):
        hs = L.slab(it_blob, Cs[i, 1], 2.0)
        if len(hs) and Cs[i, 1] < it_top - 3:
            it_lat = float((sg * hs[:, 0]).max())
            ns = L.slab(V0, Cs[i, 1], 1.5)       # the nerve's own medial half-width at this level (its section is not round)
            hw = float(sg * Cs[i, 0] - (sg * ns[:, 0]).min()) if len(ns) else rad[i]
            xc = sg * (it_lat + MILLER_MM + hw)
            qs = L.slab(qf, Cs[i, 1], 2.0)
            qs = qs[np.abs(qs[:, 0] - xc) < 8] if len(qs) else qs
            zc = float(qs[:, 2].min() - rad[i] - 0.5) if len(qs) else float(Cs[i, 2])
            ideal[i] = (xc, zc); kind[i] = "ischial"; itl[i] = it_lat
    if not ideal:
        raise RuntimeError("no ischial station")
    i_is_top, i_is_bot = min(ideal), max(ideal)
    A = Cs[i_exit]; Bt = ideal[i_is_top]
    for i in range(i_exit + 1, i_is_top):      # exit -> ischial level: straight line, on the short rotators' posterior face
        t = (S[i] - S[i_exit]) / (S[i_is_top] - S[i_exit])
        x = A[0] + t * (Bt[0] - A[0]); z = A[2] + t * (Bt[1] - A[2])
        zf = post_face(D, s, Cs[i, 1], x)
        if zf is not None and t > 0.15:
            z = zf - rad[i] - 0.5
        ideal[i] = (x, z); kind[i] = "line"
    x_is, z_is = ideal[i_is_bot]
    for i in range(i_is_bot + 1, i_end):       # thigh: blend to the source course
        blend = np.clip((S[i] - S[i_is_bot]) / BLEND_MM, 0, 1)
        ideal[i] = ((1 - blend) * x_is + blend * Cs[i, 0], (1 - blend) * z_is + blend * Cs[i, 2]); kind[i] = "thigh"
    stations = list(range(i_exit, i_end + 1))
    cands, unary = [], []
    for i in stations:
        if i in (i_exit, i_end):
            cands.append(Cs[i][[0, 2]][None]); unary.append(np.zeros(1)); continue
        ix, iz = ideal[i]
        ids = sc.near_ids([ix, Cs[i, 1], iz], WIN + 5)
        xs, zs, occ = occupancy(sc, Cs[i, 1], ix, iz, ids)
        clr = distance_transform_edt(~occ) * GRID
        dep = distance_transform_edt(occ) * GRID
        X, Z = np.meshgrid(xs, zs, indexing="ij")
        X, Z, cl, dp = X[::2, ::2].ravel(), Z[::2, ::2].ravel(), clr[::2, ::2].ravel(), dep[::2, ::2].ravel()
        d = np.hypot(X - ix, Z - iz)
        sig = 3.0 if kind[i] == "ischial" else 5.0
        U = 0.5 * (d / sig) ** 2 + 1.0 * np.maximum(0.0, rad[i] - cl) + 12.0 * dp
        if kind[i] == "ischial":
            U += 10.0 * np.maximum(0.0, (itl[i] + MILLER_MM - 2.0) - (sg * X - rad[i]))
        keep = np.argsort(U)[:150]
        cands.append(np.c_[X[keep], Z[keep]]); unary.append(U[keep])
    # Viterbi: transition cost on the xz step between consecutive stations (~3 mm apart along the nerve)
    cost = unary[0].copy(); back = []
    for k in range(1, len(stations)):
        dxz = np.linalg.norm(cands[k][:, None, :] - cands[k - 1][None, :, :], axis=2)
        T = 0.5 * (dxz / 1.0) ** 2 + np.where(dxz > 8.0, 1e6, 0.0)
        tot = cost[None, :] + T
        j = np.argmin(tot, axis=1)
        back.append(j); cost = tot[np.arange(len(j)), j] + unary[k]
    path = [int(np.argmin(cost))]
    for k in range(len(stations) - 1, 0, -1):
        path.append(int(back[k - 1][path[-1]]))
    path = path[::-1]
    chosen = np.array([cands[k][path[k]] for k in range(len(stations))])
    targets = {}
    for k, i in enumerate(stations):
        if i in ideal:
            targets[i] = dict(kind=kind[i], y=float(Cs[i, 1]), ideal=[float(v) for v in ideal[i]], to=chosen[k].tolist(),
                              r=float(rad[i]), **({"it_lat": sg * itl[i]} if i in itl else {}))
    Dx = np.zeros(len(C)); Dz = np.zeros(len(C))
    Dx[stations] = chosen[:, 0] - Cs[stations, 0]; Dz[stations] = chosen[:, 1] - Cs[stations, 2]
    Dx = gaussian_filter1d(Dx, 1.0); Dz = gaussian_filter1d(Dz, 1.0)
    Dx[: i_exit + 1] = 0; Dz[: i_exit + 1] = 0; Dx[i_end:] = 0; Dz[i_end:] = 0
    disp = np.c_[Dx, np.zeros_like(Dx), Dz]
    # per-vertex: interpolate the station displacement by the vertex's projection onto the centreline
    seg_t = cKDTree(Cs)
    _, ii = seg_t.query(V0, k=2)
    a, b = Cs[ii[:, 0]], Cs[ii[:, 1]]
    w = np.clip(np.einsum("ij,ij->i", V0 - a, b - a) / np.maximum(np.einsum("ij,ij->i", b - a, b - a), 1e-9), 0, 1)
    dv = disp[ii[:, 0]] * (1 - w)[:, None] + disp[ii[:, 1]] * w[:, None]
    V1 = V0 + dv
    C1 = Cs + disp
    rep = dict(side=s, y_exit=y_exit, i_exit=i_exit, it_top=it_top, it_bot=it_bot, max_disp=float(np.linalg.norm(disp, axis=1).max()),
               stations={int(k): v for k, v in targets.items()})
    return V1, Cs, C1, disp, rep


def guards(D, sc, s, N, V1, C1, i_lo, i_hi, rep):
    fails = []
    Vs = N["V"].astype(float)
    # centreline outside muscle / bone on the moved stretch: depth of the centre in the occupied region of its slice
    ins = []
    for i in range(i_lo, i_hi, 3):
        p = C1[i]
        ids = sc.near_ids(p, 12)
        xs, zs, occ = occupancy(sc, p[1], p[0], p[2], ids)
        dep = distance_transform_edt(occ) * GRID
        c = occ.shape[0] // 2, occ.shape[1] // 2
        if dep[c] > CENTRE_TOL or any(sc.D[k]["sys"] == "bone" for k, _ in L.inside_ids(sc, p)):
            ins.append((round(float(p[1]), 1), [k for k, _ in L.inside_ids(sc, p)], round(float(dep[c]), 1)))
    if ins:
        fails.append(f"centre inside muscle/bone (depth > {CENTRE_TOL} mm) at {len(ins)} stations: {ins[:5]}")
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
    # length and turning, on the centreline smoothed over ~3 stations (the raw bin centroids of the source zig-zag)
    def smooth_c(V):
        return gaussian_filter1d(L.centreline(dict(V=V, F=N["F"]), n=160), 2.0, axis=0, mode="nearest")

    def turn(P):
        T = np.diff(P, axis=0); T /= np.linalg.norm(T, axis=1)[:, None] + 1e-9
        return np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", T[:-1], T[1:]), -1, 1)))
    c0, c1 = smooth_c(Vs), smooth_c(V1)
    l0, l1 = L.arclen(c0)[-1], L.arclen(c1)[-1]
    if abs(l1 - l0) / l0 * 100 > LEN_TOL:
        fails.append(f"length {l0:.0f} -> {l1:.0f} mm")
    if rep["max_disp"] > CAP:
        fails.append(f"displacement {rep['max_disp']:.1f} > {CAP}")
    a0, a1 = turn(c0), turn(c1)
    if a1.max() > max(KINK_DEG, a0.max() + 5):
        fails.append(f"kink {a1.max():.0f} deg (source {a0.max():.0f})")
    ang = a1
    rep.update(len_before=float(l0), len_after=float(l1), max_turn_deg=float(ang.max()), max_turn_src_deg=float(a0.max()), inside_after=ins)
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
