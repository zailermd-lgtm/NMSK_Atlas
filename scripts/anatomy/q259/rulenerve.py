"""Q259: shared RULE-BASED nerve-tube builder for the cervical plexus / splanchnic nerves / vagus branches -- the
same method family as Q249's rule_nerves.Builder.mk and Q258's rule_brachial_own.py (spline through cited waypoints
measured on THIS page's own meshes, pushed clear of bone, round tube, closed caps, badge with error bound), trimmed
to not depend on Q249's pelvic-specific `Anat` class (no pudendal-vessel order check, no perineal skin envelope):
generic `guards.Guards` skin depth / skin pull is used instead, which is honestly less precise on a Z page (union of
open regional skin patches -> unsigned distance) than on an own page (one closed skin mesh -> signed depth) -- the
same caveat rule_nerves.py already states for that same fallback.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
import guards as GD     # noqa: E402
import nervelib as NL   # noqa: E402

SG = {"l": -1.0, "r": 1.0}


class Builder:
    def __init__(self, S):
        self.S = S
        self.E = S.E
        self.ctx = S.ctx
        self.gd = GD.Guards(S.E)
        self.soft = NL.Soft(S.E, self.gd)
        self.out = []
        self.key = S.key
        self.own = S.key.startswith("own")

    def have(self, *ids):
        return [i for i in ids if i in self.E]

    def find(self, *cands):
        return self.S.find(*cands)

    def hold(self, nid, name, why, side=None):
        self.out.append(dict(id=nid, name=name, side=side, status="held", held=[why], cat="nerve"))

    def mk(self, nid, name, latin, side, anchors, d, *, region, course, calibre, calibre_kind, source, err_mm, err_text,
           min_skin=None, skin_pull=None, len_range=None, extra_rep=None, n=None, softpush=(), side_margin=-2.0):
        anchors = [np.asarray(a, float) for a in anchors]
        d0, d1 = (d, None) if np.isscalar(d) else d
        rad_a = (d0 if d1 is None else max(d0, d1)) / 2.0
        # pre-clear each anchor of nearby bone (same convention as q249/rule_nerves.py Builder.mk): an anchor meant
        # to sit AT a bone's own surface (e.g. a root literally emerging from its vertebra) is pushed out along the
        # bone's own normal just enough for its tube's half-diameter + 0.3 mm clearance, instead of leaving the
        # whole tube cross-section half-buried there (which `finish_bones` below cannot fully correct: it only
        # pushes non-cap vertices, by design, so a buried cap stays buried).
        for ia in range(len(anchors)):
            ids = self.ctx.near_bones(anchors[ia][None], 15.0)
            if not ids:
                continue
            da, _, na, _ = self.ctx.bf.signed(anchors[ia][None], ids)
            da, na = float(da[0]), na[0]
            if da < rad_a + 0.3:
                anchors[ia] = anchors[ia] + na * (rad_a + 0.3 - da)
        raw_len = NL.path_len(np.array(anchors))
        n = n or int(np.clip(raw_len / 1.6, 10, 80))
        Pth = NL.spline(anchors, n)
        rad = (d0 if d1 is None else max(d0, d1)) / 2.0
        for sid, marg in softpush:
            if sid in self.E:
                Q = self.soft.outside(sid, Pth, rad + marg)
                Pth[1:-1] = Q[1:-1]
        ids = self.ctx.near_bones(Pth, 25.0)
        sd_raw = self.ctx.bf.signed(Pth, ids)[0] if ids else np.full(len(Pth), 9.0)
        raw_frac = float((sd_raw < -1.0).mean())
        P_before = Pth.copy()
        Pth = NL.push_out_bones(self.ctx, Pth, rad)
        disp = float(np.linalg.norm(Pth - P_before, axis=1).max())
        if skin_pull is not None and "skin" in self.E:
            Pth = self.gd.skin_pull(Pth, skin_pull + d0 / 2.0)
        V, F, c0, c1, dd = NL.tube_round(Pth, d0, d1)
        V, brep = NL.finish_bones(self.ctx, V, F, c0, c1)
        m = trimesh.Trimesh(V, F, process=False)
        rep = dict(vertices=int(len(V)), triangles=int(len(F)), watertight=bool(m.is_watertight),
                   volume_mm3=round(float(abs(m.volume)), 1), volume_cm3=round(float(abs(m.volume)) / 1000, 4), **brep)
        L = NL.path_len(Pth)
        ov = self.gd.overlap(V)
        sk = self.gd.skin_depth(V)
        rep.update(length_mm=round(L, 1), diameter_mm=[round(float(dd.min()), 2), round(float(dd.max()), 2)],
                   raw_path_fraction_inside_bone=round(raw_frac, 3), push_out_displacement_max_mm=round(disp, 1),
                   soft_overlap=ov, skin_min_depth_mm=sk, waypoints=[np.round(a, 1).tolist() for a in anchors])
        if extra_rep:
            rep.update(extra_rep)
        why = []
        if disp > 15.0:
            why.append(f"push-out of bone moved the path by {disp:.1f} mm (> 15 mm: waypoints inconsistent with the bones)")
        if rep["vertices_deeper_1mm"]:
            why.append("tube vertices still > 1 mm in bone after the push-out")
        if not rep["watertight"]:
            why.append("tube not closed")
        if min_skin is not None and sk is not None and sk < min_skin:
            why.append(f"closer than {min_skin:g} mm to / outside the skin ({sk} mm)")
        if len_range and not (len_range[0] <= L <= len_range[1]):
            why.append(f"length {L:.0f} mm outside the plausible range {len_range[0]}-{len_range[1]} mm")
        xm = self.S.xm
        xs = Pth[:, 0] - xm
        if side in "lr" and SG[side] * np.median(xs) < side_margin:
            why.append("not on its own side of the midline")
        rep["waypoint_error_bound_mm"] = err_mm
        rec = dict(name=name, latin=latin, folder="nerves", region=region, source=source)
        rec["notes"] = course
        rec["procedural_badge"] = self._badge(course, calibre, calibre_kind, rep, err_mm, err_text, ov)
        e = dict(id=nid, name=name, latin=latin, side=side, V=V, F=F, rec=rec, report=rep,
                 status="ship" if not why else "held", held=why, cat="nerve", d=dd)
        self.out.append(e)
        return e

    def _badge(self, course, calibre, kind, rep, err, err_text, ov):
        return (f"RULE-BASED (Q259): this nerve is NOT segmented from imaging, NOT dissected and NOT a Z-Anatomy object: a round tube of the cited calibre along a spline through waypoints that follow the "
                f"documented course and are defined relative to bone / neighbouring-structure landmarks measured on THIS page's own meshes. Course: {course} "
                f"Calibre: {calibre} ({'ASSUMPTION - no published diameter found' if kind == 'assumption' else 'published value'}); round cross-section {rep['diameter_mm'][0]}"
                f"{'' if rep['diameter_mm'][0] == rep['diameter_mm'][1] else '-' + str(rep['diameter_mm'][1])} mm, closed end caps. Length {rep['length_mm']} mm, volume {rep['volume_cm3']} cm3 (closed mesh). "
                f"Waypoint error bound about {err:.1f} mm ({err_text}). "
                f"Checks: {round(100 * rep['raw_path_fraction_inside_bone'])}% of the raw path inside bone before the push-out, no vertex deeper than 1 mm inside a bone after it ({rep['vertices_deeper_1mm']}); "
                f"{round(100 * ov['muscle_fraction_deeper_6mm'])}% of vertices deeper than 6 mm inside a muscle (nerves run in fascial planes and enter their own target muscle: reported, not gated), "
                f"{round(100 * ov['organ_fraction_deeper_3mm'])}% inside an organ; depth inside the skin {rep['skin_min_depth_mm']} mm. "
                "An estimate of position: the real course, calibre and branching of this nerve vary between people and are not resolved by CT, cryosection or this atlas' Z-Anatomy fit.")
