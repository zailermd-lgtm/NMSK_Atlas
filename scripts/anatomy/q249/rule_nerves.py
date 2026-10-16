"""Q249: RULE-BASED pelvic / perineal nerves (and a few other tier-1 gaps of Q247) from the page's own bones and neighbouring structures.
build(P) -> list of dict(id, name, latin, side, V, F, rec, report, status, held, ...) for the Pel P of lm.py.

Every nerve: smooth spline through documented waypoints (Gray's Anatomy 1918 text + the cited dissection papers) that are defined relative to bone landmarks measured on the page (ischial spine, ischial tuberosity, subpubic
angle, sacral anterior foramina, ...) and to neighbouring structures of the page (pudendal vessels where present, obturator internus, external anal sphincter, corpus cavernosum, ...), round cross-section of the literature
calibre, closed end caps.  No geometry is taken from a segmentation or from Z-Anatomy; a nerve the Z page already carries under its own name is skipped (reported)."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lm as LMK, nervelib as NL  # noqa: E402
import rulelig as RL, guards as GD  # noqa: E402
from lm import SG, vec  # noqa: E402

import lit as LIT_MOD  # noqa: E402
LIT = LIT_MOD.LIT


def ctx_tools(P):
    gd = GD.Guards(P.E)
    soft = NL.Soft(P.E, gd)
    return gd, soft


# ------------------------------------------------------------------------------------------------ anatomy points shared by several nerves
class Anat:
    def __init__(self, P):
        self.P = P; self.gd, self.soft = ctx_tools(P)
        self.E = P.E; self.F = P.F; self.bf = P.bf
        self.ROOT = {}      # (k, s) -> path samples of the anterior ramus
        self.pts = {}
        for s in "lr":
            self.side_points(s)

    def find(self, *c):
        for i in c:
            if i in self.E:
                return i
        return None

    def vessel_center(self, pat_ids):
        for i in pat_ids:
            if i in self.E and self.E[i]["sys"] == "vessel":
                C = LMK.centerline(self.E[i]["v"], self.E[i]["f"], 40)
                if C is not None:
                    return i, C
        return None, None

    def side_points(self, s):
        P = self.P; sg = SG[s]; m = np.array([-sg, 0.0, 0.0]); F = self.F
        IS, IT, SP = P.lm[f"IS_{s}"], P.lm[f"IT_{s}"], P.lm[f"subpubic_{s}"]
        d = {}
        d["IS"], d["IT"], d["SP"] = IS, IT, SP
        d["E0"] = IS + m * 4 + np.array([0, 3.0, -10.0])                # greater sciatic foramen, below piriformis (between piriformis above and coccygeus / sacrospinous below)
        d["ISpost"] = IS + m * 2 + np.array([0, -3.0, -7.0])            # behind the tip of the spine (nerve lies on its posterior aspect)
        d["CW0"] = IS + np.array([0, -13.0, 0.0])                       # lesser sciatic foramen: below the spine
        # pudendal canal: along the medial surface of obturator internus, ~3.5 cm above the lower margin of the tuberosity at its back end, running on the ischiopubic ramus to the posterior border of the perineal membrane
        can = []
        for t in (0.0, 0.3, 0.6, 0.85, 1.0):
            R = IT + t * (SP - IT)
            can.append(R + m * (10.0 * (1 - t)) + np.array([0, 34.0 * (1 - t) + 10.0 * t, 4.0 * (1 - t)]))
        d["canal"] = np.array(can)
        self.pts[s] = d

    def vessel_adjust(self, s, W, rn, ids):
        """anchor following the pudendal vessels: nearest point of the vessel centre line within 15 mm of the rule point W, offset by (r_vessel + r_nerve + 0.3) toward W; (W, info) unchanged if no vessel / farther"""
        vid, C = self.vessel_center(ids)
        if C is None:
            return W, None
        dd = np.linalg.norm(C - W, axis=1); j = int(np.argmin(dd))
        if dd[j] > 15.0:
            return W, dict(vessel=vid, used=False, distance=round(float(dd[j]), 1))
        rv = 1.5
        dirn = vec(W - C[j]) if dd[j] > 2.0 else np.array([-SG[s], 0, 0.0])
        return C[j] + dirn * (rv + rn + 0.3), dict(vessel=vid, used=True, distance=round(float(dd[j]), 1))


# ------------------------------------------------------------------------------------------------ the factory
BONE_RES = {  # median distance of the page's bone meshes to the person's / reference bone they stand for (mm) and where it comes from
    "own_f": (1.0, "the page's bones are segmented from her CT (voxel / slice size about 1 mm)"),
    "own_m": (1.0, "the page's bones are segmented from his CT (voxel / slice size about 1 mm)"),
    "comb_m": (3.0, "the page's bones are Z-Anatomy bones fitted to his skeleton: surface distance 3.0 mm median (Q195 badge)"),
    "comb_f": (3.2, "the page's pelvic bones are Z-Anatomy bones deformed onto her pelvis: hip bone 2.0 mm, sacrum 3.15 mm median distance (Q250 badge; p90 7.4 / 11.3 mm)"),
    "base_f": (2.1, "the page's pelvic bones are Z-Anatomy bones deformed onto the Visible Human female's pelvis: 2.07 mm median (p90 5.67 mm; Q250 badge)"),
    "base_m": (0.0, "the page's bones are the native Z-Anatomy reference bones (no fit; the nerves are placed on those bones)"),
}
BADGE_HEAD = ("RULE-BASED (Q249): this nerve is NOT segmented from imaging, NOT dissected and NOT a Z-Anatomy object: a round tube of the cited calibre along a spline through waypoints that follow the documented course "
              "and are defined relative to bone landmarks measured on THIS page's own meshes")


class Builder:
    def __init__(self, P):
        self.P = P; self.A = Anat(P); self.gd, self.soft = self.A.gd, self.A.soft; self.ovl = NL.Overlap(P.E, self.gd)
        self.out = []; self.held = []; self.skipped = []
        self.own = P.key.startswith("own"); self.F = P.F
        self._skin_env = None

    def have(self, *ids):
        return any(i in self.P.E for i in ids)

    PERINEAL_SKIN_KW = ("perineal", "anal_region", "gluteal_fold", "gluteal_region", "femoral_triangle", "labi", "scrot", "mons", "pubi", "groin", "genital", "penis", "vulva")

    def _skin_envelope(self):
        """Lazily built, cached once per page: sample points + normals of the LOCAL skin patches around the perineum
        (name-matched by `PERINEAL_SKIN_KW`), used only for region="perineum" nerve waypoints (see `skin_depth_page`).
        `self.gd.skin_depth()` (q248/guards.py) is correct on 'own' (CT-segmented) pages, which carry ONE closed
        'skin' mesh, but on a Z page the skin is ~250 separate open regional patches with no single enclosing mesh,
        so it falls back there to an UNSIGNED nearest-point distance: a waypoint floating outside the body in a
        pocket with no nearby patch (e.g. a widened perineum after a pelvis warp) reads as a large positive 'depth'
        exactly like a point deep inside, and `min_skin` can never hold it.
        Getting a reliable SIGNED depth generically, from every one of the page's ~250 patches, turned out not to
        be safe: a single global flip (Q250's own skin-envelope guard, warp.py: sample every patch, then one sign
        decided by a majority vote of bone-interior points) correctly flips the large majority of patches whose raw
        winding points inward, but a few individual patches are wound the other way and were then wrongly inverted
        too (e.g. a deep lumbar patch, holding the otherwise-fine lumbosacral trunk by ~85 mm outside when it was
        actually ~85 mm inside); and orienting each patch from its OWN signed volume (`lig_pages.outward_normals`,
        the convention this codebase already uses for muscle / organ overlap) is wrong for a different reason: these
        are thin extruded shells (an outer, body-facing layer and an inner layer a fraction of a mm beneath it,
        closed into one watertight solid), so the volume-correct normal is right on the outer layer and backwards on
        the inner one. Scoped to just the handful of patches around the perineum (confirmed by direct per-face
        offset tests: raw, UNFLIPPED winding reads correctly outward on every one of them -- unlike the rest of the
        page, this local set is small enough, and close enough to the nerves being gated, to check by hand instead
        of by a vote) this is no longer a problem, and the nearest-patch search stays local to the actually-relevant
        anatomy instead of occasionally returning a distant, irrelevant patch (e.g. thigh skin) for a perineal point
        sitting in a concave fold."""
        if self._skin_env is not None:
            return self._skin_env
        from scipy.spatial import cKDTree
        E = self.P.E
        skin_ids = [i for i, e in E.items() if e.get("sys") == "skin" and len(e.get("f", [])) and any(k in i.lower() for k in self.PERINEAL_SKIN_KW)]
        if not skin_ids:
            self._skin_env = False
            return False
        Ps, Ns = [], []
        for i in skin_ids:
            m = trimesh.Trimesh(E[i]["v"], E[i]["f"], process=False)
            n = max(20, int(m.area / 8.0))
            p, fi = trimesh.sample.sample_surface(m, n, seed=0)
            Ps.append(p); Ns.append(m.face_normals[fi])
        Pp = np.vstack(Ps); Nn = np.vstack(Ns)
        self._skin_env = (cKDTree(Pp), Nn)
        return self._skin_env

    def skin_depth_page(self, V):
        """Signed skin depth of every vertex of V against the LOCAL perineal skin envelope (see `_skin_envelope`);
        same sign convention as q248/guards.py Guards.skin_depth: positive = inside (how deep), negative = outside
        (how far). Returns the worst (minimum = most-outside-or-least-inside) value, or None if the page has no
        perineal skin patches to check against (use only for region="perineum" waypoints: elsewhere a 'nearest
        local perineal patch' distance is meaningless)."""
        env = self._skin_envelope()
        if not env:
            return None
        tree, Nn = env
        d, j = tree.query(V)
        s = ((V - tree.data[j]) * Nn[j]).sum(1)
        return round(float(np.min(np.where(s < 0, d, -d))), 1)

    def order_check(self, path, side, vessel_ids):
        A = self.A; sg = SG[side]
        vid, C = A.vessel_center(vessel_ids)
        if C is None:
            return dict(n_samples=0, vessel=None)
        from scipy.spatial import cKDTree
        d, j = cKDTree(C).query(path)
        sel = d < 12.0
        if not sel.any():
            return dict(n_samples=0, vessel=vid)
        dx = sg * (path[sel, 0] - C[j[sel], 0])
        return dict(n_samples=int(sel.sum()), vessel=vid, medial_fraction=round(float((dx < 0).mean()), 3), mean_separation_mm=round(float(d[sel].mean()), 1))

    def best_end(self, prefix, cands, rad, skin=False):
        """the candidate end point whose spline (through prefix + candidate) has the smallest fraction of its length deeper than 1 mm inside bone (ties: the first); documented direction family only.
        skin=True (perineal-region searches with no anchor organ to rely on): candidates that end up closer than 2 mm to / outside the page's own skin envelope (`skin_depth_page`, every skin patch, signed
        via the bone-interior reference points -- the fix for the fact the page's skin is ~250 open regional patches, not one closed mesh) are strongly deprioritised, not merely bone-avoided; if every
        candidate of the family is outside, the least-bad one is still returned and `mk()`'s own `min_skin` gate holds the nerve (honest: no valid in-skin endpoint exists in the documented direction family)."""
        ctx = self.P.ctx; best = None
        for c in cands:
            Pth = NL.spline(list(prefix) + [c], 40)
            ids = ctx.near_bones(Pth, 25.0)
            sd = ctx.bf.signed(Pth, ids)[0] if ids else np.full(len(Pth), 9.0)
            sd_end = P_end = ctx.bf.signed(c[None], ids)[0][0] if ids else 9.0
            cost = float((sd < -1.0).mean()) + (1.0 if sd_end < rad else 0.0)
            if skin:
                sk = self.skin_depth_page(c[None])
                if sk is not None and sk < 2.0:
                    cost += 10.0 + max(0.0, 2.0 - sk)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, c)
        return best[1]

    def skip(self, nid, why):
        self.skipped.append(dict(id=nid, reason=why))

    def hold(self, nid, why, **kw):
        self.held.append(dict(id=nid, reason=why, **kw))
        self.out.append(dict(id=nid, status="held", held=[why], **kw))

    def mk(self, nid, name, latin, side, anchors, d, *, region, course, calibre, calibre_kind, lit_keys, err_lit_mm, err_text, min_skin=3.0, n=None, softpush=(), skin_pull=None, len_range=None,
           keep_end_free=False, ends=(None, None), extra_rep=None, order_note="", order_vessels=None, side_margin=3.0):
        P = self.P; ctx = P.ctx
        d0, d1 = (d, None) if np.isscalar(d) else d
        anchors = [np.asarray(a, float) for a in anchors]
        rad_a = d0 / 2
        for ia in range(len(anchors)):
            if True:
                pa, na, da = P.snap(anchors[ia])
                if da < rad_a + NL.CLEAR_EXTRA:
                    anchors[ia] = anchors[ia] + na * (rad_a + NL.CLEAR_EXTRA - da)
        raw_len = NL.path_len(np.array(anchors))
        n = n or int(np.clip(raw_len / 1.6, 16, 90))
        Pth = NL.spline(anchors, n)
        rad = np.full(len(Pth), d0 / 2) if d1 is None else np.linspace(d0 / 2, d1 / 2, len(Pth))
        for sid, marg in softpush:
            if sid in P.E:
                Q = self.soft.outside(sid, Pth, rad + marg)
                Pth[1:-1] = Q[1:-1]
        Pth = RL.smooth_path(Pth, 2)
        ids = ctx.near_bones(Pth, 25.0)
        sd_raw = ctx.bf.signed(Pth, ids)[0] if ids else np.full(len(Pth), 9.0)
        raw_frac = float((sd_raw < -1.0).mean())
        P_before = Pth.copy()
        Pth = NL.push_out_bones(ctx, Pth, rad)
        disp = float(np.linalg.norm(Pth - P_before, axis=1).max())
        if skin_pull is not None and self.own:
            Pth = RL.smooth_path(self.gd.skin_pull(Pth, skin_pull + d0 / 2), 2)
        V, Fc, c0, c1, dd = NL.tube_round(Pth, d0, d1)
        V, brep = NL.finish_bones(ctx, V, Fc, c0, c1)
        mm = trimesh.Trimesh(V, Fc, process=False)
        rep = dict(vertices=int(len(V)), triangles=int(len(Fc)), watertight=bool(mm.is_watertight), volume_mm3=round(float(abs(mm.volume)), 1), volume_cm3=round(float(abs(mm.volume)) / 1000, 4), **brep)
        L = NL.path_len(Pth)
        ov = self.ovl(V)
        sk = self.gd.skin_depth(V)
        if not self.own and region == "perineum":
            # local perineal skin envelope (see skin_depth_page): reliable close to the perineal skin itself, but
            # covers only a handful of patches, so a PROXIMAL waypoint (e.g. still in the pudendal canal, well inside
            # the pelvis) can be far enough from all of them to read a spurious sign; checked on the DISTAL 40 % of
            # the centreline only, the part of a perineal-region nerve that is actually meant to reach the skin.
            sk_p = self.skin_depth_page(Pth[int(len(Pth) * 0.6):])
            if sk_p is not None:                                  # more trustworthy there than the unsigned Z-page
                sk = sk_p if sk is None else min(sk, sk_p)         # fallback, so it can only pull the reported depth
                                                                    # DOWN (toward "more outside"), never mask it
        rep.update(length_mm=round(L, 1), straight_distance_mm=round(float(np.linalg.norm(Pth[-1] - Pth[0])), 1), diameter_mm=[round(float(dd.min()), 2), round(float(dd.max()), 2)],
                   raw_path_fraction_inside_bone=round(raw_frac, 3), push_out_displacement_max_mm=round(disp, 1), soft_overlap=ov, skin_min_depth_mm=sk, waypoints=[np.round(a, 1).tolist() for a in anchors])
        if extra_rep: rep.update(extra_rep)
        why = []
        if order_vessels:
            oc = self.order_check(Pth, side, order_vessels)
            rep["order_check_vs_pudendal_vessels"] = oc
            if oc.get("n_samples", 0) >= 4:
                order_note = (f"Order check against the page's {oc['vessel']}: {oc['n_samples']} path samples within 12 mm of it, the nerve lies medial to the vessel at {round(100 * oc['medial_fraction'])} % of them "
                              f"(textbook order at the ischial spine / in the pudendal canal: nerve medial to the vessels), mean separation {oc['mean_separation_mm']} mm. ")
                if oc["medial_fraction"] < 0.3: why.append(f"nerve lies lateral to the pudendal vessel at {round(100 * (1 - oc['medial_fraction']))} % of the samples (textbook order violated)")
            else:
                order_note = "Order check against the pudendal vessels: not applicable (no pudendal vessel of this page within 12 mm of the nerve). "
        if disp > 12.0: why.append(f"the push-out out of bone moved the path by {disp:.1f} mm (> 12 mm: the waypoints are inconsistent with the bones)")
        if raw_frac > NL.MAX_BONE_FRAC and disp > 6.0: why.append(f"{round(100 * raw_frac)} % of the raw path inside bone (> 20 %) and the push-out moved it by {disp:.1f} mm")
        if rep["vertices_deeper_1mm"]: why.append("tube vertices still > 1 mm in bone after the push-out")
        if not rep["watertight"]: why.append("tube not closed")
        if min_skin is not None and sk is not None and sk < min_skin: why.append(f"closer than {min_skin:g} mm to / outside the skin ({sk} mm)")
        if len_range and not (len_range[0] <= L <= len_range[1]): why.append(f"length {L:.0f} mm outside the plausible range {len_range[0]}-{len_range[1]} mm")
        xs = Pth[:, 0] - self.F["x_mid"]
        if side in "lr" and (SG[side] * np.median(xs) < side_margin or np.sign(xs.mean()) != SG[side]): why.append(f"not on its own side of the midline (median x offset < {side_margin:g} mm)")
        bres = BONE_RES[P.key][0]
        err = float(np.sqrt(err_lit_mm ** 2 + 3.0 ** 2 + bres ** 2))
        rep["waypoint_error_bound_mm"] = round(err, 1)
        rep["error_components_mm"] = dict(literature_variability=err_lit_mm, landmark_rule_allowance=3.0, bone_registration_residual=bres)
        rec = dict(name=name, latin=latin, folder="nerves", region=region, source="; ".join([LIT["gray"]] + [LIT[k] for k in lit_keys]))
        rec["notes"] = course
        rec["procedural_badge"] = self.badge(name, course, calibre, calibre_kind, rep, err, err_text, order_note)
        e = dict(id=nid, name=name, latin=latin, side=side, V=V, F=Fc, rec=rec, report=rep, status="ship" if not why else "held", held=why, cat="nerve", path=Pth, d=dd, cal_kind=calibre_kind, region=region)
        self.out.append(e)
        return e

    def badge(self, name, course, calibre, kind, rep, err, err_text, order_note):
        ov = rep["soft_overlap"]
        return (f"{BADGE_HEAD}. Course (Gray's Anatomy 1918 and the cited papers): {course} "
                f"Calibre: {calibre} ({'ASSUMPTION - no published diameter found' if kind == 'assumption' else 'published value'}); round cross-section {rep['diameter_mm'][0]}"
                f"{'' if rep['diameter_mm'][0] == rep['diameter_mm'][1] else '-' + str(rep['diameter_mm'][1])} mm, closed end caps. Length {rep['length_mm']} mm, volume {rep['volume_cm3']} cm3 (closed mesh). "
                f"Waypoint error bound about {err:.1f} mm ({err_text}; plus 3 mm landmark-rule allowance and {rep['error_components_mm']['bone_registration_residual']} mm bone residual ({BONE_RES[self.P.key][1]}), summed in quadrature). "
                f"Checks: {round(100 * rep['raw_path_fraction_inside_bone'])} % of the raw path inside bone before the push-out, no vertex deeper than 1 mm inside a bone after it ({rep['vertices_deeper_1mm']}); "
                f"{round(100 * ov['muscle_fraction_deeper_6mm'])} % of the vertices deeper than 6 mm inside a muscle (nerves run in fascial planes and enter their muscle: reported, not gated), "
                f"{round(100 * ov['organ_fraction_deeper_3mm'])} % inside an organ; depth inside the skin {rep['skin_min_depth_mm']} mm. {order_note}"
                "An estimate of position: the real course, calibre and branching of this nerve vary between people and are not resolved by CT or the cryosections.")


