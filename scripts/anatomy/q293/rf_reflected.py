#!/usr/bin/env python3
"""Q293: the REFLECTED (indirect) head of rectus femoris, RULE-BASED, fitted onto each page's own hip bone and its own rectus femoris.

No source we hold has a mesh of it: Z-Anatomy lists "Reflected head of rectus femoris" (TA2 2616) only as a name (no OB / ME datablock
in Startup.blend, checked Q293), BodyParts3D has FMA22430 rectus femoris only, CVH (Wu 2015) and the HRA VH_F set have no thigh muscle
heads. So the head is BUILT here from cited dimensions on the page's own bones, and badged RULE-BASED with its volume:

  footprint  on the lateral wall of the ilium just above the superior acetabular rim, from the posterior apex (21.0 mm posterior to the
             12:30 labral position, Gursoy 2024) forward to 1:30, cranio-caudal width 16.8 mm (Ryan 2014: 47.7 x 16.8 mm; Atzmon 2019:
             footprint alone 38.1 mm long, 22.3 mm cranio-caudal); it "fans out posteriorly, becoming thinner and wider" (Atzmon 2019)
  free part  "becomes a free tendon overlying the acetabular bone as it travels anteriorly and distally towards its muscular
             attachment" (Atzmon 2019), joining the direct head below the AIIS: width 10.9 mm and thickness 6.9 mm at the confluence of
             both heads (Atzmon 2019); total footprint + free portion 55.3 mm (Atzmon 2019)
  deep course: its tendon continues as the deep intramuscular tendon of the muscle (Hasselman 1995) -- not modelled beyond the
             confluence (it lies inside the existing rectus femoris mesh)

The clock face is the arthroscopic one (12 o'clock superior, 3 o'clock anterior on both hips; Hapa 2013 places the indirect head at
12 o'clock and the AIIS margins at 1-2:30). Joint centre = the page's pose-rig hip centre (femoral-head sphere fit). Nothing is tuned to
make a number come out; every derived value (length, footprint, angle between the heads, volume, bone penetration) is measured on the
result and reported.

    python3 scripts/anatomy/q293/rf_reflected.py build [--keys base_m,...] [--out /dev/shm/q293/work]   # meshes (.npz) + data/derived/Q293_rf_reflected_head.json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
REPORT = REPO / "data/derived/Q293_rf_reflected_head.json"

CITE = {
    "ryan2014": {"cite": "Ryan JM, Harris JD, Graham WC, Virk SS, Ellis TJ. Origin of the direct and reflected head of the rectus femoris: an anatomic study. Arthroscopy 2014;30(7):796-802",
                 "pmid": "24793210", "doi": "10.1016/j.arthro.2014.03.003",
                 "quote": "The average dimensions of the footprint of the direct head of the rectus femoris were 13.4 mm (±1.7) × 26.0 mm (±4.1), whereas the dimensions of the reflected head footprint were 47.7 mm (±4.4) × 16.8 mm (±2.2)."},
    "atzmon2019": {"cite": "Atzmon R, Sharfman ZT, Atoun E, Sampson TG, Amar E, Rath E. The anatomical properties of the indirect head of the rectus femoris tendon: a cadaveric study with clinical significance for labral reconstruction surgery. Arch Orthop Trauma Surg 2020;140(1):85-92",
                   "pmid": "31734733", "doi": "10.1007/s00402-019-03293-6",
                   "quote": "The width and thickness at the confluence of both heads were 10.9 mm and 6.9 mm, respectively. The mean total length of the footprint and \"free portion\" of the IHRF was 55.3 mm"},
    "atzmon2019b": {"cite": "Atzmon R et al. 2020 (as above)", "pmid": "31734733", "doi": "10.1007/s00402-019-03293-6",
                    "quote": "The origin of the IHRF on the acetabulum fans out posteriorly, becoming thinner and wider as the origin travels posteriorly. The tendon footprint is firmly attached on the lateral wall of the ilium and becomes a free tendon overlying the acetabular bone as it travels anteriorly and distally towards its muscular attachment."},
    "gursoy2024": {"cite": "Gursoy S, Bessa F, Dandu N, et al. Indirect Head of the Rectus Femoris Tendon as a Graft for Segmental Hip Labral Reconstruction. Am J Sports Med 2024;52(7):1753-1764",
                   "pmid": "38761016", "doi": "10.1177/03635465241251824",
                   "quote": "The centroid and posterior apex of the indirect rectus femoris attachment are respectively located 10.3 ± 2.6 mm and 21.0 ± 6.5 mm posteriorly, 2.5 ± 7.8 mm and 0.7 ± 8.0 mm superiorly, and 5.0 ± 2.8 mm and 22.2 ± 4.4 mm laterally to the 12:30 labral position."},
    "hapa2013": {"cite": "Hapa O, Bedi A, Gursan O, et al. Anatomic footprint of the direct head of the rectus femoris origin. Arthroscopy 2013;29(12):1932-40",
                 "pmid": "24140143", "doi": "10.1016/j.arthro.2013.08.023",
                 "quote": "On the clock face, the lateral margin (1-o'clock to 1:30 position) and medial margin (2-o'clock to 2:30 position) of the AIIS and the indirect head of the rectus (12 o'clock) were consistent for all specimens."},
    "hasselman1995": {"cite": "Hasselman CT, Best TM, Hughes C, Martinez S, Garrett WE. An explanation for various rectus femoris strain injuries using previously undescribed muscle architecture. Am J Sports Med 1995;23(4):493-9",
                      "pmid": "7573663", "doi": "10.1177/036354659502300421",
                      "quote": "The proximal tendon is composed of a superficial, anterior portion from the direct head, and a deep intramuscular portion from the indirect head."},
    "benes2025": {"cite": "Benes M, Bartak V, Uhlik J, et al. Surgical anatomy of the anterior musculocapsular complex of the hip. Anat Cell Biol 2025;58(2):155-165",
                  "pmid": "40194840", "doi": "10.5115/acb.24.329",
                  "quote": "Macroscopically, the rectus femoris muscle contributed to the articular capsule exclusively through its reflected head."},
}
LIT = {"footprint_len_mm": (38.1, "atzmon2019b / Atzmon footprint alone 38.1 mm; Ryan 47.7 ± 4.4"), "footprint_width_mm": (16.8, "ryan2014"),
       "confluence_width_mm": (10.9, "atzmon2019"), "confluence_thick_mm": (6.9, "atzmon2019"), "total_len_mm": (55.3, "atzmon2019"),
       "apex_posterior_mm": (21.0, "gursoy2024")}

W_FOOT, W_CONF, T_FOOT_POST, T_FOOT_ANT, T_CONF = 16.8, 10.9, 2.0, 3.0, 6.9
APEX_POST, ANT_CLOCK = 21.0, 1.5           # mm posterior of 12:30 (Gursoy); anterior end of the footprint (clock hours, Hapa AIIS lateral margin 1-1:30)


def unit(v):
    v = np.asarray(v, float); n = np.linalg.norm(v, axis=-1, keepdims=True); return v / np.where(n == 0, 1, n)


class Bone:
    def __init__(self, v, f):
        import trimesh
        self.t = trimesh.Trimesh(v, f, process=False)
        self.v = np.asarray(v, float)
        P, fi = trimesh.sample.sample_surface_even(self.t, 40000, seed=293) if len(v) > 0 else (None, None)
        self.P = np.asarray(P); self.N = self.t.face_normals[fi]
        from scipy.spatial import cKDTree
        self.T = cKDTree(self.P)
        self.watertight = bool(self.t.is_watertight)

    def nearest(self, X):
        d, i = self.T.query(np.atleast_2d(X)); return self.P[i], self.N[i], d

    def inside_depth(self, X):
        """> 0 = depth inside the bone (mm), by the nearest sample's outward normal (robust on open meshes)"""
        p, n, d = self.nearest(X)
        s = np.einsum("ij,ij->i", np.atleast_2d(X) - p, n)
        return np.where(s < 0, d, -d)


