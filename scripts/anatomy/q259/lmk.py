"""Q259: generic vertebral / soft-tissue landmarks for the CERVICAL PLEXUS, the THORACIC/LUMBAR/SACRAL SPLANCHNIC
NERVES and the VAGUS's major branches, shared by rule_cervical.py / rule_splanchnic.py / rule_vagus.py.

Vertebra numbering (own pages' `cervical_vertebrae#k` / `thoracic_vertebrae#k` / `lumbar_vertebrae#k` ids are numbered
BOTTOM-UP within each region -- #1 is the most INFERIOR vertebra of that region, #N the most superior; this was
re-checked EMPIRICALLY here (not assumed from Q258/Q249's own prose), by comparing the y-centroid of every id on
both own pages: cervical_vertebrae#1..#7 ascend in y (611->716 mm on own_m), thoracic_vertebrae#1..#12 ascend
(313->595 mm), lumbar_vertebrae#1..#5 ascend (132->277 mm on own_m; own_f's lumbar#5 is an outlier position, not
used by this module), and thoracic#12 sits immediately below cervical#1 (both pages) -- so cervical#1=C7...#7=C1,
thoracic#1=T12...#12=T1, lumbar#1=L5...#5=L1, exactly the convention Q258's neck_lm.py and Q249's lm.py each
documented separately for their own narrower slice of the spine; this module is the first to state the WHOLE
column's mapping in one place and re-verify it). Z pages use natural (non-reversed) ids: zan_atlas_c1, zan_axis_c2,
zan_vertebra_c3..c7, zan_vertebra_t1..t12, zan_vertebra_l1..l5 -- confirmed present on all four Z pages by direct
listing before this module was written, not assumed.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
import rulelig as RL   # noqa: E402
import lm as LMK       # noqa: E402

SG = {"l": -1.0, "r": 1.0}


def is_z(key):
    return not key.startswith("own")


def vertebra_id(E, key, level):
    """level: 'c1'..'c7', 't1'..'t12', 'l1'..'l5'. -> a real mesh id present in E, or None."""
    region, idx = level[0], int(level[1:])
    if is_z(key):
        if region == "c":
            cand = "zan_atlas_c1" if idx == 1 else ("zan_axis_c2" if idx == 2 else f"zan_vertebra_c{idx}")
        elif region == "t":
            cand = f"zan_vertebra_t{idx}"
        else:
            cand = f"zan_vertebra_l{idx}"
    else:
        if region == "c":
            cand = f"cervical_vertebrae#{8 - idx}"     # C1->#7 ... C7->#1
        elif region == "t":
            cand = f"thoracic_vertebrae#{13 - idx}"    # T1->#12 ... T12->#1
        else:
            cand = f"lumbar_vertebrae#{6 - idx}"       # L1->#5 ... L5->#1
    return cand if cand in E else None


def lateral_point(E, vid, s, xm, frac_pctl=97.0, bias=None):
    """centroid of the most-lateral vertices of vertebra `vid` on side s (approximates the transverse-process /
    intervertebral-foramen region a ventral ramus crosses -- Gray's Anatomy 1918, 'Spinal Nerves'). bias='low'/'high'
    restricts to the inferior/superior half of that selection first (for a level this page has no separate
    vertebra for, approximated from the inferior/superior half of the nearest real one -- same device Q258's
    neck_lm.vertebra_lateral used for C8/T1)."""
    v = E[vid]["v"]
    relx = (v[:, 0] - xm) * SG[s]
    thr = np.percentile(relx, frac_pctl)
    sel = v[relx >= thr]
    if bias and len(sel) >= 8:
        ym = np.median(sel[:, 1])
        sel = sel[sel[:, 1] <= ym] if bias == "low" else sel[sel[:, 1] >= ym]
    return sel.mean(0)


def anterolateral_point(E, vid, s, xm, lat_lo=65.0, lat_hi=92.0):
    """a point on the ANTEROLATERAL aspect of the vertebral body / rib head, side s: the real position of a
    sympathetic-chain ganglion at this level (Gray's Anatomy for Students ch.4/'Back': the sympathetic trunk lies
    against the heads of the ribs in the thorax, on the anterolateral surface of the vertebral bodies in the lumbar
    / sacral region) -- NOT the same point as `lateral_point` (which approximates the more-lateral, more-posterior
    transverse-process region a ventral ramus crosses): selected as the most-ANTERIOR vertex within a LATERAL band
    (65th-92nd percentile of lateral extent, not the outermost ~3%), so it sits medial to the ramus exit point and
    toward the front of the vertebra, matching the textbook description qualitatively from this page's own geometry
    (a geometric approximation, not a segmented ganglion -- stated in every nerve card that uses it)."""
    v = E[vid]["v"]
    relx = (v[:, 0] - xm) * SG[s]
    lo, hi = np.percentile(relx, lat_lo), np.percentile(relx, lat_hi)
    sel = v[(relx >= lo) & (relx <= hi)]
    if len(sel) < 6:
        sel = v[relx >= np.percentile(relx, lat_lo - 15)]
    return sel[np.argmax(sel[:, 2])]


def body_lateral_point(E, vid, s, xm, frac_pctl=80.0):
    """a point on the lateral surface of the vertebral BODY (not the posterior transverse-process region): mean of
    vertices beyond a lateral percentile that are also in the anterior half (z above the vertebra's own median z) --
    used for the lumbar/sacral sympathetic chain, which runs along the anterolateral margin of the vertebral bodies
    themselves, not over the transverse processes."""
    v = E[vid]["v"]
    relx = (v[:, 0] - xm) * SG[s]
    zmed = np.median(v[:, 2])
    sel = v[(relx >= np.percentile(relx, frac_pctl)) & (v[:, 2] >= zmed)]
    if len(sel) < 6:
        sel = v[relx >= np.percentile(relx, frac_pctl)]
    return sel.mean(0)


class Spine:
    """one page's vertebra id list + convenience accessors, shared by the three Q259 builders."""
    def __init__(self, key, root):
        self.key = key
        self.ctx = RL.Ctx(key, root=root)
        self.E, self.bf, self.F = self.ctx.E, self.ctx.bf, self.ctx.F
        self.xm = self.F["x_mid"]
        self.z = is_z(key)
        self.notes = {}

    def vid(self, level):
        return vertebra_id(self.E, self.key, level)

    def lateral(self, level, s, **kw):
        vid = self.vid(level)
        if vid is None:
            return None
        p = lateral_point(self.E, vid, s, self.xm, **kw)
        self.notes[f"{level}_{s}_lateral"] = dict(id=vid, point=np.round(p, 1).tolist())
        return p

    def anterolateral(self, level, s, **kw):
        vid = self.vid(level)
        if vid is None:
            return None
        p = anterolateral_point(self.E, vid, s, self.xm, **kw)
        self.notes[f"{level}_{s}_chain"] = dict(id=vid, point=np.round(p, 1).tolist())
        return p

    def body_lateral(self, level, s, **kw):
        vid = self.vid(level)
        if vid is None:
            return None
        p = body_lateral_point(self.E, vid, s, self.xm, **kw)
        self.notes[f"{level}_{s}_body"] = dict(id=vid, point=np.round(p, 1).tolist())
        return p

    def have(self, *ids):
        return [i for i in ids if i in self.E]

    def find(self, *cands):
        for c in cands:
            if c in self.E:
                return c
        return None

    def centerline(self, mid, n=30):
        if mid not in self.E:
            return None
        return LMK.centerline(self.E[mid]["v"], self.E[mid]["f"], n)

    # ------------------------------------------------------------------ sacrum (same method as q249/lm.py's own
    # _sacrum(), reimplemented against THIS module's own Ctx/root rather than lm.Pel's hardcoded env-only root, so
    # it can be pointed at build/q258 like every other Q259 landmark) -- FORAMEN_FRAC / FORAMEN_LAT are the exact
    # constants lm.py documents and cites (Ebraheim NA et al., Orthopedics 1998;21:703-6).
    def _sacrum(self):
        if getattr(self, "_sac_done", False):
            return
        self._sac_done = True
        xm = self.xm
        ids = [i for i in self.E if self.E[i]["sys"] == "bone" and (i.startswith("sacrum") or i == "coccyx" or i == "zan_sacrum" or i == "zan_coccyx") and "zfill" not in i]
        if not ids:
            self.sac = None
            return
        Vv = np.vstack([self.E[i]["v"] for i in ids]); Vv = Vv[np.abs(Vv[:, 0] - xm) < 70]
        self.sac_ids = ids
        y_top = float(np.percentile(Vv[:, 1], 99.5)); y_min = float(Vv[:, 1].min())
        ys = np.arange(y_top, y_min, -1.0); y_end = y_min
        for y in ys:
            m = np.abs(Vv[:, 1] - y) < 1.5
            if m.sum() and np.ptp(Vv[m, 0]) < 24 and y < y_top - 60:
                y_end = float(y); break
        self.sac = dict(y_top=y_top, y_end=y_end, half_w=float(np.percentile(np.abs(Vv[:, 0] - xm), 99)), v=Vv)

    def sacral_point(self, k, s, lateral_mm=None):
        """point near the S{k} anterior sacral foramen (or `lateral_mm` from the midline at that height, for the
        sacral sympathetic chain, which runs medial to the foramina -- Gray's Anatomy for Students ch.6: the sacral
        part of the sympathetic trunk lies on the pelvic surface of the sacrum, medial to the anterior sacral
        foramina)."""
        self._sacrum()
        if self.sac is None:
            return None
        import sys as _s
        FORAMEN_FRAC = {1: 0.28, 2: 0.46, 3: 0.63, 4: 0.79}
        FORAMEN_LAT = {1: 25.0, 2: 22.0, 3: 18.0, 4: 16.0}
        y_top, y_end, hw, Vv = self.sac["y_top"], self.sac["y_end"], self.sac["half_w"], self.sac["v"]
        yk = y_top - FORAMEN_FRAC[k] * (y_top - y_end)
        xk = self.xm + SG[s] * (FORAMEN_LAT[k] if lateral_mm is None else lateral_mm) * hw / 60.0
        win = (np.abs(Vv[:, 0] - xk) < 10) & (np.abs(Vv[:, 1] - yk) < 10)
        if win.sum() < 3:
            win = (np.abs(Vv[:, 0] - xk) < 16) & (np.abs(Vv[:, 1] - yk) < 16)
        sel = Vv[win]
        if not len(sel):
            return None
        return np.array([xk, yk, float(sel[:, 2].max())])

    def scm_posterior(self, s, y_target):
        """point on the posterior border of sternocleidomastoid, side s, nearest the given height y_target
        (Erb's point -- where the cervical plexus's cutaneous branches emerge -- is classically described at the
        midpoint of SCM's posterior border; the anterior-most axis in this frame is +Z, so 'posterior' = low z)."""
        sid = self.find(f"sternocleidomastoid_{s}")
        if sid is None:
            return None
        v = self.E[sid]["v"]
        band = v[np.abs(v[:, 1] - y_target) < 15.0]
        if len(band) < 6:
            band = v
        return band[np.argmin(band[:, 2])]