# ------------------------------------------------------------------------------------------------ pelvic nerve set
ROOT_D = {1: (6.1, "cited"), 2: (4.5, "assumption"), 3: (3.5, "assumption"), 4: (2.5, "assumption")}
ROOT_CAL = {1: "S1 root: Ebraheim 1997 width 9.8 x thickness 4.3 mm (male) / 8.6 x 4.3 mm (female) = area-equivalent round diameter 6.5 / 6.1 mm; Chaves 2018 MR neurography 5.4 mm",
            2: "S2 root: no published diameter found; 75 % of S1 (Ebraheim 1997: root width decreases from S1 to S3)",
            3: "S3 root: no published diameter found; 57 % of S1",
            4: "S4 root: no published diameter found; 41 % of S1"}


def pt_at(P, f):
    Pc = np.asarray(P, float); s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))]
    t = f * s[-1]
    return np.array([np.interp(t, s, Pc[:, i]) for i in range(3)])


def build(P, only=None, include_sex=True):
    B = Builder(P); A = B.A; F = P.F; ctx = P.ctx; E = P.E
    sex_m = not P.female
    gd, soft = B.gd, B.soft
    xm = F["x_mid"]
    Z = not P.key.startswith("own")
    want = (lambda k: True) if only is None else (lambda k: k in only)
    for s in "lr":
        sw = "left" if s == "l" else "right"; sg = SG[s]; m = np.array([-sg, 0.0, 0.0]); pt = A.pts[s]
        IS, IT, SP, E0 = pt["IS"], pt["IT"], pt["SP"], pt["E0"]
        # ---- sacral ventral rami S1-S4 (roots of the plexus) and the lumbosacral trunk
        for k in (1, 2, 3, 4):
            if not want("roots"): break
            Fk = P.lm[f"S{k}_foramen_{s}"]; Nk = P.lm[f"S{k}_normal_{s}"]
            dk, ckind = ROOT_D[k]
            start = Fk + Nk * (dk / 2 + 0.3)
            Ek = E0 + np.array([0, {1: 6.0, 2: 3.0, 3: 0.0, 4: -3.0}[k], 0]) + m * {1: 0.0, 2: 1.5, 3: 3.0, 4: 4.5}[k]
            mid = 0.5 * (start + Ek) + np.array([0, 0, 4.0])
            e = B.mk(f"s{k}_ventral_ramus_{s}", f"Ventral ramus of S{k} ({sw})", f"Ramus anterior nervi spinalis S{k} {'sinister' if s == 'l' else 'dexter'}", s, [start, mid, Ek], dk, region="pelvis",
                     course=(f"leaves the pelvic sacral foramen S{k}, runs laterally and downward on the anterior (pelvic) surface of piriformis and converges on the sacral plexus at the greater sciatic foramen below piriformis. "
                             f"Waypoints: A = S{k} anterior sacral foramen ({'fractions of the sacral height ' + str(LMK.FORAMEN_FRAC[k]) + ' and lateral distance ' + str(LMK.FORAMEN_LAT[k]) + ' mm at a half-width of 60 mm'}), B = midway, C = greater sciatic foramen point below piriformis "
                             f"(10 mm behind / 4 mm medial / 3 mm above the ischial spine). Distances of the S1 / S2 rami from the spine in dissections: 31 / 19 mm"),
                     calibre=ROOT_CAL[k], calibre_kind=ckind, lit_keys=["ebraheim97", "chaves18", "ebraheim98", "sra23"], err_lit_mm=8.0,
                     err_text="foramen position by proportion, half a foramen height 13 mm; dissection variability of the root positions about 8 mm (assumption)", len_range=(30, 140),
                     softpush=((A.find(f"piriformis_{s}") or "", 0.3),))
            A.ROOT[(k, s)] = e.get("path")
        if want("roots") and (1, s) in A.ROOT and A.ROOT[(1, s)] is not None:
            S1p = A.ROOT[(1, s)]
            J = pt_at(S1p, 0.30)
            prom = P.lm["promontory"]
            cands = [np.array([xm + sg * lx, prom[1] + dy, prom[2] + dz]) for lx in (30.0, 26.0, 34.0, 22.0) for dy in (4.0, 8.0, 0.0) for dz in (-8.0, -4.0, -12.0)]
            A0 = B.best_end([J], cands, 3.7)
            d_l = 6.9 if True else 0
            B.mk(f"lumbosacral_trunk_{s}", f"Lumbosacral trunk ({sw})", f"Truncus lumbosacralis {'sinister' if s == 'l' else 'dexter'}", s, [A0, 0.5 * (A0 + J) + np.array([0, 0, 3.0]), J], d_l, region="pelvis",
                 course=("L4 (part) + L5 ventral rami leave the lumbar spine at the L5-S1 level, descend over the sacral ala medial to the sacroiliac joint (2 cm below the pelvic brim) and join the S1 ramus. "
                         "Waypoints: A = 30 mm lateral to the sacral promontory at its level, B = midway, C = point on the S1 ramus 30 % of its length from the foramen"),
                 calibre=f"Ebraheim 1997 lumbosacral trunk 11.4 x 4.4 mm (male) / 11.2 x 4.0 mm (female) -> area-equivalent round diameter 7.1 / 6.7 mm; used {d_l} mm", calibre_kind="cited", lit_keys=["ebraheim97", "sra23"],
                 err_lit_mm=8.0, err_text="lumbosacral trunk 40 mm from the spine in dissections; length 30 +- 9 mm (Ebraheim 1997) sets the sanity window", len_range=(18, 55))
        # ---- inferior gluteal nerve
        if want("gluteal") and (1, s) in A.ROOT and A.ROOT[(1, s)] is not None:
            gm = A.find(f"gluteus_maximus_{s}")
            S1p = A.ROOT[(1, s)]
            if gm is None:
                B.hold(f"inferior_gluteal_n_{s}", "no gluteus maximus on the page")
            else:
                tgt, nn = soft.surface_point(gm, E0 + np.array([sg * 15.0, -10.0, -40.0]), margin=-5.0)
                B.mk(f"inferior_gluteal_n_{s}", f"Inferior gluteal nerve ({sw})", f"Nervus gluteus inferior {'sinister' if s == 'l' else 'dexter'}", s,
                     [pt_at(S1p, 0.60), E0 + np.array([0, 5.0, 0]) + m * 2, 0.5 * (E0 + tgt) + np.array([0, 4.0, 0]), tgt], 3.0, region="gluteal",
                     course=("arises from the dorsal divisions of L5, S1 and S2 (dorsal surface of the combined lumbosacral trunk + S1), leaves the pelvis through the greater sciatic foramen below piriformis, "
                             "runs 28.5 mm (6-53) from the ischial spine and divides into branches that enter the deep surface of gluteus maximus. Waypoints: S1 ramus 60 %, greater sciatic foramen point, "
                             "point 40 mm behind / 15 mm lateral / 10 mm below it, end = 5 mm inside the deep surface of gluteus maximus"),
                     calibre="inferior gluteal nerve trunk: no published diameter found (its cutaneous branch is 0.7 mm, Clin Anat 2018); 3.0 mm = ASSUMPTION ('a few millimetres', Skeletal Radiol 2023)", calibre_kind="assumption",
                     lit_keys=["ssl16", "igncut18", "mrn23"], err_lit_mm=20.0, err_text="distance of the nerve from the ischial spine in dissections 28.5 mm, range 6-53 mm (half range about 20 mm)", len_range=(30, 140))
        # ---- nerve to obturator internus
        if want("oi") and (1, s) in A.ROOT and A.ROOT[(1, s)] is not None:
            oi = A.find(f"obturator_internus_{s}")
            if oi is None:
                B.hold(f"nerve_to_obturator_internus_{s}", "no obturator internus on the page")
            else:
                T, nn = soft.surface_point(oi, IS + m * 3 + np.array([0, -18.0, 12.0]), margin=0.3)
                B.mk(f"nerve_to_obturator_internus_{s}", f"Nerve to obturator internus (+ superior gemellus) ({sw})", f"Nervus musculi obturatorii interni {'sinister' if s == 'l' else 'dexter'}", s,
                     [pt_at(A.ROOT[(1, s)], 0.85), E0 + np.array([sg * 4.0, 0, 0]), pt["ISpost"] + np.array([sg * 5.0, -1.0, -1.0]), pt["CW0"] + np.array([sg * 5.0, 0, 1.0]), T], 2.0, region="pelvis",
                     course=("from the ventral divisions of L5, S1, S2, leaves the pelvis through the greater sciatic foramen below piriformis, crosses the ischial spine lateral to the pudendal vessels (0.7 cm from the spine), "
                             "passes through the lesser sciatic foramen and enters obturator internus on its pelvic surface (gives the nerve to superior gemellus on the way)"),
                     calibre="no published diameter of this nerve found; 2.0 mm = ASSUMPTION (obturator nerve branches 1.8-2.6 mm, Microsurgery; small nerves 'a few mm', Skeletal Radiol 2023)", calibre_kind="assumption",
                     lit_keys=["sra23", "mrn23"], err_lit_mm=7.0, err_text="distance from the ischial spine 0.7 cm, variability unknown (about 7 mm assumed)", len_range=(25, 110), softpush=((oi, 0.3),))
        # ---- pudendal canal anchors (vessel-following where the page has the pudendal vessels) and branches
        if want("pudendal"):
            rn = 2.0
            can = [c.copy() for c in pt["canal"]]
            oi_id = A.find(f"obturator_internus_{s}")
            if oi_id:
                for ic, c in enumerate(can):
                    q = soft.surface_point(oi_id, c, margin=rn + 0.3, direction=vec(m + np.array([0, -0.6, 0.0])), thr=0.2, maxdist=14.0)[0]
                    if q is not None:
                        can[ic] = q
            ves_ids = [f"zan_internal_pudendal_vein_{s}", f"zan_internal_pudendal_artery_{s}", f"internal_pudendal_v_{s}", f"internal_pudendal_a_{s}"]
            info = []
            adj = []
            for c in can:
                w, vi = A.vessel_adjust(s, c, rn, ves_ids)
                adj.append(w); info.append(vi)
            used = [i for i in info if i and i.get("used")]
            vinfo = dict(vessel_anchor=(info[0] or {}).get("vessel"), canal_points_following_vessel=len(used), of=len(can))
            canal = adj
            pt["canal_adj"] = canal
            pt["vinfo"] = vinfo
            T_dn = None
            zt = f"pudendal_n_{s}"
            if Z and zt in E:
                from scipy.spatial import cKDTree
                dz = cKDTree(E[zt]["v"]).query(np.array(canal[:4]))[0]
                B.skip(zt, f"the Z page carries {zt} (trunk, Z-Anatomy fit): kept, only its branches are added; distance of the Z trunk mesh from the rule canal points: mean {dz.mean():.1f} mm, max {dz.max():.1f} mm")
                vinfo["z_trunk_to_rule_canal_mm"] = dict(mean=round(float(dz.mean()), 1), max=round(float(dz.max()), 1))
            if not Z:
                trunk_start = pt_at(A.ROOT[(3, s)], 0.70) if (3, s) in A.ROOT and A.ROOT[(3, s)] is not None else E0
                B.mk(f"pudendal_n_{s}", f"Pudendal nerve ({sw})", f"Nervus pudendus {'sinister' if s == 'l' else 'dexter'}", s,
                     [trunk_start, E0 + m * 2, pt["ISpost"], pt["CW0"], canal[0], canal[1], canal[2], canal[3]], (4.7, 3.0), region="pelvis",
                     course=("from the ventral divisions of S2-S4, leaves the pelvis through the greater sciatic foramen below piriformis, crosses the posterior aspect of the ischial spine (medial to the spine, 0.6 cm, behind the sacrospinous ligament), "
                             "enters the lesser sciatic foramen and runs forward in the pudendal (Alcock's) canal on the medial surface of obturator internus 3-4 cm above the lower margin of the ischial tuberosity, with the internal pudendal vessels, "
                             "to the posterior border of the perineal membrane where it divides into the perineal nerve and the dorsal nerve of the penis / clitoris. Canal waypoints = ischial tuberosity -> subpubic angle line shifted 10 mm medially and 34 -> 10 mm up "
                             + ("; the internal pudendal vessels of this page were followed (" + str(vinfo) + ")" if vinfo["canal_points_following_vessel"] else "; no pudendal vessel of this page lies within 15 mm of the rule course (own bones only)")),
                     calibre="pudendal trunk 4.67 +- 1.17 mm near the sacrospinous ligament (Clin Anat 2005), 5.2 / 4.9 mm over the spine (Dis Colon Rectum 2000); distal 3.0 mm (donor nerve, JPRAS 2023): tapered 4.7 -> 3.0 mm", calibre_kind="cited",
                     lit_keys=["pn05", "pn00", "pn23", "ssl16", "pfn07"], err_lit_mm=6.0, err_text="pudendal nerve 0.6 +- 0.4 cm medial to the spine, distance from the spine 0-9 mm (median 0)", len_range=(70, 200), softpush=((A.find(f"obturator_internus_{s}") or "", 0.3),), order_vessels=ves_ids)
            # inferior rectal nerve: from the canal (back part) across the ischioanal fossa to the external anal sphincter
            eas = A.find("external_anal_sphincter", "zan_external_anal_sphincter")
            if want("irn"):
                if eas is None:
                    B.hold(f"inferior_rectal_n_{s}", "no external anal sphincter on the page")
                else:
                    Jir = 0.7 * canal[0] + 0.3 * canal[1]
                    kd_, nn_ = soft.field(eas)
                    order = np.argsort(np.linalg.norm(kd_.data - Jir, axis=1))[:40:2]
                    cands = [kd_.data[o] + nn_[o] * 0.3 for o in order]
                    T = B.best_end([Jir], cands, 1.0)
                    mid = 0.5 * (Jir + T) + np.array([0, -2.0, 0])
                    B.mk(f"inferior_rectal_n_{s}", f"Inferior rectal nerve ({sw})", f"Nervus rectalis inferior {'sinister' if s == 'l' else 'dexter'}", s, [Jir, mid, T], 1.5, region="perineum",
                         course=("leaves the pudendal nerve in the back part of the pudendal canal, crosses the ischioanal fossa medially and divides on the lateral wall of the anal canal to supply the external anal sphincter and the perianal skin. "
                                 "Waypoints: junction on the canal (70 % canal point 0 + 30 % point 1), midway, nearest surface point of the external anal sphincter of this page. 1 / 2 / 3 branches in 13 / 76 / 11 % (one is drawn)"),
                         calibre="no adult diameter found (fetal pudendal trunk 0.98 mm); 1.5 mm = ASSUMPTION", calibre_kind="assumption", lit_keys=["pn00", "pfn07"], err_lit_mm=7.0,
                         err_text="inferior rectal nerve length 27 mm (20-34, Dis Colon Rectum 2000); origin variants (IRN piercing the ligament in 40 %)", len_range=(12, 70), extra_rep=dict(junction_vessel=vinfo), order_vessels=ves_ids)
            # dorsal nerve of the penis / clitoris and perineal nerve
            Jpd = canal[3]
            if want("dorsal"):
                B_dorsal(B, A, P, s, sw, sg, m, canal, Jpd, vinfo, sex_m, ves_ids)
            if want("perineal"):
                cands = [Jpd + m * md + np.array([0, dn, an]) for dn in (-20.0, -26.0, -14.0, -32.0) for md in (8.0, 12.0, 4.0, 16.0) for an in (6.0, 0.0, 12.0)]
                cands = [c for c in cands if sg * (c[0] - xm) > 4.0] or cands
                mids = [Jpd + m * a + np.array([0, b, c]) for a in (5.0, 2.0, 9.0) for b in (-8.0, -4.0, -12.0) for c in (4.0, 0.0, 8.0)]
                mids = [c for c in mids if sg * (c[0] - xm) > 4.0] or mids
                best = None
                for md_ in mids:
                    t_ = B.best_end([Jpd, md_], cands, 1.3, skin=True)
                    Pth_ = NL.spline([Jpd, md_, t_], 40); ids_ = P.ctx.near_bones(Pth_, 25.0)
                    sd_ = P.ctx.bf.signed(Pth_, ids_)[0] if ids_ else np.full(len(Pth_), 9.0)
                    cost_ = float((sd_ < -1.0).mean())
                    sk_ = B.skin_depth_page(t_[None])
                    if sk_ is not None and sk_ < 2.0:
                        cost_ += 10.0 + max(0.0, 2.0 - sk_)
                    if best is None or cost_ < best[0] - 1e-9:
                        best = (cost_, md_, t_)
                _, Pm, Tn = best
                B.mk(f"perineal_n_{s}", f"Perineal nerve - {'posterior scrotal' if sex_m else 'posterior labial'} branches ({sw})", f"Nervus perinealis {'sinister' if s == 'l' else 'dexter'}", s,
                     [Jpd, Pm, Tn], 2.0, region="perineum",
                     course=("the larger terminal branch of the pudendal nerve, below the perineal membrane in the superficial perineal pouch; gives the posterior scrotal (male) / posterior labial (female) nerves to the skin and the "
                             "motor branches to the superficial perineal muscles. Waypoints: terminal division of the pudendal nerve (canal point 3), 5 mm medial / 8 mm down, end = the point of a family (4-16 mm medial, 14-32 mm down, 0-12 mm forward of the division) whose path stays out of bone"),
                     calibre="no published diameter found; 2.0 mm = ASSUMPTION (between the pudendal trunk 3.0 mm and the dorsal nerve 1.9-2.6 mm)", calibre_kind="assumption", lit_keys=["pn23", "dnc20", "dnc21"], err_lit_mm=8.0,
                     err_text="terminal branching pattern varies (single / double / triple trunk)", len_range=(15, 80), skin_pull=4.0, min_skin=2.0, extra_rep=dict(junction_vessel=vinfo), order_vessels=ves_ids)
        more_nerves(B, A, P, s, sw, sg, m, want, Z)
    if want("hypogastric"):
        midline_autonomic(B, A, P, want)
    if want("medial"):
        medial_branches(B, A, P)
    if want("abdominal"):
        abdominal_nerves(B, A, P, Z)
    if want("recurrent"):
        recurrent_branches(B, A, P)
    return B


