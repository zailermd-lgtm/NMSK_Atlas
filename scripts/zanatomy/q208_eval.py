"""Q208 evaluation helpers: per-patch quality (edge ratio vs the Z source, slab thickness, own-skin containment), skin sheet crossings, seam steps."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402


def crossing_ids(pg, extra=()):
    """the id set of the Q207 'skin sheet intersection' count: limb / hand patches (without nail plates and perionyx) + the patches that Q207 / Q208 moved"""
    q7 = json.loads((REPO / "data/derived/Q207_ship_diff_{}.json".format(pg.which)).read_text())
    moved = set(q7["geometry_changed"]) | set(extra)
    ids = set(moved) | {i for i in pg.skin_ids if C7.LIMB_SKIN_RE.search(i)}
    return sorted(i for i in ids if "nail_plate" not in i and "perionyx" not in i and i in pg.S)


def crossings(pg, V, ids, restrict=None):
    """face-pair intersections among the patches `ids` (vertex dict V): (all, depth > 1 mm, > 2 mm, > 4 mm) and the per patch-pair counts of the deep ones (> 2 mm)"""
    Vc, F, ow, nm = G.concat({i: (V[i], pg.f(i)) for i in ids})
    pr = G.intersecting_pairs(Vc, F, ow)
    dd = G.pair_depth(Vc, F, pr) if len(pr) else np.zeros(0)
    deep = {}
    for (x, y), d in zip(pr, dd):
        if d > 2:
            k = tuple(sorted((nm[ow[x]], nm[ow[y]])))
            deep[k] = deep.get(k, 0) + 1
    return dict(face_pairs=int(len(pr)), depth_gt_1mm=int((dd > 1).sum()), depth_gt_2mm=int((dd > 2).sum()), depth_gt_4mm=int((dd > 4).sum())), deep


def quality(pg, V, V0, raw, ids):
    out = {}
    for i in ids:
        f = pg.f(i)
        t1, t0 = G.slab_thickness(V[i], f), G.slab_thickness(V0[i], f)
        e1, e0 = G.edge_ratio(V[i], f, raw.v(i)), G.edge_ratio(V0[i], f, raw.v(i))
        out[i] = dict(thickness_median_mm=[round(float(np.nanmedian(t0)), 2), round(float(np.nanmedian(t1)), 2)],
                      thickness_p5_mm=[round(float(np.nanpercentile(t0, 5)), 2), round(float(np.nanpercentile(t1, 5)), 2)],
                      edge_ratio_p5_p95=[[round(float(np.percentile(e0, 5)), 2), round(float(np.percentile(e0, 95)), 2)], [round(float(np.percentile(e1, 5)), 2), round(float(np.percentile(e1, 95)), 2)]],
                      edge_ratio_max=[round(float(e0.max()), 2), round(float(e1.max()), 2)])
    return out