def frame(side):
    L = np.array([1.0 if side == "r" else -1.0, 0, 0]); S = np.array([0, 1.0, 0]); A = np.array([0, 0, 1.0])
    return L, S, A


def clock_dir(h, S, A):
    t = np.radians(h * 30.0)              # 12 o'clock = superior, 3 o'clock = anterior (both hips)
    return np.cos(t) * S + np.sin(t) * A


def rim(bone, H, side):
    """per clock hour: the most lateral hip-bone point near the acetabular opening (the rim crest) and the socket radius"""
    L, S, A = frame(side)
    d = np.linalg.norm(bone.P - H, axis=1)
    rho = float(np.percentile(d[d < 45], 8))                  # socket (lunate surface) radius about the femoral-head centre
    out = {}
    for h in np.arange(9.0, 15.01, 0.25):
        u = clock_dir(h % 12 if h != 12 else 12, S, A)
        X = bone.P - H; proj = X - np.outer(X @ L, L); r = np.linalg.norm(proj, axis=1)
        ang = np.degrees(np.arccos(np.clip((proj @ u) / np.maximum(r, 1e-9), -1, 1)))
        m = (ang < 8) & (r > rho) & (r < rho + 10) & (d < rho + 16)
        if m.sum() < 5:
            continue
        lat = X[m] @ L
        k = np.argmax(lat)
        out[round(float(h), 2)] = (bone.P[m][k], float(r[m][k]))
    return rho, out