def B_dorsal(B, A, P, s, sw, sg, m, canal, Jpd, vinfo, sex_m, ves_ids):
    E = P.E; soft = B.soft
    SP = P.lm[f"subpubic_{s}"]
    if sex_m:
        cc = A.find("corpus_cavernosum_penis", "zan_corpus_cavernosum_of_penis")
        if cc is None:
            return B.hold(f"dorsal_n_penis_{s}", "no corpus cavernosum on the page")
        C = LMK.centerline(E[cc]["v"], E[cc]["f"], 30)
        if C is None:
            return B.hold(f"dorsal_n_penis_{s}", "corpus cavernosum centre line not found")
        if np.linalg.norm(C[0] - SP) > np.linalg.norm(C[-1] - SP):
            C = C[::-1]
        Cs = np.array([C[0] + (C[1] - C[0]) * 0.0] + [C[i] for i in range(len(C))])
        # shaft radius = median distance of the mesh to the centre line
        from scipy.spatial import cKDTree
        R = float(np.median(cKDTree(C).query(E[cc]["v"])[0]))
        tang = np.gradient(C, axis=0); tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        dors = np.array([0.0, 0.5, 0.87])                  # dorsal = toward the pubis / anterior, the penis hangs down
        off = []
        for i, c in enumerate(C):
            dd = dors - (dors @ tang[i]) * tang[i]; dd /= np.linalg.norm(dd) + 1e-9
            lat = np.array([sg, 0, 0.0]); lat = lat - (lat @ tang[i]) * tang[i]; lat /= np.linalg.norm(lat) + 1e-9
            off.append(c + (R + 1.5) * (0.8 * dd + 0.6 * lat))
        off = np.array(off)
        pick = off[[int(round(x)) for x in np.linspace(len(off) * 0.12, len(off) - 1, 6)]]
        anchors = [Jpd, canal[4], *pick]
        B.mk(f"dorsal_n_penis_{s}", f"Dorsal nerve of the penis ({sw})", f"Nervus dorsalis penis {'sinister' if s == 'l' else 'dexter'}", s, anchors, (3.7, 1.6), region="perineum",
             course=("terminal branch of the pudendal nerve; runs forward along the medial aspect of the inferior pubic ramus in the deep perineal pouch, passes beneath the pubic arch between the arcuate pubic ligament and the transverse perineal ligament, "
                     "and runs on the dorsolateral surface of the penile shaft lateral to the dorsal artery to the glans. Waypoints: terminal division of the pudendal nerve (canal point 3), subpubic angle, then the dorsolateral line of the corpus cavernosum "
                     f"({cc}; shaft radius {R:.1f} mm measured on the page, nerve centre {R + 1.5:.1f} mm from the axis at 10 o'clock / 2 o'clock)"),
             calibre="dorsal nerve of the penis proper 3.7 mm, its branches 1.6 mm (Orr Shauly 2021, 3 cadavers): tapered 3.7 -> 1.6 mm", calibre_kind="cited", lit_keys=["dnp21", "dnp14", "pn23"], err_lit_mm=6.0,
             err_text="penile shaft position of the page (organ transferred / fitted), 2-6 main branches in dissections (one drawn)", len_range=(60, 340), softpush=((cc, 0.3),), min_skin=None, extra_rep=dict(junction_vessel=vinfo), order_vessels=ves_ids, side_margin=0.5)
    else:
        cc = A.find("clitoris_cavernous_body")
        if cc is None:
            return B.hold(f"dorsal_n_clitoris_{s}", "no clitoris on the page")
        v = E[cc]["v"]
        tip = v[np.argmax((v - SP) @ vec([0, -0.3, 1.0]))].copy()
        tip[0] = P.F["x_mid"] + sg * 1.5          # the two dorsal nerves meet at the glans: each ends 1.5 mm on its own side of the midline
        mid = 0.5 * (SP + tip)
        B.mk(f"dorsal_n_clitoris_{s}", f"Dorsal nerve of the clitoris ({sw})", f"Nervus dorsalis clitoridis {'sinister' if s == 'l' else 'dexter'}", s, [Jpd, canal[4], mid, tip], (2.6, 1.9), region="perineum",
             course=("terminal branch of the pudendal nerve; runs forward along the inferior pubic ramus in the deep perineal pouch, passes beneath the pubic arch, runs on the dorsolateral surface of the clitoral body and ends in the glans "
                     f"(traceable to within 6 mm of the glans). Waypoints: terminal division of the pudendal nerve (canal point 3), subpubic angle, midway, glans end of the clitoral body ({cc}: vertex farthest forward / down)"),
             calibre="dorsal nerves of the clitoris 2.0-3.2 mm along the body (Aesthet Surg J 2020), 1.9 +- 0.3 mm distally (JPRAS 2021): tapered 2.6 -> 1.9 mm", calibre_kind="cited", lit_keys=["dnc20", "dnc21", "pn23"], err_lit_mm=5.0,
             err_text="position of the clitoral body of the page (CVH-derived, registered), 2.0-3.2 mm calibre range", len_range=(25, 260), softpush=((cc, 0.3),), min_skin=None, extra_rep=dict(junction_vessel=vinfo), order_vessels=ves_ids, side_margin=0.5)


