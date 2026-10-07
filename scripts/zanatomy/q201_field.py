"""Q201: the soft-tissue field of the male elbow / forearm / wrist, defined where the Q168 blend defines it: on the Z-SOURCE positions.

Measured (Q201): the unrefined Z structures of the Q195 state ARE the Q168 blend of the Z source -- v = sum_u W_u(x_src) T_u(x_src), T_u the per-bone similarity of unit u (Q195_zan_to_vhm.json), W_u the
tapered inverse-distance weights to the Z-source bone point clouds (zan_to_vhf_whole_body.ZanToVhf.blend): blend(raw) equals the shipped vertex to 0.0 mm (median) for the forearm muscles, nerves and
vessels checked, the rest is the later per-structure refinement (Q190 / Q191 / Q195).  The Q168 transforms of his right radius / ulna were wrong (scale 0.84 / 0.87, wrist 30 mm off the carpals, left ulna
rolled ~110 deg), so every structure carried by them is distorted (right extensor digiti minimi: volume 0.11 x the Z source, 47 % of the triangles stretched).  The Q199 field looks the displacement up at
the CURRENT (distorted) positions; here it is the blend itself re-run with the corrected transforms of the three moving bones per side:

    D(x_src) = sum_{u in moving bones} W_u(x_src) [ T'_u(x_src) - T_u(x_src) ],     T'_u = chain_u o T_u

(W from the SAME weights the blend used, the other units contribute 0), added to the current vertex.  A structure the later steps moved onto his own mesh keeps that move: only the blend part changes.
"""
from __future__ import annotations

import numpy as np

from scripts.transfer import zan_to_vhf_whole_body as Q

BONES = ("humerus", "radius", "ulna")


class DeltaField:
    def __init__(self, xf, chains: dict):
        self.xf = xf
        self.chains = chains
        self.mov = {}
        for k, name in enumerate(xf.unit_names):
            base = name.split("/")[0]
            for side, ch in chains.items():
                for b in BONES:
                    if base == f"{b}_{side}":
                        self.mov[k] = (side, b)

    def unit_delta(self, k, X):
        side, b = self.mov[k]
        T = Q.apply_sim(self.xf.unit_A[k], self.xf.unit_t[k], X)
        return self.chains[side].apply(b, T) - T

    def weights(self, v, cls):
        """(unit indices, W): exactly the weights ZanToVhf.blend uses for the points v (Z-source frame) of limb class cls"""
        xf = self.xf
        v = np.asarray(v, np.float64)
        idx, ctree = xf._allowed(cls)
        dmin = ctree.query(v)[0]
        reach = dmin + Q.BLEND_CUTOFF_MM
        vlo, vhi = v.min(0), v.max(0)
        box_gap = np.linalg.norm(np.maximum(0, np.maximum(xf.lo[idx] - vhi, vlo - xf.hi[idx])), axis=1)
        idx = idx[box_gap <= reach.max()]
        D = np.full((len(v), len(idx)), np.inf)
        for k, i in enumerate(idx):
            gap = np.linalg.norm(np.maximum(0, np.maximum(xf.lo[i] - v, v - xf.hi[i])), axis=1)
            sel = gap <= reach
            if sel.any():
                D[sel, k] = xf.trees[i].query(v[sel])[0]
        return idx, Q.smooth_idw_weights(D)

    def _blend_delta(self, v, cls):
        idx, W = self.weights(v, cls)
        out = np.zeros_like(v)
        for k, i in enumerate(idx):
            if i not in self.mov:
                continue
            sel = W[:, k] > 0
            if sel.any():
                out[sel] += W[sel, k:k + 1] * self.unit_delta(i, v[sel])
        return out

    def delta(self, mesh_id, raw_v):
        """displacement (n, 3) to ADD to the current vertices of mesh `mesh_id` (whose Z-source vertices are raw_v)"""
        v = np.asarray(raw_v, np.float64)
        if mesh_id in self.xf.piece_map:                       # a rigid follower / a bone: its own transform (bones are moved by the chain itself)
            return np.zeros_like(v)
        lab_v, n = Q.spatial_clusters(v)
        if n == 1:
            return self._blend_delta(v, self.xf.limb_class(v))
        out = np.zeros_like(v)
        for c in range(n):
            sel = lab_v == c
            out[sel] = self._blend_delta(v[sel], self.xf.limb_class(v[sel]))
        return out


def load_xf(raw: dict, report_path=None):
    """the Q168 / Q195 transform of the male (committed per-bone fits) with the Z-source bones of `raw`"""
    import json
    from pathlib import Path
    from scripts.zanatomy import body_ctx
    rp = Path(report_path) if report_path else body_ctx.REGION_REPORT
    fits = Q.fits_from_json(json.loads(rp.read_text())["bone_fits"])
    need = {p for fr in fits.values() if fr.get("status") == "fitted" for p in fr["pieces"]}
    return Q.ZanToVhf(fits, {k: np.asarray(raw[k], float) for k in need if k in raw})
