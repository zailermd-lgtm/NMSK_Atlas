"""A learned nerve-section scorer, trained on the female's own verified sciatic sections (vhf_nerve_patches.py).

    python3 scripts/cryo/vhf_nerve_scorer.py train --patches SCRATCH/nerve_patches.npz --out SCRATCH/nerve_scorer.joblib \
        --report data/derived/vhf_nerve_scorer_report.json

Features of a 48 x 48 px (16 mm) RGB patch: the red channel mean-pooled to 12 x 12 (the fascicle pattern and the
patch's shape), colour means, red-channel residual energy at 1 / 2 / 4 px scales (speckle vs cells vs lobules),
mean gradient, and a 4-ring radial profile of the red channel (a compact oval in fat is bright-centre / brighter-
rim). A histogram gradient-boosting classifier is fitted on all 8 rotations/flips of every patch; validation
holds out every fifth LEVEL (not every fifth patch, which would leak neighbouring 1 mm sections). The scorer
gives the tracker a probability per candidate blob and a dense probability map over the corridor where the
hand-crafted detector finds nothing. Nothing here is anatomy; it is how a verified nerve section looks on her.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

P = 24
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution via the NCI Imaging Data Commons; classifier trained on this atlas's own verified sciatic track "
          "(scripts/cryo/vhf_nerve_scorer.py). Derived data.")


def features(X):
    """X: (n, 48, 48, 3) uint8 -> (n, d) float32."""
    f = X.astype(np.float32); R = f[..., 0]; n = len(X)
    pooled = R.reshape(n, 12, 4, 12, 4).mean(axis=(2, 4)).reshape(n, -1) / 255.0
    col = f.reshape(n, -1, 3).mean(axis=1) / 255.0
    res = []
    for s in (1.0, 2.0, 4.0):
        sm = np.stack([ndi.gaussian_filter(r, s) for r in R])
        res.append(np.abs(R - sm).mean(axis=(1, 2)) / 255.0)
    grad = np.stack([np.hypot(ndi.sobel(r, 0), ndi.sobel(r, 1)).mean() for r in R]) / 255.0
    yy, xx = np.mgrid[-P:P, -P:P]; rr = np.hypot(yy + 0.5, xx + 0.5)
    rings = [((rr >= a) & (rr < b)) for a, b in ((0, 6), (6, 12), (12, 18), (18, 24))]
    prof = np.stack([R[:, m].mean(axis=1) for m in rings], axis=1) / 255.0
    return np.concatenate([pooled, col, np.stack(res, axis=1), grad[:, None], prof], axis=1).astype(np.float32)


def augment(X, Y):
    xs, ys = [], []
    for k in range(4):
        r = np.rot90(X, k, axes=(1, 2)); xs += [r, r[:, :, ::-1]]; ys += [Y, Y]
    return np.concatenate(xs), np.concatenate(ys)


def load(path):
    import joblib
    return joblib.load(path)


def score_patches(model, patches):
    if len(patches) == 0:
        return np.zeros(0)
    return model.predict_proba(features(np.stack(patches)))[:, 1]


def dense_scan(model, im, region, stride=6):
    """Probability map over `region` (bool) at patch centres on a grid; 0 elsewhere. Smoothed by 2 px."""
    prob = np.zeros(im.shape[:2], np.float32)
    rows = np.arange(P, im.shape[0] - P, stride); cols = np.arange(P, im.shape[1] - P, stride)
    pts = [(r, c) for r in rows for c in cols if region[r, c]]
    if not pts:
        return prob
    X = np.stack([im[r - P:r + P, c - P:c + P] for r, c in pts]); p = model.predict_proba(features(X))[:, 1]
    for (r, c), v in zip(pts, p):
        prob[r - stride // 2:r + stride // 2 + 1, c - stride // 2:c + stride // 2 + 1] = v
    return ndi.gaussian_filter(prob, 2.0)


def train(a):
    import joblib
    from sklearn.ensemble import HistGradientBoostingClassifier
    d = np.load(a.patches, allow_pickle=True); X, Y, meta = d["X"], d["Y"], d["meta"]
    levels = np.array([f"{m[0]}:{m[1]}" for m in meta]); uniq = sorted(set(levels)); hold = set(uniq[::5])
    val = np.array([l in hold for l in levels]); tr = ~val
    Xa, Ya = augment(X[tr], Y[tr]); Fa = features(Xa); Fv = features(X[val])
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=0.5, random_state=0)
    clf.fit(Fa, Ya)
    pv = clf.predict_proba(Fv)[:, 1]
    from sklearn.metrics import roc_auc_score, average_precision_score
    kinds = np.array([m[2] for m in meta])[val]
    rep = {"source": SOURCE, "n_train_patches": int(tr.sum()), "n_train_augmented": int(len(Ya)), "n_val_patches": int(val.sum()),
           "val_levels_held_out": len(hold), "val_auc": round(float(roc_auc_score(Y[val], pv)), 4),
           "val_average_precision": round(float(average_precision_score(Y[val], pv)), 4),
           "val_recall_at_0.5": round(float((pv[Y[val] == 1] >= 0.5).mean()), 3),
           "val_false_positive_rate_at_0.5": {k: round(float((pv[(Y[val] == 0) & (kinds == k)] >= 0.5).mean()), 3)
                                              for k in ("hard", "corridor", "random") if ((Y[val] == 0) & (kinds == k)).any()},
           "features": int(Fa.shape[1])}
    Xall, Yall = augment(X, Y); clf.fit(features(Xall), Yall)   # the shipped model: fitted on every level
    joblib.dump(clf, a.out)
    if a.report:
        Path(a.report).write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1)); print("model", a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train"); t.add_argument("--patches", required=True); t.add_argument("--out", required=True); t.add_argument("--report", default=None)
    a = ap.parse_args()
    if a.cmd == "train":
        train(a)


if __name__ == "__main__":
    main()