def organ_ids(A, *c):
    return [i for i in c if i in A.E]


def more_nerves(B, A, P, s, sw, sg, m, want, Z):
    E = P.E; soft = B.soft; pt = A.pts[s]; F = P.F
    IS, E0 = pt["IS"], pt["E0"]
    S4p = A.ROOT.get((4, s)); S1p = A.ROOT.get((1, s)); S2p = A.ROOT.get((2, s))
    lat = "sinister" if s == "l" else "dexter"
    cg = A.find(f"coccygeus_{s}"); la = A.find(f"levator_ani_{s}")
    # ---- nerve to coccygeus and nerve to levator ani (S3-S5)
    if want("pelvicfloor") and S4p is not None:
        r_ = 0.5
        if cg is None:
            B.hold(f"nerve_to_coccygeus_{s}", "no coccygeus on the page")
        else:
            c = 0.5 * (pt_at(S4p, 0.45) + IS)
            T, _ = soft.surface_point(cg, c, margin=r_ + 0.3, direction=vec(m + np.array([0, 1.0, 0.3])), thr=0.0)
            B.mk(f"nerve_to_coccygeus_{s}", f"Nerve to coccygeus ({sw})", f"Nervus musculi coccygei {lat}", s, [pt_at(S4p, 0.45), 0.5 * (pt_at(S4p, 0.45) + T), T], 1.0, region="pelvis",
                 course=("branches of S3 / S4 (S5) leave the sacral ventral rami close to the foramina, run over the pelvic surface of the sacrospinous ligament - coccygeus complex and perforate the ventral surface of coccygeus (94 % of 14 female cadavers). "
                         "Waypoints: S4 ramus at 45 % of its length, midway, nearest pelvic (superior-medial) surface point of the page's coccygeus to the midpoint of that point and the ischial spine"),
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine motor branch)", calibre_kind="assumption", lit_keys=["ssl16", "lan15", "pfn07"], err_lit_mm=7.0,
                 err_text="the S3 nerve lies 3 mm (0-11) from the superior border of the ligament; the exact entry point is not documented", len_range=(12, 90))
        if la is None or cg is None:
            B.hold(f"nerve_to_levator_ani_{s}", "no levator ani / coccygeus on the page")
        else:
            W, _ = soft.surface_point(cg, IS + m * 25 + np.array([0, 2.0, -6.0]), margin=r_ + 0.3, direction=vec(m + np.array([0, 1.0, 0.3])), thr=0.0)
            T, _ = soft.surface_point(la, IS + m * 35 + np.array([0, -8.0, 22.0]), margin=r_ + 0.3, direction=vec(np.array([0.3 * -sg, 1.0, 0.2])), thr=0.0)
            B.mk(f"nerve_to_levator_ani_{s}", f"Nerve to levator ani ({sw})", f"Nervus musculi levatoris ani {lat}", s, [pt_at(S4p, 0.35), W, 0.5 * (W + T), T], 1.0, region="pelvis",
                 course=("arises from S4 (+ S5; S3 in 15 %), crosses the superior (pelvic) surface of the sacrospinous - coccygeus complex about 2.5 cm medial to the ischial spine (42 %: penetrates coccygeus and runs on the inferior surface of levator ani; "
                         "58 %: continues on the superior surface of iliococcygeus; the superior-surface course is drawn). Waypoints: S4 ramus at 35 %, pelvic surface of coccygeus 25 mm medial / 6 mm behind the spine, pelvic surface of the page's levator ani 35 mm medial / 22 mm in front"),
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine motor branch)", calibre_kind="assumption", lit_keys=["lan15", "pfn07", "ssl16"], err_lit_mm=7.0,
                 err_text="levator ani nerve 2.5 +- 0.7 cm medial to the ischial spine (SD 7 mm); two documented terminal patterns", len_range=(30, 140))
    # ---- coccygeal plexus and anococcygeal nerve
    if want("coccygeal") and S4p is not None:
        sv = P.sac_v; ye = P.sac["y_end"]; tip = P.lm["coccyx_tip"]
        cxv = np.vstack([sv[sv[:, 1] < ye + 2]] + ([E["coccyx"]["v"]] if "coccyx" in E else []))
        ymid = 0.5 * (ye + tip[1])
        mm = (np.abs(cxv[:, 1] - ymid) < 4) & (sg * (cxv[:, 0] - F["x_mid"]) > 0)
        mt = (np.abs(cxv[:, 1] - (tip[1] + 6)) < 4) & (sg * (cxv[:, 0] - F["x_mid"]) > -1)
        if mm.sum() and mt.sum():
            Lm = cxv[mm][np.argmax(sg * cxv[mm][:, 0])] + np.array([sg * 1.0, 0, 0])
            Lt = cxv[mt][np.argmax(sg * cxv[mt][:, 0])] + np.array([sg * 1.0, 0, 0])
            e = B.mk(f"coccygeal_plexus_{s}", f"Coccygeal plexus ({sw})", f"Plexus coccygeus {lat}", s, [pt_at(S4p, 0.28), 0.5 * (pt_at(S4p, 0.28) + Lm), Lm, Lt], 1.0, region="pelvis",
                     course=("small plexus on the pelvic surface of coccygeus formed by a descending branch of S4, the S5 ventral ramus (emerging from the sacral hiatus) and the coccygeal nerve, which wrap around the lateral margin of the coccyx; "
                             "the anococcygeal nerves arise from it. Waypoints: S4 ramus at 28 %, lateral margin of the sacrococcygeal column at mid-height of the lowest sacral segment and coccyx, lateral margin 6 mm above the coccygeal tip"),
                     calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine plexus cord)", calibre_kind="assumption", lit_keys=["ssl16"], err_lit_mm=8.0, err_text="plexus formation varies between people (S4-S5-Co1 contributions); no quantitative dissection found", len_range=(20, 110))
            if e.get("status") == "ship" or True:
                Tt = tip + np.array([sg * 7.0, -12.0, -8.0])
                B.mk(f"anococcygeal_n_{s}", f"Anococcygeal nerve ({sw})", f"Nervus anococcygeus {lat}", s, [Lt, 0.5 * (Lt + Tt), Tt], 0.8, region="perineum",
                     course=("arises from the coccygeal plexus, pierces coccygeus and the sacrotuberous ligament and supplies the skin between the coccyx and the anus. Waypoints: lateral coccygeal margin 6 mm above the tip, midway, 7 mm lateral / 12 mm below / 8 mm behind the coccygeal tip"),
                     calibre="no published diameter found; 0.8 mm = ASSUMPTION (cutaneous twig)", calibre_kind="assumption", lit_keys=["ssl16"], err_lit_mm=8.0, err_text="2-4 anococcygeal nerves in textbooks, no quantitative dissection found",
                     len_range=(8, 60), skin_pull=3.0, min_skin=2.0)
    # ---- own pages only: nerve to quadratus femoris and posterior femoral cutaneous nerve (Z pages carry both under their ids)
    qf = A.find(f"quadratus_femoris_{s}")
    if want("qf"):
        if not Z and S1p is not None:
            if qf is None:
                B.hold(f"nerve_to_quadratus_femoris_{s}", "no quadratus femoris on the page")
            else:
                cqf = E[qf]["v"].mean(0)
                T, _ = soft.surface_point(qf, cqf + np.array([0, 0, 12.0]), margin=1.3, direction=vec(np.array([0, 0, 1.0])), thr=0.3)
                B.mk(f"nerve_to_quadratus_femoris_{s}", f"Nerve to quadratus femoris (+ inferior gemellus) ({sw})", f"Nervus musculi quadrati femoris {lat}", s,
                     [pt_at(S1p, 0.85), E0 + m * 1 + np.array([0, -1.0, 0]), 0.5 * (E0 + T) + np.array([sg * 4.0, -4.0, 2.0]), T], 2.0, region="gluteal",
                     course=("from the ventral divisions of L4, L5, S1, leaves the pelvis through the greater sciatic foramen below piriformis anterior to the sciatic nerve, descends on the posterior surface of the ischium / hip capsule deep to the sciatic nerve, "
                             "gemelli and obturator internus tendon and enters the anterior surface of quadratus femoris (gives the nerve to inferior gemellus). Waypoints: S1 ramus at 85 %, greater sciatic foramen point, midway, anterior surface of the page's quadratus femoris"),
                     calibre="no published diameter found; 2.0 mm = ASSUMPTION ('a few millimetres', Skeletal Radiol 2023)", calibre_kind="assumption", lit_keys=["mrn23", "sra23"], err_lit_mm=8.0, err_text="no quantitative dissection of its course found; distance of the sciatic nerve from the spine 1.4 cm", len_range=(35, 140))
        elif Z:
            B.skip(f"nerve_to_quadratus_femoris_{s}", "the Z page already carries nerve_to_quadratus_femoris_l/r")
    if want("pfcn"):
        if Z:
            B.skip(f"posterior_femoral_cutaneous_n_{s}", "the Z page already carries posterior_femoral_cutaneous_n_l/r")
        else:
            pfcn(B, A, P, s, sw, sg, m, S2p)


