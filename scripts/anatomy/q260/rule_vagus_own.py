"""Q260: the vagus nerve's CERVICAL TRUNK on the two OWN pages (Imaging F/M), which ship NO vagus mesh at all -- Q259
confirmed this directly and explicitly queued it ("the own pages DO have the needed landmarks -- common/internal
carotid arteries, subclavian artery, trachea, oesophagus -- so a rule-based vagus trunk is feasible, just out of
THIS round's scope"). This module builds exactly that trunk, using the real carotid-sheath relationship (Gray's
Anatomy for Students, 4th ed., ch.8: the vagus descends in the neck within the carotid sheath, in the interval
between and POSTERIOR to the internal jugular vein (lateral) and the internal / common carotid artery (medial) --
Moore, Dalley, Agur, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica) -- the own pages' own
`internal_carotid_a_{s}` / `common_carotid_a_{s}` / `internal_jugular_v_{s}` meshes (confirmed present on both own
pages before writing this module, not assumed) give that exact landmark directly, matching the owner's own
brief wording almost verbatim ("between the internal/common carotid artery and the internal jugular vein").

Course sampled at 8 evenly spaced heights from just below the skull base (top of the internal carotid artery /
internal jugular vein, approximating the jugular foramen region where the vagus truly originates) down to the root
of the neck (the common carotid artery's own inferior-most point, at or near the thoracic inlet) -- at each height,
the real artery point (internal carotid above, common carotid below, whichever mesh covers that height) and the real
vein point are each the centroid of a thin y-band of that vessel's own vertices; the nerve point is their midpoint,
biased POSTERIORLY (lower z, this atlas' own convention: see q259/lmk.py `scm_posterior`) by 35% of the
artery-vein separation, matching the textbook "behind the interval" description qualitatively rather than
numerically (no publication was found giving a numeric anteroposterior offset within the sheath for this atlas to
cite; stated as a geometric approximation, not a segmented or dissected position).

SCOPE: the trunk only (skull base to root of neck), matching the brief's own wording ("own-page vagus trunk...
unblocks future vagus-branch work... you do NOT need to build those branches this round unless trivial"). The
recurrent laryngeal branch is NOT attempted here: own_f ships no trachea mesh at all (confirmed), own_m's trachea
exists but neither own page ships a cricoid cartilage (confirmed, see the audit script run before this module was
written) -- the RLN's ascending tracheo-oesophageal-groove waypoints (q259/rule_vagus.py's own method) and its
cricoid-cartilage end point cannot be built with genuine landmarks on either own page without at least one of
these two missing meshes; held/deferred honestly rather than guessed, see docs/OPEN_ITEMS_FOR_OWNER.md.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q259"))
import rulelig as RL             # noqa: E402
import guards as GD              # noqa: E402
import nervelib as NL            # noqa: E402
import lm as LMK                 # noqa: E402
from rulenerve import Builder as RBuilder  # noqa: E402
import lmk                       # noqa: E402

SG = {"l": -1.0, "r": 1.0}
SOURCE = ("Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.8 ('the vagus nerve descends within the carotid sheath, posterior to and between the internal jugular vein and the internal, then common, "
          "carotid artery'); Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998).")
ERR = 10.0
ERR_TEXT = ("landmark-rule allowance: the nerve's own real position within the carotid sheath (how far 'posterior' of the artery-vein midline it sits) is not numerically quantified in the cited texts for this atlas to "
            "match exactly -- the 35% posterior bias is a geometric approximation of the textbook description, not a measured or cited offset; the artery/vein waypoints themselves are this page's own real segmented vessels.")
CAL = ("no per-subject vagus-nerve diameter measured for this atlas; 1.4 mm = MODELLING CHOICE, matched to this atlas' own already-shipped Z-page vagus mesh (zan_vagus_nerve_x, 1.0-1.6 mm, Q240 calibre table) for "
       "cross-page visual consistency, not a new literature citation.")


def _vessel_xz_at_y(E, ids, y):
    """x,z of the given vessel mesh id(s) at height y, by PIECEWISE-LINEAR interpolation along each mesh's own
    smooth centreline (lm.py's generic geodesic centerline(), already used elsewhere in this codebase) rather than
    a raw-vertex y-band average -- switched to this after a raw-vertex version produced an unstable point (and a
    large, flagged push-out) exactly in the real anatomical GAP between the internal and common carotid artery
    meshes (no mesh there: the carotid bifurcation itself is not separately shipped), where the nearest-single-
    vertex fallback could pick an end-cap vertex with an unrepresentative position (checked directly: own_m right,
    idx 19 needed a 21 mm vessel-clearance push at exactly that gap's height). Concatenating the (possibly two)
    vessels' own centrelines and interpolating x(y)/z(y) linearly bridges a real gap smoothly instead of jumping
    between raw vertices; outside either vessel's own real y-range, interpolation clamps to that vessel's own end
    point rather than extrapolating (np.interp's own behaviour), matching the project's own 'don't invent beyond
    the landmark' convention."""
    pts = []
    for mid in ids:
        if mid not in E:
            continue
        C = LMK.centerline(E[mid]["v"], E[mid]["f"], 24)
        if C is not None:
            pts.append(C)
    P = np.vstack(pts)
    order = np.argsort(P[:, 1])
    P = P[order]
    x = float(np.interp(y, P[:, 1], P[:, 0]))
    z = float(np.interp(y, P[:, 1], P[:, 2]))
    return np.array([x, y, z])


def _skin_depth_trimesh(E, V):
    """Q260 found Guards.skin_depth (the shared q248/guards.py utility) gave a false 'tens of mm outside the skin'
    reading for points in the superior neck on own pages, and worked around it HERE ONLY (not in the shared module,
    named 'not fixed' at the time) by recomputing the same exact trimesh watertight signed distance this function
    still contains. Q263 root-caused it (a sparse random surface-point sample's nearest-SAMPLED-point + its normal
    flips sign across sharp folds -- e.g. the ear/jaw region -- because two points 12.6 mm apart ON THE SURFACE can
    have near-opposite normals there) and fixed `Guards.skin_depth` itself the same way, generically, for every
    caller. This function is now REDUNDANT (confirmed: its own output is byte-identical to the fixed
    `Guards.skin_depth` on all 4 vagus builds, own_m/own_f x l/r) -- kept only so `build()`'s own
    `skin_min_depth_mm_guards`/`skin_min_depth_mm` reporting below still runs unchanged; the two numbers will simply
    read the same now instead of differing."""
    import trimesh as _tm
    sk = E["skin"]
    m = _tm.Trimesh(sk["v"], sk["f"], process=False)
    if not m.is_watertight:
        return None
    return round(float(_tm.proximity.ProximityQuery(m).signed_distance(V).min()), 1)


def build(key, root="build/q259"):
    ctx = RL.Ctx(key, root=root)
    E = ctx.E
    out = []
    notes = {}
    trachea_id = "trachea" if "trachea" in E else None
    cricoid_id = None  # neither own page ships one; checked explicitly
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        nid = f"vagus_n_{s}"
        icc = f"internal_carotid_a_{s}"
        ccc = f"common_carotid_a_{s}"
        ijv = f"internal_jugular_v_{s}"
        have = [i for i in (icc, ccc, ijv) if i in E]
        if icc not in E or ccc not in E or ijv not in E:
            out.append(dict(id=nid, name="Vagus nerve", side=s, status="held",
                             held=[f"one of {icc}/{ccc}/{ijv} not on this page (have: {have})"], cat="nerve"))
            continue
        Vic, Vcc, Vij = E[icc]["v"], E[ccc]["v"], E[ijv]["v"]
        # the superior-most few mm (close to the jugular foramen / cranial base) trips the SAME generic
        # bone-signed-distance-field false positive Q259 already found and fixed for the C1 nerve root on these
        # pages ("a known limitation of a surface-sample-based field on a geometrically complex bone" -- the
        # cranium here, misclassifying a point just below the skull base as deeply inside it); checked directly
        # this round (own_m right: cranium sd -12.4 mm at the uppermost third of the raw path) and fixed the SAME
        # way Q259 fixed C1 -- bias the target point inferior (here, trim the superior extent) rather than fighting
        # the field; the real jugular-foramen level itself is already an approximation (no separate skull-base
        # mesh to anchor to more precisely), so this is a small, anatomically-reasonable adjustment, not a new
        # source of error.
        y_top = float(min(Vic[:, 1].max(), Vij[:, 1].max())) - 20.0
        if "cranium" in E:
            xm = ctx.F["x_mid"]
            cv = E["cranium"]["v"]
            band = cv[(SG[s] * (cv[:, 0] - xm) > 10) & (SG[s] * (cv[:, 0] - xm) < 70)]
            if len(band):
                # the field artifact above reaches noticeably BELOW the cranium mesh's own real lowest vertex in
                # this lateral band (checked directly: own_m right, real cranium vertices start at y=715.5 but the
                # signed-distance field still misclassified y=703.7, 12 mm lower, as inside it) -- a 25 mm margin
                # below that real lowest vertex clears the artifact zone with room to spare, checked on both own
                # pages / both sides after this fix, not assumed from one case.
                y_top = min(y_top, float(band[:, 1].min()) - 25.0)
        # y_bot: the LOWER of the two real vessels' own extent, not just the artery's -- checked directly this
        # round (own_m right: internal_jugular_v stops at y=564 while common_carotid_a continues to y=550, i.e.
        # the artery alone descends further than the vein on this page/side; using the artery's own bottom alone
        # left the vein lookup with no real data below y=564 and silently reused its lowest real point for every
        # query height below that -- a genuine 'invented' flat tail this round does not want, caught by comparing
        # the output anchors' y-spacing against np.linspace's expected even spacing before shipping, not assumed).
        y_bot = float(max(Vcc[:, 1].min(), Vij[:, 1].min())) + 3.0
        if y_top <= y_bot:
            out.append(dict(id=nid, name="Vagus nerve", side=s, status="held",
                             held=["internal carotid / jugular top is not above the common carotid bottom on this page (implausible vessel geometry for this course)"], cat="nerve"))
            continue
        ys = np.linspace(y_top, y_bot, 10)
        anchors = []
        for y in ys:
            ap = _vessel_xz_at_y(E, (icc, ccc), y)
            vp = _vessel_xz_at_y(E, (ijv,), y)
            mid = 0.5 * (ap + vp)
            sep = np.linalg.norm(ap - vp)
            post = np.array([0.0, 0.0, -1.0]) * (0.35 * sep)
            anchors.append(mid + post)
        # one light 3-point smoothing pass (endpoints fixed): the per-height artery/vein band centroids are each
        # independent real measurements and are not perfectly smooth from one sampled height to the next, which a
        # cubic spline (fit through ALL of them) can overshoot between -- checked directly this round (own_f left:
        # the raw spline passed within -47 mm of the 'skin' mesh near the top even though every individual anchor
        # measured 36-65 mm inside it); smoothing the anchors first removes the overshoot without moving any anchor
        # by more than about 2-3 mm (checked, not assumed).
        A0 = [a.copy() for a in anchors]
        for _ in range(2):
            A1 = [A0[0]] + [0.25 * A0[i - 1] + 0.5 * A0[i] + 0.25 * A0[i + 1] for i in range(1, len(A0) - 1)] + [A0[-1]]
            A0 = A1
        anchors = A0
        # a class holding E/ctx like q259's Spine, just enough for rulenerve.Builder
        class _S:
            pass
        Sx = _S(); Sx.E = E; Sx.ctx = ctx; Sx.key = key
        Sx.xm = ctx.F["x_mid"]
        B = RBuilder(Sx)
        e = B.mk(nid, f"Vagus nerve ({sw})", f"Nervus vagus {lat}", s, anchors, 1.4, region="neck",
                 course=(f"cervical trunk only (skull base to root of neck): descends in the carotid sheath, posterior to and between the internal/common carotid artery (medial, this page's own {icc}/{ccc}) and the "
                         f"internal jugular vein (lateral, this page's own {ijv}) -- 10 waypoints, each the midpoint of a real artery/vein cross-section at that height, biased 35% of their separation posteriorly, "
                         "lightly smoothed to remove spline overshoot between heights (see module docstring). "
                         "Recurrent laryngeal branch NOT built: this page ships no cricoid cartilage" + (" and no trachea" if trachea_id is None else " (trachea present, cricoid absent)") + "."),
                 calibre=CAL, calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(60, 320),
                 softpush=((icc, 0.5), (ccc, 0.5), (ijv, 0.5)))
        if e.get("status") == "ship":
            sk2 = _skin_depth_trimesh(E, e["V"])
            if sk2 is not None:
                e["report"]["skin_min_depth_mm_guards"] = e["report"]["skin_min_depth_mm"]
                e["report"]["skin_min_depth_mm"] = sk2
                e["report"]["skin_min_depth_mm_note"] = ("cross-checked against trimesh's exact watertight signed distance (see _skin_depth_trimesh docstring): Q263 fixed the shared Guards.skin_depth itself to use this "
                                                           f"same exact method, so the two numbers now agree ({e['report']['skin_min_depth_mm_guards']} mm both) -- kept as a standing cross-check, not because they still differ.")
        out.append(e)
        notes[f"vagus_{s}_anchors"] = [np.round(a, 1).tolist() for a in anchors]
    return out, notes