def build_side(key, side, bone, rf_v, H, rep):
    L, S, A = frame(side)
    rho, R = rim(bone, H, side)
    hs = sorted(R)
    # 12:30 labral position -> posterior apex 21 mm posterior along the rim (Gursoy 2024)
    r1230 = R[min(hs, key=lambda h: abs(h - 12.5))][1]                 # rim radius at 12:30 (mm, about the femoral-head centre)
    h_apex = 12.5 - np.degrees(APEX_POST / r1230) / 30.0               # 21.0 mm of rim arc posterior to 12:30 (Gursoy 2024)
    h_apex = min(hs, key=lambda h: abs(h - h_apex))
    h_ant = 12 + ANT_CLOCK
    band = [h for h in hs if h_apex <= h <= h_ant]
    # footprint centre line: from the rim crest outward (away from the socket centre, on the lateral wall) by half the width
    # rim crest radius / lateral offset per clock position, median-smoothed (the coarse meshes give a jagged crest)
    rr = np.array([R[h][1] for h in band]); ll = np.array([(R[h][0] - H) @ L for h in band])
    med = lambda a: np.array([np.median(a[max(0, i - 2):i + 3]) for i in range(len(a))])
    rr, ll = med(rr), med(ll)
    cl, nrm, wid, thk = [], [], [], []
    for j, h in enumerate(band):
        u = clock_dir(h, S, A)
        w = W_FOOT * (1.15 - 0.15 * j / max(1, len(band) - 1))           # wider posteriorly (Atzmon)
        t = T_FOOT_POST + (T_FOOT_ANT - T_FOOT_POST) * j / max(1, len(band) - 1)   # thinner posteriorly (Atzmon)
        q, n, _ = bone.nearest(H + L * (ll[j] - 3.0) + u * (rr[j] + 1.0 + w / 2))   # just above the rim, on the lateral wall
        cl.append(q[0]); nrm.append(unit(n[0])); wid.append(w); thk.append(t)
    cl, nrm = np.array(cl), np.array(nrm)
    sm = lambda a: np.array([a[max(0, i - 2):i + 3].mean(0) for i in range(len(a))])
    cl, nrm = sm(cl), unit(sm(nrm))
    cl = cl + nrm * (np.array(thk)[:, None] / 2 + 0.4)
    # AIIS: the most anterior hip-bone point between 1:30 and 2:30, 5-35 mm outside the socket radius
    X = bone.P - H; proj = X - np.outer(X @ L, L); r = np.linalg.norm(proj, axis=1)
    hh = (np.degrees(np.arctan2(proj @ A, proj @ S)) / 30.0) % 12
    m = (hh > 1.25) & (hh < 2.75) & (r > rho + 5) & (r < rho + 40) & ((X @ L) > -15)
    aiis = bone.P[m][np.argmax(X[m] @ A)]
    # confluence with the direct head: on this page's own rectus femoris, its centre line at the level 20 mm below the AIIS
    top = rf_v[rf_v[:, 1] > rf_v[:, 1].max() - 120]
    yc = min(aiis[1] - 20.0, float(rf_v[:, 1].max()) - 10.0)
    sl = rf_v[np.abs(rf_v[:, 1] - yc) < 4.0]
    if len(sl) < 10:
        sl = top[np.argsort(-top[:, 1])[:60]]
    C = sl.mean(0)
    c_rf, _, Vt = np.linalg.svd(top - top.mean(0), full_matrices=False); ax_rf = unit(Vt[0] if Vt[0][1] > 0 else -Vt[0])   # direct head / RF axis, pointing up
    # free part: from the anterior end of the footprint, forward and down to C, bowed away from the bone (Bezier)
    E = cl[-1]; tE = unit(cl[-1] - cl[-2])
    D = np.linalg.norm(C - E)
    b1 = E + tE * D * 0.45 + nrm[-1] * 3.0; b2 = C + ax_rf * D * 0.45
    ts = np.linspace(0, 1, 14)[1:]
    free = np.array([(1 - t) ** 3 * E + 3 * (1 - t) ** 2 * t * b1 + 3 * (1 - t) * t ** 2 * b2 + t ** 3 * C for t in ts])
    path = np.vstack([cl, free])
    nF = len(cl)
    W = np.r_[wid, np.interp(ts, [0, 1], [wid[-1], W_CONF])]
    Tk = np.r_[thk, np.interp(ts, [0, 1], [thk[-1], T_CONF])]
    # frames: thin direction = bone normal on the footprint, parallel-transported along the free part
    tang = unit(np.gradient(path, axis=0))
    Nn = [nrm[0]]
    for i in range(1, len(path)):
        n = nrm[i] if i < nF else Nn[-1]
        n = unit(n - tang[i] * (n @ tang[i])); Nn.append(n)
    Nn = np.array(Nn); Bn = unit(np.cross(tang, Nn))
    K = 16; th = np.linspace(0, 2 * np.pi, K, endpoint=False)
    V = []
    for i in range(len(path)):
        for a in th:
            V.append(path[i] + Bn[i] * np.cos(a) * W[i] / 2 + Nn[i] * np.sin(a) * Tk[i] / 2)
    V = np.array(V); F = []
    for i in range(len(path) - 1):
        for k in range(K):
            a, b, c, d = i * K + k, i * K + (k + 1) % K, (i + 1) * K + (k + 1) % K, (i + 1) * K + k
            F += [[a, b, c], [a, c, d]]
    c0 = len(V); V = np.vstack([V, path[0], path[-1]])
    for k in range(K):
        F.append([c0, (k + 1) % K, k]); n0 = (len(path) - 1) * K; F.append([c0 + 1, n0 + k, n0 + (k + 1) % K])
    F = np.array(F)
    # keep it out of the bone: push any vertex inside the hip bone back to its surface + 0.3 mm (stated, measured before / after)
    dep0 = bone.inside_depth(V)
    for _ in range(3):
        dep = bone.inside_depth(V); bad = dep > -0.3
        if not bad.any():
            break
        p, n, _ = bone.nearest(V[bad]); V[bad] = p + unit(n) * 0.3
    dep1 = bone.inside_depth(V)
    import trimesh
    tm = trimesh.Trimesh(V, F, process=False)
    if tm.volume < 0:
        F = F[:, ::-1]; tm = trimesh.Trimesh(V, F, process=False)
    seglen = lambda P: float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
    free_dir = unit(C - free[-4])                            # the reflected tendon's direction as it reaches the confluence
    ang = float(np.degrees(np.arccos(np.clip(abs(free_dir @ ax_rf), -1, 1))))
    rfd = np.linalg.norm(rf_v - aiis, axis=1).min()
    out = {"socket_radius_mm": round(rho, 1), "clock_apex": round(h_apex, 2), "clock_anterior_end": h_ant,
           "footprint_len_mm": round(seglen(cl), 1), "footprint_width_mm": [round(min(wid), 1), round(max(wid), 1)],
           "free_len_mm": round(seglen(np.vstack([E, free])), 1), "total_len_mm": round(seglen(path), 1),
           "confluence_width_thick_mm": [W_CONF, T_CONF], "volume_cm3": round(float(tm.volume) / 1000, 2),
           "watertight": bool(tm.is_watertight), "aiis_mm": np.round(aiis, 1).tolist(), "confluence_mm": np.round(C, 1).tolist(),
           "rf_nearest_to_aiis_mm": round(float(rfd), 1),
           "angle_reflected_vs_direct_head_deg": round(ang, 1),
           "bone_penetration": {"verts_inside_gt_0_5mm_before_push_pct": round(100 * float((dep0 > 0.5).mean()), 1),
                                "verts_inside_gt_0_5mm_after_pct": round(100 * float((dep1 > 0.5).mean()), 2),
                                "max_depth_after_mm": round(float(max(0.0, dep1.max())), 2)},
           "hip_bone_watertight": bone.watertight}
    rep[f"{key}_{side}"] = out
    return V, F, out


