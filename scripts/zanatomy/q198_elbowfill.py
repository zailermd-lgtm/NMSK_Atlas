#!/usr/bin/env python3
"""Q198 READ-ONLY: soft-tissue fill profile through the elbow. Along the two-segment limb axis (upper arm line / forearm line through the elbow centre) the share of
the skin-enclosed, non-bone cross-section that is occupied by ANY muscle / tendon / ligament solid. A band where it drops to ~0 is an anatomical void
(upper-arm block and forearm block do not meet).  python3 scripts/zanatomy/q198_elbowfill.py [MODEL ...]  -> data/derived/Q198_elbowfill.json + build/q198_renders/elbow_fill_profiles.png"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q198_audit import load, MODELS, SkinField, Grid, female_sealers  # noqa: E402

DER = REPO / "data" / "derived"


def line_dist(P, c, a):
    d = P - c
    return np.linalg.norm(d - np.outer(d @ a, a), axis=1)


def run(key):
    S = load(key); kind = MODELS[key][2]
    sk = [s for s in S if s["sys"] == "skin" or s["id"] == "skin"] + female_sealers(key, S)
    skin = SkinField(sk, 3.0, close=1 if kind == "own" else 2)
    r = json.loads((DER / f"Q198_model_{key}.json").read_text())
    out = {}
    for side in ("l", "r"):
        j = next((x for x in r["junctions"] if x["name"] == "elbow" and x["side"] == side), None)
        if j is None:
            out[side] = {"note": "no elbow bones in this model"}; continue
        c = np.asarray(j["centre_mm"]); ea = j["elbow_angles"]
        h = np.asarray(ea["humerus_axis"]); f = np.asarray(ea["forearm_axis"])
        g = Grid(c - 135, c + 135, 2.0)
        soft = np.zeros(g.shape, bool); bone = np.zeros(g.shape, bool)
        for s in S:
            if s["side"] not in (side,) or s["sys"] not in ("muscle", "bone", "joint", "insertion", "tendon", "ligament"):
                continue
            if np.linalg.norm(s["v"] - c, axis=1).min() > 175:
                continue
            if s["sys"] == "bone":
                bone |= g.solid(s["v"], s["f"], close=1)
            elif s["sys"] == "muscle":
                soft |= g.solid(s["v"], s["f"], close=1)
            else:
                soft |= g.solid(s["v"], s["f"], close=1)
        X = np.stack(np.meshgrid(*[np.arange(n) for n in g.shape], indexing="ij"), -1).reshape(-1, 3) * g.h + g.lo
        sd = skin.signed(X)
        inside = (sd < -1.0).reshape(g.shape)
        tissue = (inside & ~bone)
        P = X
        hb = h / np.linalg.norm(h); fb = f / np.linalg.norm(f)
        dh = P - c
        th, tf_ = dh @ hb, dh @ fb
        # upper arm (proximal of the joint plane): coordinate = -t along h; forearm: along f
        ua = (th < 0) & (line_dist(P, c, hb) < 55)
        fa = (tf_ >= 0) & (line_dist(P, c, fb) < 55)
        rows = []
        for t in np.arange(-110, 111, 4.0):
            if t < 0:
                sel = ua & (np.abs(th - t) < 2.0)
            else:
                sel = fa & (np.abs(tf_ - t) < 2.0)
            sel = sel.reshape(g.shape) & tissue
            n = int(sel.sum())
            rows.append((float(t), n, float((sel & soft).sum() / n) if n > 200 else np.nan))
        rows = np.array(rows)
        ok = ~np.isnan(rows[:, 2])
        near = ok & (np.abs(rows[:, 0]) <= 60)
        low = (rows[:, 2] < 0.35) & ok
        # longest run of low-fill slices within +-70 mm
        best, cur = 0, 0
        for t, lo in zip(rows[:, 0], low):
            if abs(t) <= 70 and lo:
                cur += 4
                best = max(best, cur)
            else:
                cur = 0
        out[side] = {"min_fill_within_60mm": round(float(np.nanmin(rows[near, 2])), 3) if near.any() else None, "median_fill_within_60mm": round(float(np.nanmedian(rows[near, 2])), 3) if near.any() else None,
                     "void_band_mm_fill_lt_0.35": best, "profile": [[round(a, 0), round(b, 3) if not np.isnan(b) else None] for a, _, b in rows]}
        print(key, side, out[side]["min_fill_within_60mm"], out[side]["median_fill_within_60mm"], out[side]["void_band_mm_fill_lt_0.35"], flush=True)
    return out


def main():
    keys = sys.argv[1:] or list(MODELS)
    p = DER / "Q198_elbowfill.json"
    res = json.loads(p.read_text()) if p.exists() else {}
    for k in keys:
        res[k] = run(k)
        p.write_text(json.dumps(res))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for i, side in enumerate(("l", "r")):
        for k, lab in [("own_m", "own male"), ("own_f", "own female"), ("z_male", "Z male base"), ("z_base_f", "Z generic (f)"), ("z_male_fit", "Z fit his"), ("z_female_fit", "Z fit her")]:
            if k in res and "profile" in res[k].get(side, {}):
                pr = np.array([[a, np.nan if b is None else b] for a, b in res[k][side]["profile"]])
                ax[i].plot(pr[:, 0], pr[:, 1], label=lab, lw=1.6)
        ax[i].set_title(f"{'left' if side=='l' else 'right'} elbow: share of skin-enclosed non-bone cross-section occupied by muscle/tendon"); ax[i].set_xlabel("mm along the arm (negative = upper arm, positive = forearm)"); ax[i].axvline(0, c="k", lw=0.5)
        ax[i].title.set_fontsize(8)
    ax[0].set_ylabel("fill fraction"); ax[0].legend(fontsize=7)
    (REPO / "build" / "q198_renders").mkdir(parents=True, exist_ok=True)
    fig.savefig(REPO / "build" / "q198_renders" / "elbow_fill_profiles.png", dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    main()