def midline_autonomic(B, A, P, want):
    E = P.E; soft = B.soft; F = P.F; xm = F["x_mid"]
    prom = P.lm["promontory"]
    B0 = prom + np.array([0, 6.0, 12.0])
    viscera = organ_ids(A, "rectum", "zan_sigmoid_colon", "urinary_bladder", "zan_urinary_bladder", "uterus", "vagina", "prostate", "zan_prostate")
    # superior hypogastric plexus: midline, in front of L5 / S1 below the aortic bifurcation
    cands = [B0 + np.array([0, dy, dz]) for dy in (34.0, 28.0, 40.0, 22.0) for dz in (3.0, 8.0, 14.0, -2.0)]
    top = B.best_end([B0], cands, 2.5)
    B.mk("superior_hypogastric_plexus", "Superior hypogastric plexus", "Plexus hypogastricus superior", "m", [top, 0.5 * (top + B0) + np.array([0, 0, 1.5]), B0], 4.5, region="pelvis",
         course=("a flat network (mesh 65 %, single nerve 24 %, fibres 11 %) in front of the lower lumbar vertebrae and the sacral promontory, below the aortic bifurcation, between the common iliac vessels; it divides into the two hypogastric nerves "
                 "(bifurcation cranial to the promontory in 80 %). Drawn as ONE midline cord: from 34 mm above the bifurcation point (6 mm above and 12 mm in front of the promontory) down to it"),
         calibre="plexus width / length not used; the cord is drawn with the hypogastric-nerve width 4.35-4.62 mm (Kutlu 2022) = rounded 4.5 mm; true cross-section is a flat band: the volume is an upper bound", calibre_kind="cited", lit_keys=["kutlu22"], err_lit_mm=8.0,
         err_text="bifurcation 8.5 +- 8.0 mm from the left common iliac vein, 13.4 +- 9.8 mm from the right internal iliac artery (Kutlu 2022)", len_range=(20, 70), min_skin=None)
    for s in "lr":
        sg = SG[s]; sw = "left" if s == "l" else "right"; lat = "sinister" if s == "l" else "dexter"; m = np.array([-sg, 0, 0.0])
        F3, N3 = P.lm[f"S3_foramen_{s}"], P.lm[f"S3_normal_{s}"]
        rect = A.find("rectum", "zan_sigmoid_colon")
        ihp = None
        if rect is not None:
            rv = E[rect]["v"]
            mk_ = (np.abs(rv[:, 1] - F3[1]) < 10) & (sg * (rv[:, 0] - xm) > 0)
            if mk_.sum() > 5:
                lv = rv[mk_][np.argmax(sg * rv[mk_][:, 0])]
                ihp = lv + np.array([sg * 6.0, 0, 0])
        if ihp is None:
            ihp = F3 + N3 * 32.0 + np.array([sg * 8.0, 0, 0])
        pp, nn_, dd_ = P.snap(ihp)
        if dd_ < 6.0:
            ihp = ihp + nn_ * (6.0 - dd_)
        A.pts[s]["IHP"] = ihp
        mid = 0.5 * (B0 + ihp) + np.array([sg * 5.0, 0, 6.0])
        B.mk(f"hypogastric_n_{s}", f"Hypogastric nerve ({sw})", f"Nervus hypogastricus {lat}", s, [B0 + np.array([sg * 2.0, 0, 0]), mid, ihp], 4.5, region="pelvis",
             course=("the sympathetic continuation of the superior hypogastric plexus, runs down in front of the sacrum and lateral to the rectum / mesorectum, medial to the internal iliac vessels and ureter (ureter 24-28 mm lateral to the bifurcation), "
                     "to the inferior hypogastric (pelvic) plexus at the level of S3-S4 on the side of the rectum. Waypoints: bifurcation point, midway (5 mm lateral, 6 mm forward), inferior hypogastric point = 32 mm in front of the S3 anterior foramen + 8 mm lateral, kept 6 mm outside the pelvic viscera of the page"),
             calibre="width 4.35 (left) / 4.62 (right) mm at 2 cm below the SHP bifurcation (Kutlu 2022, 45 cadavers) -> 4.5 mm round (the real nerve is a flattened band, the volume is an upper bound)", calibre_kind="cited", lit_keys=["kutlu22"], err_lit_mm=10.0,
             err_text="position relative to the sacrum / rectum varies with the mesorectal anatomy; no per-landmark SD found", len_range=(40, 140), softpush=tuple((v, 1.5) for v in viscera), min_skin=None)
        ihp_top = ihp
        ihp_end = ihp + np.array([-sg * 2.0, -12.0, 24.0])
        B.mk(f"inferior_hypogastric_plexus_{s}", f"Inferior hypogastric (pelvic) plexus ({sw})", f"Plexus hypogastricus inferior {lat}", s, [ihp_top, 0.5 * (ihp_top + ihp_end), ihp_end], 3.0, region="pelvis",
             course=("a plate of nerve fibres and ganglion cells on the side of the rectum (and of the vagina / prostate, bladder base) receiving the hypogastric nerve and the pelvic splanchnic nerves and giving the visceral branches; "
                     "drawn as one cord from the point where the hypogastric nerve ends 12 mm down and 24 mm forward along the side of the pelvic viscera"),
             calibre="plate dimensions are not available as a diameter (a Surg Radiol Anat 2010 quantitative study reports sizes, not read here); 3.0 mm = ASSUMPTION for the drawn cord", calibre_kind="assumption", lit_keys=["kutlu22"], err_lit_mm=10.0,
             err_text="position varies with organ filling and the mesorectal anatomy", len_range=(15, 60), softpush=tuple((v, 1.5) for v in viscera), min_skin=None)
        for k in (2, 3, 4):
            Rk = A.ROOT.get((k, s))
            if Rk is None: continue
            st = pt_at(Rk, 0.10)
            tgt = ihp + np.array([0, {2: 5.0, 3: 0.0, 4: -5.0}[k], 0])
            B.mk(f"pelvic_splanchnic_n_s{k}_{s}", f"Pelvic splanchnic nerve S{k} ({sw})", f"Nervus splanchnicus pelvicus S{k} {lat}", s, [st, 0.5 * (st + tgt) + np.array([0, 0, 4.0]), tgt], 1.0, region="pelvis",
                 course=(f"parasympathetic preganglionic fibres from the S{k} ventral ramus (S2-S4 'nervi erigentes') run forward on the side of the rectum to the inferior hypogastric plexus. Waypoints: S{k} ramus at 10 % of its length, midway, the inferior hypogastric point (S2 5 mm above, S4 5 mm below that of S3)"),
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine autonomic branch)", calibre_kind="assumption", lit_keys=["kutlu22"], err_lit_mm=10.0, err_text="course not quantified in the dissections found; follows the S3-S4 anatomy of the plexus", len_range=(12, 110),
                 softpush=tuple((v, 1.5) for v in viscera), min_skin=None)