def build(keys, outdir):
    import model as Mo
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    rep["_README"] = ["Q293: rule-based reflected head of rectus femoris per page / side, scripts/anatomy/q293/rf_reflected.py; measured on the result, nothing tuned"]
    rep["cites"] = CITE; rep["literature_targets"] = {k: {"value": v[0], "src": v[1]} for k, v in LIT.items()}
    for key in keys:
        M = Mo.Model(key); B = M.bones()
        rig = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())["rig"]; J = {j["id"]: j for j in rig["joints"]}
        mesh = {}
        for side in "rl":
            hb = B[f"hip_bone_{side}"]; bone = Bone(hb["v"], hb["f"])
            rf = [x for x in M.S if x["id"] in (f"rectus_femoris_{side}", f"zan_rectus_femoris_{side}")]
            assert len(rf) == 1, (key, side, [x["id"] for x in rf])
            V, F, o = build_side(key, side, bone, np.asarray(rf[0]["v"], float), np.array(J[f"hip_{side}"]["c"]), rep)
            mesh[side] = (V, F)
            print(key, side, json.dumps(o))
        np.savez(outdir / f"rf_reflected_{key}.npz", vr=mesh["r"][0], fr=mesh["r"][1], vl=mesh["l"][0], fl=mesh["l"][1])
    REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build"]); ap.add_argument("--keys", default=",".join(KEYS))
    ap.add_argument("--out", default="/dev/shm/q293/work")
    a = ap.parse_args()
    build(a.keys.split(","), a.out)


if __name__ == "__main__":
    main()
