"""Q248: soft-tissue guards shared by the rule-based builders (same limits as transfer.Carrier): closed muscles / organs of the page (inverted windings corrected), Z-filled seam muscles reported not gated, skin depth."""
from __future__ import annotations
import numpy as np, trimesh
from scipy.spatial import cKDTree
import lig_pages as PG

MUSCLE_DEEP_MM, ORGAN_DEEP_MM, MAX_MUSCLE_FRAC, MAX_ORGAN_FRAC, MIN_SKIN_DEPTH = 6.0, 3.0, 0.25, 0.10, 3.0


class Guards:
    def __init__(self, E):
        self.E = E; self._soft = {}; self._closed = {}

    def _field(self, i):
        if i not in self._soft:
            m = PG.mesh(self.E[i]); n = int(min(40000, max(4000, m.area / 0.5)))
            np.random.seed(0)
            pts, fi = trimesh.sample.sample_surface(m, n, seed=0)
            self._soft[i] = (cKDTree(pts), PG.outward_normals(m)[fi])
        return self._soft[i]

    def overlap(self, V):
        lo, hi = V.min(0) - 8, V.max(0) + 8
        dm = np.zeros(len(V), bool); do = np.zeros(len(V), bool); who, zf = {}, {}
        for i, e in self.E.items():
            if e["sys"] not in ("muscle", "organ", "viscera") or len(e["f"]) <= 20:
                continue
            a, b = e["v"].min(0), e["v"].max(0)
            if not ((a <= hi).all() and (b >= lo).all()):
                continue
            if i not in self._closed:
                self._closed[i] = bool(PG.mesh(e).is_watertight)
            if not self._closed[i]:
                continue
            kd, nn = self._field(i)
            d, k = kd.query(V)
            ins = ((V - kd.data[k]) * nn[k]).sum(1) < 0
            org = e["sys"] != "muscle"
            deep = ins & (d > (ORGAN_DEEP_MM if org else MUSCLE_DEEP_MM))
            if deep.any():
                if "zfill" in i:
                    zf[i] = int(deep.sum()); continue
                who[i] = int(deep.sum()); (do if org else dm).__ior__(deep)
        return dict(muscle_fraction_deeper_6mm=round(float(dm.mean()), 3), organ_fraction_deeper_3mm=round(float(do.mean()), 3),
                    top=dict(sorted(who.items(), key=lambda x: -x[1])[:4]), z_filled_estimates_not_gated=dict(sorted(zf.items(), key=lambda x: -x[1])[:3]))

    def skin_depth(self, V):
        """own pages: signed depth inside the closed 'skin' mesh -- EXACT (trimesh's own watertight winding-number
        signed distance), not the nearest-SAMPLED-point + its normal approximation this used before Q263. That
        approximation is what Q260 found and reported as a false "tens of mm outside the skin" reading in the
        superior neck on own pages: verified directly (Q263) that it is a genuine sign flip, not just noise -- e.g.
        own_f at (-10, 693.8, 10) is a real 65.7 mm INSIDE (trimesh exact), but the nearest SAMPLED surface point is
        on the far side of a sharp fold near the ear/jaw only 12.6 mm away along the surface yet pointing an almost
        opposite normal, so the dot-product sign flips to "69 mm outside". This is inherent to a sparse random
        surface-point sample in any concave, tightly-folded region (ear, jaw angle, neck) -- no amount of resampling
        fixes it generically, only querying the mesh itself does. Switched to the exact method (already proven
        correct and fast enough at this codebase's own call sizes by Q260's own rule_vagus_own.py, which used it only
        to correct its own cards after the fact) -- cached per Guards instance, built once, reused by every mk() call
        on the same page. Z pages: UNSIGNED distance to the union of the skin pieces (unchanged: those pieces are
        open, there is no closed mesh to query exactly against)."""
        sk = self.E.get("skin")
        if sk is not None:
            if not hasattr(self, "_skin_pq"):
                m = PG.mesh(sk)
                self._skin_pq = trimesh.proximity.ProximityQuery(m) if m.is_watertight else None
            if self._skin_pq is not None:
                return round(float(self._skin_pq.signed_distance(V).min()), 1)
            # defensive fallback only: not watertight (not the case on any current own page, checked directly)
            kd, nn = self._field("skin")
            d, k = kd.query(V)
            s = ((V - kd.data[k]) * nn[k]).sum(1)
            return round(float(np.min(np.where(s < 0, d, -d))), 1)
        if not hasattr(self, "_zskin"):
            pts = []
            for i, e in self.E.items():
                if e["sys"] == "skin" and len(e["f"]) > 3:
                    m = PG.mesh(e); pts.append(trimesh.sample.sample_surface(m, int(min(8000, max(300, m.area / 2.0))), seed=0)[0])
            self._zskin = cKDTree(np.vstack(pts)) if pts else None
        return None if self._zskin is None else round(float(self._zskin.query(V)[0].min()), 1)

    def skin_pull(self, P, depth, keep=(0, -1), iters=6):
        """own pages: move path points that are shallower than `depth` mm below the (closed) skin inward along the skin normal, ends fixed (a ligament lies deep to the subcutis; the page's skin can hug the bone)"""
        if "skin" not in self.E:
            return P
        kd, nn = self._field("skin")
        P = P.copy()
        for _ in range(iters):
            d, k = kd.query(P)
            s = ((P - kd.data[k]) * nn[k]).sum(1)
            dep = np.where(s < 0, d, -d)
            bad = dep < depth
            for i in keep:
                bad[i] = False
            if not bad.any():
                break
            P[bad] -= nn[k][bad] * (depth - dep[bad])[:, None]
        return P

    def gate(self, V, min_skin=MIN_SKIN_DEPTH, gate_soft=True):
        """gate_soft False (Z pages): muscle / organ overlap is REPORTED, not gated -- every soft structure of a Z page is itself a Z-Anatomy fit estimate (precedent Q243)"""
        ov = self.overlap(V); sk = self.skin_depth(V)
        why = []
        if gate_soft and ov["muscle_fraction_deeper_6mm"] > MAX_MUSCLE_FRAC: why.append("> 25 % of the vertices deeper than 6 mm inside a muscle")
        if gate_soft and ov["organ_fraction_deeper_3mm"] > MAX_ORGAN_FRAC: why.append("> 10 % of the vertices deeper than 3 mm inside an organ")
        if sk is not None and sk < min_skin: why.append(f"closer than {min_skin:g} mm to / outside the skin")
        return ov, sk, why