def medial_branches(B, A, P):
    """medial branches of the lumbar dorsal rami (facet-joint radiofrequency targets): L1-L4 medial branches cross the junction of the superior articular process and the transverse-process root of the vertebra below
    (L2..L5); the L5 dorsal ramus runs in the groove between the S1 superior articular process and the sacral ala."""
    E = P.E; xm = P.F["x_mid"]
    lum = P.lumbar()
    if lum is None:
        B.hold("medial_branches", "lumbar vertebrae L1-L5 not found on the page"); return
    for s in "lr":
        sg = SG[s]; sw = "left" if s == "l" else "right"; lat = "sinister" if s == "l" else "dexter"; m = np.array([-sg, 0, 0.0])
        for n in (1, 2, 3, 4, 5):
            if n < 5:
                vid = lum[n]                              # vertebra below: L2 for the L1 medial branch ... L5 for the L4 medial branch
                v = E[vid]["v"]; side = v[sg * (v[:, 0] - xm) > 0]
                ytop = float(np.percentile(side[:, 1], 98)); hgt = float(np.percentile(side[:, 1], 98) - np.percentile(side[:, 1], 2))
                win = (np.abs(side[:, 0] - xm) > 16) & (np.abs(side[:, 0] - xm) < 32) & (side[:, 1] > ytop - 0.42 * hgt) & (side[:, 1] < ytop - 0.08 * hgt)
                bone_id = vid; below = f"L{n + 1}"
            else:
                sacr = [i for i in P.sac_ids if i.startswith("sacrum")]
                v = np.vstack([E[i]["v"] for i in sacr]); side = v[(sg * (v[:, 0] - xm) > 0) & (np.abs(v[:, 0] - xm) < 70)]
                ytop = float(np.percentile(side[:, 1], 98)); hgt = 40.0
                win = (np.abs(side[:, 0] - xm) > 16) & (np.abs(side[:, 0] - xm) < 36) & (side[:, 1] > ytop - 0.5 * hgt) & (side[:, 1] < ytop - 0.1 * hgt)
                bone_id = sacr[0]; below = "S1"
            nid = f"lumbar_medial_branch_l{n}_{s}" if n < 5 else f"l5_dorsal_ramus_medial_branch_{s}"
            if win.sum() < 5:
                B.hold(nid, f"no vertebral vertices in the junction window of {below}"); continue
            Jv = side[win][np.argmin(side[win][:, 2])]                      # most posterior vertex of the window = mammillary process / transverse-process root, dorsal surface
            J = Jv + np.array([0, 0, -1.2])
            S0 = J + np.array([sg * 6.0, 3.5, 9.0])                         # bifurcation of the dorsal ramus 3.5 mm above the root of the transverse process (L1-L4), in front of it
            E1 = J + np.array([-sg * 9.0, -10.0, -5.0])                     # to the multifidus along the lamina / facet joint below
            B.mk(nid, (f"Medial branch of the L{n} dorsal ramus ({sw})" if n < 5 else f"Medial branch of the L5 dorsal ramus ({sw})"), f"Ramus medialis rami dorsalis nervi spinalis L{n} {lat}", s, [S0, J, E1], 1.0, region="back",
                 course=(f"the dorsal ramus of L{n} leaves the L{n}-L{n + 1 if n < 5 else 'S1'} intervertebral foramen and divides about 3.5 mm above the superior border of the transverse-process root; its medial branch runs backward and caudally across the junction of the "
                         f"superior articular process and the transverse-process root of {below} (in the fibro-osseous canal under the mammilloaccessory ligament) and supplies multifidus and the facet joints above and below. "
                         f"Waypoints: bifurcation point (6 mm lateral / 3.5 mm above / 9 mm in front of the junction), junction = most posterior vertex of the window 16-32 mm lateral to the midline in the upper part of {below} ({bone_id}), "
                         "end 9 mm medial / 10 mm caudal / 5 mm behind the junction"),
                 calibre="no published diameter of the medial branch found; 1.0 mm = ASSUMPTION (the facet-joint radiofrequency literature treats it as a fine branch)", calibre_kind="assumption", lit_keys=["mb15"], err_lit_mm=3.5,
                 err_text="bifurcation 3.5 +- 1.2 mm above the transverse-process root (1.9 +- 0.9 at L5), Shuang 2015, 12 cadavers; vertebral landmarks are page meshes", len_range=(12, 60), min_skin=3.0, extra_rep=dict(junction_vertex_on=bone_id))


