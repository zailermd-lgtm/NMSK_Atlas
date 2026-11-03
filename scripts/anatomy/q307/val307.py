"""Q307 validation of the transfer, run on the SUBSTITUTED page before any page is built.

What it has to prove, and nothing else:
  1. the owner's nerve now exists on BOTH Imaging pages and on BOTH sides, in the forearm, radial of the radius,
     continuous with that page's own musculocutaneous nerve and apposed to its own brachioradialis;
  2. the three half-done lower-limb nerves now meet their own branches -- the plantar nerves were 436.6 mm
     (Imaging M, right) and 370.4 mm (Imaging F, left) from their parent tibial nerve;
  3. nothing leaves the body and nothing gains bone penetration of its own (Q299's two validated tests);
  4. mesh realness: mean dihedral against the CVH references 31.7 / 27.6 / 29.5 deg.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
for p in ("q241", "q299", "q304", "q307"):
    sys.path.insert(0, str(REPO / "scripts" / "anatomy" / p))
import place307 as P        # noqa: E402
import contain299 as CT     # noqa: E402
import xfer304 as X4        # noqa: E402

NERVES = Path("/dev/shm/q307/nerves")
OUT = REPO / "data/derived/Q307_nerve_validation.json"
CVH = (31.7, 27.6, 29.5)


def substituted(key):
    """the page's structures with this round's transferred meshes in place -- the page as it WILL be built."""
    m = P.MODEL.Model(key)
    z = np.load(NERVES / f"{key}_nerves.npz")
    items = json.loads((NERVES / f"{key}_nerves.json").read_text())
    byid = {x["id"]: x for x in m.S}
    added = []
    for i, rec in items.items():
        v = np.asarray(z[i + "__v"], float); f = np.asarray(z[i + "__f"], np.int64)
        if i in byid:
            byid[i]["v"], byid[i]["f"] = v, f
        else:
            x = dict(id=i, name=rec["name"], sys="nerve", side=rec["side"], v=v, f=f,
                     src=("xfer_zan2vh" + ("m" if key == "own_m" else "f") + "_nerves_q307"),
                     rec=rec.get("rec_combined") or {}, idx=len(m.S))
            m.S.append(x); byid[i] = x; added.append(i)
    return m, byid, items, added


def forearm_frame(byid, side):
    rv = np.vstack([byid[k]["v"] for k in byid if k == f"radius_{side}"])
    uv = np.vstack([byid[k]["v"] for k in byid if k == f"ulna_{side}"])
    hv = np.vstack([byid[k]["v"] for k in byid if k == f"humerus_{side}"])
    c = rv.mean(0); u = np.linalg.svd(rv - c, full_matrices=False)[2][0]
    t = (rv - c) @ u
    e0, e1 = c + u * t.min(), c + u * t.max()
    T = cKDTree(hv)
    if T.query(e0[None])[0][0] > T.query(e1[None])[0][0]:
        u, t = -u, -t
    L0 = c + u * t.min(); Ln = float(t.max() - t.min())
    w = c - uv.mean(0); w -= (w @ u) * u; w /= np.linalg.norm(w)
    return c, u, w, L0, Ln


def run(keys=("own_m", "own_f")):
    out = {}
    for key in keys:
        m, byid, items, added = substituted(key)
        rec = dict(page=key, n_substituted=len(items), n_new_ids=len(added), checks={})
        # --- 1. the owner's nerve
        lac = {}
        for side in ("l", "r"):
            i = f"zan_lateral_antebrachial_cutaneous_nerve_{side}"
            if i not in byid:
                lac[side] = dict(present=False); continue
            L = P.samples(byid[i]["v"], byid[i]["f"], 2.0)
            c, u, w, L0, Ln = forearm_frame(byid, side)
            tL = ((L - L0) @ u) / Ln
            rad = (L - c) @ w
            mcn = byid.get(f"musculocutaneous_n_{side}")
            br = byid.get(f"brachioradialis_{side}")
            d_mcn = float(cKDTree(P.samples(mcn["v"], mcn["f"], 1.0)).query(L)[0].min()) if mcn else None
            dbr = cKDTree(P.samples(br["v"], br["f"], 1.0)).query(L)[0] if br else None
            lac[side] = dict(present=True, id=i, source=byid[i].get("src"),
                             t_along_forearm=[round(float(tL.min()), 3), round(float(tL.max()), 3)],
                             radial_coord_p50_mm=round(float(np.median(rad)), 1),
                             ulna_radial_coord_p50_mm=round(float(np.median((np.vstack([byid[f"ulna_{side}"]["v"]]) - c) @ w)), 1),
                             d_musculocutaneous_mm=round(d_mcn, 2) if d_mcn is not None else None,
                             d_brachioradialis_p50_mm=round(float(np.median(dbr)), 2) if dbr is not None else None,
                             dihedral_mean_deg=round(X4.dihedral_mean(byid[i]["v"], byid[i]["f"]), 1))
        rec["checks"]["lateral_antebrachial_cutaneous"] = lac
        # --- 2. the repaired lower-limb nerves and their branches
        pairs = [("lateral_plantar_n", "tibial_n"), ("medial_plantar_n", "tibial_n"),
                 ("saphenous_n", "femoral_n"), ("femoral_n_anterior_cutaneous_branches", "femoral_n")]
        cont = {}
        for child, parent in pairs:
            for side in ("l", "r"):
                ci, pi = f"{child}_{side}", f"{parent}_{side}"
                if ci not in byid or pi not in byid:
                    continue
                C = P.samples(byid[ci]["v"], byid[ci]["f"], 2.0)
                PA = P.samples(byid[pi]["v"], byid[pi]["f"], 1.0)
                cont[f"{ci} -> {pi}"] = round(float(cKDTree(PA).query(C)[0].min()), 2)
        rec["checks"]["continuity_mm"] = cont
        # --- 3. Q299's two tests, on the substituted page
        BM = CT.build(key, 2.0)
        val = CT.validate(BM)
        rec["checks"]["body_mask_validates"] = val["ok"]
        rng = np.random.default_rng(7)
        outside, inbone = {}, {}
        for i in sorted(items):
            V = byid[i]["v"]; F = byid[i]["f"]
            ins = BM["g"].inside(BM["body"], V)
            if not ins.all():
                d = BM["skin_tree"].query(V[~ins])[0]
                outside[i] = dict(n_outside=int((~ins).sum()), worst_mm=round(float(d.max()), 2))
            fb = X4.in_bone_frac(np.asarray(V, float), np.asarray(F, np.int64), BM["bones"], rng)
            if fb > 0.05:
                inbone[i] = round(fb, 4)
        rec["checks"]["leaves_the_body"] = outside
        rec["checks"]["in_bone_frac_over_5pct"] = inbone
        del BM
        # --- 4. realness
        dih = {i: round(X4.dihedral_mean(byid[i]["v"], byid[i]["f"]), 1) for i in sorted(items)}
        rec["checks"]["dihedral"] = dict(cvh_references_deg=list(CVH),
                                         min=min(dih.values()), max=max(dih.values()),
                                         median=round(float(np.median(list(dih.values()))), 1), per_structure=dih)
        out[key] = rec
        print(f"=== {key}: {len(items)} substituted ({len(added)} new ids); body mask validates {val['ok']}; "
              f"{len(outside)} leave the body; {len(inbone)} over 5 % in bone; dihedral "
              f"{rec['checks']['dihedral']['min']}-{rec['checks']['dihedral']['max']} deg", flush=True)
        for s, r in lac.items():
            print(f"    LACN {s}: {r}", flush=True)
        for k2, v2 in sorted(cont.items()):
            print(f"    {k2:62s} {v2} mm", flush=True)
        del m
    OUT.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print("->", OUT)


if __name__ == "__main__":
    run(tuple(sys.argv[1:]) or ("own_m", "own_f"))
