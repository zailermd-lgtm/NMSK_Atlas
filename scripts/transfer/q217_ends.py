"""Q217: muscle ends onto HIS bones (origin / insertion), stretched along the muscle.

For every muscle whose end zone (extreme 10 % of the length along the principal axis of its main piece, the Q204 end test) lies > END_GATE_MM from the bone its card names (origin / insertion text 'bone_id: ...'), that end zone
is translated so that its closest 10 % land on that bone (smooth displacement field over the mesh, the other end zone and, optionally, the belly held: q216_fix.pull_anchored), capped at CAP_MM.  The muscle is stretched
along its own axis (along its tendon); nothing else changes.  Bones: the displayed bone meshes (surface samples)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q217_slide import surface_samples  # noqa: E402

END_GATE_MM = 3.5
CAP_MM = 25.0


def named_bones(rec):
    out = []
    for key in ("origin", "insertion"):
        m = re.match(r"\s*([a-z0-9_]+)\s*:", (rec or {}).get(key) or "")
        out.append(m.group(1) if m else None)
    return out


def zones(v, frac=0.10):
    """two end zones along the principal axis: {'lo': mask, 'hi': mask} (t = projection on the axis, oriented so that +axis points up in y)"""
    c = v.mean(0)
    u = np.linalg.svd(v - c, full_matrices=False)[2][0]
    if u[1] < 0:
        u = -u
    t = (v - c) @ u
    L = float(t.max() - t.min())
    lo, hi = t <= t.min() + frac * L, t >= t.max() - frac * L
    return {"lo": lo, "hi": hi}, u, t


def zone_dist(v, mask, tree):
    d = tree.query(v[mask])[0]
    return float(np.percentile(d, 5)), float(d.min())


def plan(v, rec, bone_tree, which=None):
    """-> list of (end name, zone mask, target bone id, p5 distance) for the ends that are off their bone"""
    zs, u, t = zones(v)
    nb = named_bones(rec)
    out = []
    for nm, z in zs.items():
        for bid in [b for b in nb if b and (which is None or b in which)]:
            if bid not in bone_tree:
                continue
            p5, mn = zone_dist(v, z, bone_tree[bid][0])
            out.append((nm, z, bid, p5, mn))
    # per end: the nearest of its candidate bones
    best = {}
    for nm, z, bid, p5, mn in out:
        if nm not in best or p5 < best[nm][3]:
            best[nm] = (nm, z, bid, p5, mn)
    return list(best.values())


def bone_trees(bones, spacing=1.0):
    return {bid: (cKDTree(surface_samples(v, f, spacing)), surface_samples(v, f, spacing)) for bid, (v, f) in bones.items()}