def pfcn(B, A, P, s, sw, sg, m, S2p):
    E = P.E; pt = A.pts[s]; E0 = pt["E0"]; xm = P.F["x_mid"]; lat = "sinister" if s == "l" else "dexter"
    if "sciatic_n" not in E or S2p is None:
        return B.hold(f"posterior_femoral_cutaneous_n_{s}", "no sciatic nerve on the page to follow")
    e = E["sciatic_n"]; v, f = e["v"], e["f"]
    ok = (sg * (v[f[:, 0], 0] - xm) > 0) & (sg * (v[f[:, 1], 0] - xm) > 0) & (sg * (v[f[:, 2], 0] - xm) > 0)
    C = LMK.centerline(v, f[ok], 40) if ok.sum() > 50 else None
    if C is None:
        return B.hold(f"posterior_femoral_cutaneous_n_{s}", "sciatic centre line not found")
    if C[0][1] < C[-1][1]:
        C = C[::-1]
    from scipy.spatial import cKDTree
    vs = v[np.unique(f[ok])]
    Rs = float(np.median(cKDTree(C).query(vs)[0]))
    off = np.array([0, 0, -(Rs + 1.25 + 2.0)])
    pick = [C[i] + off for i in np.linspace(0, len(C) - 1, 8).astype(int)]
    B.mk(f"posterior_femoral_cutaneous_n_{s}", f"Posterior femoral cutaneous nerve ({sw})", f"Nervus cutaneus femoris posterior {lat}", s,
         [pt_at(S2p, 0.90), E0 + np.array([0, -4.0, -8.0]), *pick], 2.5, region="thigh",
         course=("from the dorsal divisions of S1-S2 and the ventral divisions of S2-S3, leaves the pelvis through the greater sciatic foramen below piriformis behind the sciatic nerve, runs under gluteus maximus and descends in the middle of the "
                 "back of the thigh superficial (behind) to the sciatic nerve and the long head of biceps femoris, deep to the fascia lata, to the popliteal fossa (gives the inferior cluneal and the perineal branches; these are not drawn). "
                 f"Waypoints: S2 ramus at 90 %, greater sciatic foramen point, then the page's own sciatic nerve centre line (8 points, the page nerve is traced only below about y = {C[0][1]:.0f} mm) shifted {Rs + 3.25:.1f} mm backward"),
         calibre="trunk diameter not found (perforating branches 1.34 +- 0.35 mm, Clin Breast Cancer 2024; 'a few millimetres', Skeletal Radiol 2023); 2.5 mm = ASSUMPTION", calibre_kind="assumption", lit_keys=["pfcn24", "mrn23", "ssl16"], err_lit_mm=8.0,
         err_text="the page's sciatic nerve is itself only partly traced (rule-assisted detector); the PFCN follows it", len_range=(120, 520), min_skin=4.0)


