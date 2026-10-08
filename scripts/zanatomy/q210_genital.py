#!/usr/bin/env python3
"""Q210 (1): the male genital structures lie OUTSIDE the Q207 / Q208 urogenital skin.  Decision (numbers in Q210_genital_male.json): the SKIN follows the structures.
Q207 refit the two urogenital skin halves to the Z-SOURCE volume (37.1 k mm3 each) while the fitted structures kept the fit scale of the person (testes +30 % volume, spongiosum +22 %, penis length +20 %, all of them inside
his own CT skin); moving the structures with the Q207 skin warp would shorten the penis by 8-37 % (glans 45 -> 28 mm) and shrink the testes by 20 %.  Here the Q207 refit (q207_uro.refit_split: ONE similarity +
harmonic residual onto the fixed neighbours, nodes at the seam) is re-run with the volume target of the person's own genital scale: the smallest target (2 k mm3 grid) at which every listed structure is enclosed
(audit measure: no vertex > 3 mm outside the Q198 envelope; 1 mm envelope: <= 12 % of the vertices > 0.5 mm, none > 5 mm outside), then the Q208 rim weld (q208_uro.weld) closes the border steps again.
    python3 scripts/zanatomy/q210_genital.py [T_mm3 ...]        (no argument: search the target)"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q210_core as K  # noqa: E402
from scripts.zanatomy import q207_uro as U7  # noqa: E402
from scripts.zanatomy import q208_uro as U8  # noqa: E402


def refit(pg, raw, V0, T, log=lambda *a: None):
    ids = list(K.UROS)
    oth = [i for i in pg.skin_ids if i not in ids and i in raw.S]
    out, rep = U7.refit_split({i: raw.v(i) for i in ids}, {i: pg.v(i) for i in ids}, {i: pg.f(i) for i in ids}, {i: raw.v(i) for i in oth}, {i: V0[i] for i in oth},
                              others_faces={i: pg.f(i) for i in oth}, vol_target=T, log=log)
    V = dict(V0)
    V.update(out)
    rawv = {i: raw.v(i) for i in pg.skin_ids if i in raw.S}
    faces = {i: pg.f(i) for i in pg.skin_ids}
    V2, info = U8.weld(faces, rawv, V, list(rawv), w_pull=20.0, lam_s=0.3, log=lambda *a: None)
    rep["weld"] = {i: [round(float(np.linalg.norm(V2[i] - V[i], axis=1).max()), 2), round(float(np.linalg.norm(V2[i] - V[i], axis=1).mean()), 2)] for i in info["free"]}
    return V2, rep


def passes(rows, main_ids=K.GEN_MAIN, fine_tol=12.0, fine_max=5.0):
    """enclosed: no vertex > 3 mm outside the Q198 envelope (audit measure) and, on the 1 mm envelope, <= 12 % of the vertices > 0.5 mm / none > 5 mm outside (the Q206 skin the structures were fitted to: 0-17 % / 4 mm).
    The external pudendal vessels (groin, drawn from the fixed inguinal / thigh patches) are outside the urogenital patch domain: reported, not part of the test."""
    bad = {i: r for i, r in rows.items() if i in main_ids and (r["audit_gt3_pct"] > 0.0 or r.get("fine_gt0.5_pct", 0) > fine_tol or r.get("fine_max_mm", 0) > fine_max)}
    return not bad, bad


def evaluate(pg, V, with_fine=True):
    sf = K.coarse(pg, V)
    fine = K.fine_box(pg, V, sf) if with_fine else None
    return sf, K.outside_rows(pg, sf, fine=fine)


def search(pg, raw, V0, grid=(48000, 50000, 52000, 54000, 56000, 58000, 60000), log=print):
    trials = {}
    lo, hi = 0, len(grid) - 1
    best = None
    # bisection over the (monotone) target: the smallest passing one
    while lo <= hi:
        mid = (lo + hi) // 2
        T = grid[mid]
        t = time.time()
        V, rep = refit(pg, raw, V0, T)
        sf, rows = evaluate(pg, V)
        ok, bad = passes(rows)
        trials[T] = dict(ok=ok, volumes=rep["volumes"], scale=rep["scale"], bad={i[4:]: [r["audit_gt3_pct"], r["audit_max_mm"], r.get("fine_gt0.5_pct")] for i, r in bad.items()})
        log(f"T={T}: volumes {rep['volumes']} pass={ok} bad={list(trials[T]['bad'])}  [{time.time() - t:.0f}s]")
        if ok:
            best = (T, V, rep)
            hi = mid - 1
        else:
            lo = mid + 1
    return best, trials


if __name__ == "__main__":
    pg, raw = K.load()
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    if len(sys.argv) > 1:
        T = int(sys.argv[1])
        V, rep = refit(pg, raw, V0, T)
        sf, rows = evaluate(pg, V)
        print(T, rep["volumes"], rep["weld"], passes(rows)[0], {i[4:20]: (r["audit_gt3_pct"], r["audit_max_mm"], r["fine_gt0.5_pct"]) for i, r in rows.items()})
    else:
        best, trials = search(pg, raw, V0)
        T, V, rep = best
        pickle.dump((V, dict(T=T, rep=rep, trials=trials)), open(K.state_path("genital"), "wb"))
        print("chosen T", T)
