"""Q258: neck / interscalene landmarks for the PROXIMAL brachial plexus (roots C5-T1, trunks, divisions, cords) on the two
own pages (Imaging-based F/M), which carry none of it today (Q247 audit: only the Z-transferred terminal arm nerves exist there;
the owner's complaint -- no brachial plexus between anterior and middle scalene -- is this exact gap).

Everything is MEASURED ON THE PAGE'S OWN MESHES (cervical vertebrae C5-C7, first thoracic vertebra T1, scalenus anterior / medius,
clavicle, pectoralis minor) by geometric rules, exactly like scripts/anatomy/q249/lm.py does for the pelvic nerves; no atlas
landmark is interpolated from another body.  Vertebra numbering check (done empirically, not assumed -- the own pages' own
`cervical_vertebrae#k` / `thoracic_vertebrae#k` ids are numbered BOTTOM-UP, same convention lm.py documents for lumbar_vertebrae):
on both own_m and own_f, cervical_vertebrae#1..#4 and thoracic_vertebrae#11/#12 were checked against each other's y-ranges
(ascending #1->#4, thoracic#12 immediately below cervical#1) -> cervical_vertebrae#1 = C7, #2 = C6, #3 = C5; thoracic_vertebrae#12 = T1.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
import rulelig as RL  # noqa: E402

ROOT = "build/q256"   # last full geometry+UI regen (Q256); clinical/* siblings are re-staged fresh from the current committed files, not read from here
SG = {"l": -1.0, "r": 1.0}
CERV_IDX = {"c5": 3, "c6": 2, "c7": 1}     # cervical_vertebrae#k, bottom-up numbering (checked empirically, see module docstring)
THOR_T1_IDX = 12                           # thoracic_vertebrae#12 = T1 (bottom-up numbering, immediately below cervical#1=C7)


class Neck:
    def __init__(self, key, root=None):
        self.key = key
        self.ctx = RL.Ctx(key, root=root or ROOT)
        self.E, self.bf = self.ctx.E, self.ctx.bf
        self.xm = self.ctx.F["x_mid"]
        self.notes = {}
        self._gap = {}

    # ---------------------------------------------------------------- vertebra lateral (transverse-process-region) point
    def vertebra_lateral(self, level, s):
        """centroid of the most-lateral ~3% of vertices of the named cervical/T1 vertebra, on side s: approximates the
        transverse-process region the ventral ramus crosses on its way out of the intervertebral foramen (Gray's Anatomy
        1918, 'Spinal Nerves': the ramus lies in the groove of the transverse process, anterior to the vertebral artery).

        C8 and T1 share an interspace this page has no separate vertebra geometry for: C8 is approximated from the
        INFERIOR half of C7's own mesh (cervical_vertebrae#1), T1 from the SUPERIOR half of the T1 mesh
        (thoracic_vertebrae#12) -- two distinct points, not the same vertebra centroid reused, stated honestly as a
        coarser approximation than C5-C7 (see rule_brachial_own.py's ERR_MM for the inferior-trunk error band)."""
        bias = None
        if level == "c8":
            vid = f"cervical_vertebrae#{CERV_IDX['c7']}"; bias = "low"
        elif level == "t1":
            vid = f"thoracic_vertebrae#{THOR_T1_IDX}"; bias = "high"
        else:
            vid = f"cervical_vertebrae#{CERV_IDX[level]}"
        v = self.E[vid]["v"]
        relx = (v[:, 0] - self.xm) * SG[s]
        thr = np.percentile(relx, 97)
        sel = v[relx >= thr]
        if bias is not None and len(sel) >= 8:
            ym = np.median(sel[:, 1])
            sel = sel[sel[:, 1] <= ym] if bias == "low" else sel[sel[:, 1] >= ym]
        p = sel.mean(0)
        self.notes[f"{level}_{s}_vertebra"] = dict(id=vid, bias=bias, n_selected=int(len(sel)), point=p.round(2).tolist())
        return p

    # ---------------------------------------------------------------- interscalene-gap polyline (the owner's named location)
    def gap_polyline(self, s, n=12):
        if s in self._gap:
            return self._gap[s]
        sa = self.E[f"scalenus_anterior_{s}"]["v"]
        sm = self.E[f"scalenus_medius_{s}"]["v"]
        y0, y1 = max(sa[:, 1].min(), sm[:, 1].min()), min(sa[:, 1].max(), sm[:, 1].max())
        ys = np.linspace(y0, y1, n)
        bw = (y1 - y0) / n * 1.6 + 1e-6
        pts, yy = [], []
        for y in ys:
            wa = sa[np.abs(sa[:, 1] - y) < bw]; wm = sm[np.abs(sm[:, 1] - y) < bw]
            if len(wa) < 5 or len(wm) < 5:
                continue
            pts.append((wa.mean(0) + wm.mean(0)) / 2); yy.append(y)
        poly = (np.array(yy), np.array(pts))
        self._gap[s] = poly
        self.notes[f"gap_{s}"] = dict(y_range=[round(float(y0), 1), round(float(y1), 1)], n_levels=len(yy))
        return poly

    def gap_point(self, s, y, clamp_note=None):
        """point on the gap trajectory at height y: linear interpolation within the scalene muscles' own measured
        range, LINEAR EXTRAPOLATION (using the nearest two measured points' trend) beyond it -- the muscles do not
        extend all the way down to the clavicle on these pages (checked, not assumed: a flat clamp there collapsed
        the trunk and division points onto nearly the same spot, caught by inspecting shipped lengths before
        shipping), so the course continues the measured trend rather than flattening out."""
        yy, pts = self.gap_polyline(s)
        if y < yy[0]:
            d = (pts[1] - pts[0]) / (yy[1] - yy[0])
            if clamp_note is not None:
                self.notes.setdefault("extrapolated", []).append(f"{clamp_note}: {yy[0] - y:.0f} mm below the scalenus muscles' own range, extrapolated")
            return pts[0] + d * (y - yy[0])
        if y > yy[-1]:
            d = (pts[-1] - pts[-2]) / (yy[-1] - yy[-2])
            if clamp_note is not None:
                self.notes.setdefault("extrapolated", []).append(f"{clamp_note}: {y - yy[-1]:.0f} mm above the scalenus muscles' own range, extrapolated")
            return pts[-1] + d * (y - yy[-1])
        i = int(np.searchsorted(yy, y))
        t = (y - yy[i - 1]) / (yy[i] - yy[i - 1])
        return pts[i - 1] + t * (pts[i] - pts[i - 1])

    # ---------------------------------------------------------------- clavicle superior-surface height (reference y only)
    def clavicle_top_y(self, s, frac=0.5):
        """mean y of the MEDIAL half of this side's clavicle (frac of its sternal->acromial span), not the bone's
        overall y-max -- the overall max is the elevated acromial/lateral end (this subject's arm pose raises it well
        above where the plexus actually crosses, which was caught by comparing it against the interscalene-gap
        polyline's own y-range before shipping: the overall max put every trunk/division point above that range and
        collapsed them onto a single clamped point)."""
        cl = self.E[f"clavicle_{s}"]["v"]
        relx = (cl[:, 0] - self.xm) * SG[s]
        lo, hi = relx.min(), relx.max()
        sel = cl[relx <= lo + frac * (hi - lo)]
        return float(sel[:, 1].mean())

    def plexus_point(self, s, y, lateral_fan=0.0):
        """a point ON THE SAME interscalene-gap trajectory as gap_point (real scalenus anterior/medius geometry), at
        height y, with an optional small additional lateral offset (`lateral_fan` mm, away from the midline) -- the
        trunks/divisions/cords are NOT jumped onto a separate clavicle-fraction track (that produced an unanchored,
        tens-of-mm lateral discontinuity in an early version of this module, caught by inspecting the per-structure
        lengths before shipping); they continue smoothly down the same measured gap trajectory, extrapolated at its
        lower (already-clamped) end for the part below where the scalene muscles themselves end."""
        p = self.gap_point(s, y)
        return p + np.array([SG[s] * lateral_fan, 0.0, 0.0])

    # ---------------------------------------------------------------- pectoralis minor lateral border (cord-to-branch transition zone)
    def pecminor_point(self, s, frac=0.85, medial=False):
        pm = self.E[f"pectoralis_minor_{s}"]["v"]
        relx = (pm[:, 0] - self.xm) * SG[s]
        thr = np.percentile(relx, 100 * frac if not medial else 100 * (1 - frac))
        sel = pm[relx >= thr] if not medial else pm[relx <= thr]
        return sel.mean(0)

    # ---------------------------------------------------------------- existing terminal-nerve proximal anchor (continuity check only, not a hard constraint)
    def nerve_anchor(self, nid, s):
        full = f"{nid}_{s}"
        if full not in self.E:
            return None, full
        v = self.E[full]["v"]
        return v[np.argmax(v[:, 1])], full