def abdominal_nerves(B, A, P, Z):
    """iliohypogastric, ilioinguinal and genitofemoral nerves for the Imaging-based pages; the Z pages carry iliohypogastric_n and genitofemoral_n (skipped, reported) but no ilioinguinal nerve (built)."""
    E = P.E; soft = B.soft; xm = P.F["x_mid"]; lum = P.lumbar()
    for s in "lr":
        sg = SG[s]; sw = "left" if s == "l" else "right"; lat = "sinister" if s == "l" else "dexter"; m = np.array([-sg, 0, 0.0])
        ps = A.find(f"iliopsoas_{s}", f"psoas_major_{s}", f"zan_psoas_major_{s}"); ql = A.find(f"quadratus_lumborum_{s}")
        ASIS, PT = P.lm[f"ASIS_{s}"], P.lm[f"pubic_crest_{s}"]
        if ps is None or ql is None or lum is None:
            for nid in ("iliohypogastric_n", "ilioinguinal_n", "genitofemoral_n"):
                B.hold(f"{nid}_{s}", "no psoas / quadratus lumborum / lumbar vertebrae on the page")
            continue
        yL2 = float(E[lum[1]]["v"][:, 1].mean()); yL3 = float(E[lum[2]]["v"][:, 1].mean())
        pv = E[ps]["v"]; mk_ = (np.abs(pv[:, 1] - yL2) < 8) & (sg * (pv[:, 0] - xm) > 0)
        if mk_.sum() < 5:
            for nid in ("iliohypogastric_n", "ilioinguinal_n", "genitofemoral_n"):
                B.hold(f"{nid}_{s}", "psoas not found at the L2 level")
            continue
        Wa = pv[mk_][np.argmax(sg * pv[mk_][:, 0])] + np.array([sg * 2.0, 0, 0])
        Wb, _ = soft.surface_point(ql, Wa + np.array([sg * 14.0, -35.0, -12.0]), margin=2.0, direction=vec(np.array([0, 0, 1.0])), thr=0.3)
        Wc = ASIS + np.array([sg * 4.0, 35.0, -35.0])
        Wd = ASIS + np.array([-sg * 18.0, 4.0, 3.0])
        have = {n: (f"{n}_{s}" in E) for n in ("iliohypogastric_n", "genitofemoral_n", "ilioinguinal_n")}
        for n in ("iliohypogastric_n", "genitofemoral_n"):
            if Z and have[n]:
                B.skip(f"{n}_{s}", f"the Z page already carries {n}_l/r")
        for nid, nm, la, d, cal, calk, endv, lk, courseT in (
            ("iliohypogastric_n", "Iliohypogastric nerve", "Nervus iliohypogastricus", 2.2, "ultrasound median diameter 2.9 x 1.6 mm (Eichenberger 2006) = area-equivalent round 2.2 mm (cadaver values of 0.9-1.8 mm exist for the neighbouring ilioinguinal / genitofemoral nerves)", "cited",
             PT + np.array([0, 30.0, 4.0]), ["iliohyp06", "dnp21"], "ends as the anterior cutaneous branch above the superficial inguinal ring"),
            ("ilioinguinal_n", "Ilioinguinal nerve", "Nervus ilioinguinalis", 2.2, "ultrasound median diameter 3.0 x 1.6 mm (Eichenberger 2006) = area-equivalent round 2.2 mm; Orr Shauly 2021 measured 0.9 mm in 3 cadavers", "cited",
             PT + np.array([sg * 6.0, 10.0, 4.0]), ["iliohyp06", "dnp21"], "runs through the inguinal canal in front of the spermatic cord / round ligament and leaves by the superficial inguinal ring")):
            if Z and nid != "ilioinguinal_n":
                continue
            B.mk(f"{nid}_{s}", f"{nm} ({sw})", f"{la} {lat}", s, [Wa, Wb, Wc, Wd, 0.5 * (Wd + endv) + np.array([0, 0, 3.0]), endv], d, region="abdomen",
                 course=("from L1 (T12 for the iliohypogastric), emerges from the lateral border of psoas, crosses the anterior surface of quadratus lumborum below the kidney, pierces transversus abdominis near the iliac crest and runs between transversus abdominis and internal oblique "
                         f"(about 5 cm cranial and posterior to the anterior superior iliac spine) to the region 2 cm medial to the spine; {courseT}. Waypoints: lateral border of psoas at the L2 level, anterior surface of quadratus lumborum, "
                         "35 mm above / 35 mm behind the anterior superior iliac spine, 18 mm medial to it, then to the end point (above the pubic tubercle: iliohypogastric 30 mm, ilioinguinal 10 mm up / 6 mm lateral, kept 4+ mm under the skin)"),
                 calibre=cal, calibre_kind=calk, lit_keys=lk, err_lit_mm=10.0, err_text="no quantitative course data beyond the ultrasound landmark (5 cm cranial / posterior to the ASIS); layers of the abdominal wall are not segmented individually on this page",
                 len_range=(150, 420), skin_pull=4.0, min_skin=3.0)
        Wg = pv[(np.abs(pv[:, 1] - yL3) < 8) & (sg * (pv[:, 0] - xm) > 0)]
        if len(Wg) and not Z:
            Wg0, _ = soft.surface_point(ps, Wg[np.argmin(sg * Wg[:, 0])] + np.array([0, 0, 6.0]), margin=1.5, direction=vec(np.array([0, 0, 1.0])), thr=0.3)
            DIR = 0.5 * (ASIS + PT) + np.array([sg * 0.0, 12.0, 0.0])
            B.mk(f"genitofemoral_n_{s}", f"Genitofemoral nerve ({sw})", f"Nervus genitofemoralis {lat}", s, [Wg0, 0.5 * (Wg0 + DIR) + np.array([0, 0, 4.0]), DIR, 0.5 * (DIR + PT) + np.array([sg * 4.0, 0, 3.0]), PT + np.array([sg * 4.0, -8.0, 4.0])], 1.9, region="abdomen",
                 course=("from L1-L2, pierces psoas and descends on its anterior surface (behind the peritoneum, lateral to the ureter) to the deep inguinal ring, where it divides: the genital branch runs through the inguinal canal with the spermatic cord / round ligament "
                         "to the scrotum / labium majus (drawn); the femoral branch passes behind the inguinal ligament (not drawn). Waypoints: anterior surface of psoas at L3, deep inguinal ring (midpoint of ASIS - pubic tubercle, 12 mm above the inguinal ligament), pubic tubercle region"),
                 calibre="genitofemoral nerve 1.8 mm (Orr Shauly 2021) and 2.0 mm (JPRAS 2023): 1.9 mm", calibre_kind="cited", lit_keys=["dnp21", "pn23"], err_lit_mm=10.0, err_text="no quantitative course data; deep ring position from the ASIS - pubic tubercle midpoint",
                 len_range=(120, 400), skin_pull=4.0, min_skin=3.0)


def recurrent_branches(B, A, P):
    """recurrent (thenar) motor branch of the median nerve: leaves the median nerve at the distal border of the flexor retinaculum and runs radially / proximally into the thenar muscles (abductor pollicis brevis, opponens, flexor pollicis brevis)."""
    E = P.E; soft = B.soft
    for s in "lr":
        sw = "left" if s == "l" else "right"; lat = "sinister" if s == "l" else "dexter"; sg = SG[s]
        nid = f"recurrent_branch_of_median_n_{s}"
        med = A.find(f"median_n_lateral_root_{s}", f"median_n_{s}")
        thenar = [i for i in (f"abductor_pollicis_brevis_{s}", f"opponens_pollicis_{s}", f"flexor_pollicis_brevis_{s}") if i in E]
        if med is None or not thenar:
            B.hold(nid, "no median nerve / thenar muscle on the page"); continue
        C = LMK.centerline(E[med]["v"], E[med]["f"], 60)
        if C is None:
            B.hold(nid, "median nerve centre line not found"); continue
        if C[0][1] < C[-1][1]:
            C = C[::-1]
        M0 = C[-1]                                       # distal end of the page's median nerve (palm)
        # the thenar muscle surface point nearest to the median end, then 3 mm into the muscle
        best = None
        for i in thenar:
            kd, nn = soft.field(i)
            d, k = kd.query(M0)
            if best is None or d < best[0]:
                best = (d, kd.data[k] - nn[k] * 3.0, i)
        d, T, tid = best
        # origin along the page's median nerve so that the branch has the published length (20.7 mm): the branch leaves the nerve at the distal border of the retinaculum (extra-ligamentous) or inside the carpal tunnel (sub- / transligamentous)
        tail = C[-12:]
        dd = np.linalg.norm(tail - T, axis=1)
        j = int(np.argmin(np.abs(dd - 20.7)))
        if abs(dd[j] - 20.7) < 8.0:
            M0 = tail[j]
        if d > 40.0:
            B.hold(nid, f"nearest thenar muscle {d:.0f} mm from the end of the page's median nerve"); continue
        B.mk(nid, f"Recurrent (thenar) branch of the median nerve ({sw})", f"Ramus muscularis nervi mediani {lat}", s, [M0, 0.5 * (M0 + T) + np.array([0, 1.0, 1.0]), T], 1.0, region="hand",
             course=("leaves the median nerve at the distal border of the flexor retinaculum (extraligamentous 46 %, subligamentous 31 %, transligamentous 23 % in the classical series) and runs radially and proximally into the thenar muscles "
                     f"(abductor pollicis brevis, opponens pollicis, flexor pollicis brevis). Waypoints: distal end of the page's median nerve ({med}, centre line), midway, 3 mm inside the nearest thenar muscle ({tid}); "
                     "the retinaculum / Kaplan's cardinal line of the page is not used as a landmark (absent on the Imaging-based pages)"),
             calibre="recurrent branch of the median nerve: width 1.0 +- 0.3 mm, transferable length 20.7 +- 4.5 mm (Abou-Al-Shaar 2020, 16 hands)", calibre_kind="cited", lit_keys=["rmn20"], err_lit_mm=6.0,
             err_text="transferable length 20.7 +- 4.5 mm; three course variants; the median nerve and thenar muscles of the page are themselves Z-Anatomy fits", len_range=(5, 45), min_skin=1.5)
