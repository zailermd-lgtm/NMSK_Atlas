"""Q260: genuine LUMBAR and SACRAL plexus absences filled rule-based, same method family as Q249/Q258/Q259 (spline
through cited waypoints, pushed clear of bone, round tube, closed caps, badge with error bound) -- reusing
`data/nerves/lumbosacral_plexus.json`'s OWN existing ids (every one of them already cited there, parent-linked to
its real trunk: this round invents no new registry node for any item built here).

METHOD for a 'muscular branch' (the bulk of what's built here): the branch's ORIGIN is the point on the parent
nerve's own real shipped centreline (lm.py's generic geodesic centerline(), reused, not reimplemented) CLOSEST to
the target muscle -- a closest-approach heuristic, stated plainly as a MODELLING CHOICE (no publication found
giving a precise arborisation fraction along the trunk for each of these specific branches; the textbook course
description for each is otherwise followed: Gray's Anatomy for Students, 4th ed., ch.6; Moore, Dalley, Agur,
Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica -- the SAME source already cited on every one of these
registry nodes). The END point is the target muscle's own real surface, nearest the origin (nervelib.Soft's
surface_point, already used throughout Q249/Q258/Q259). A branch is HELD, not guessed, whenever its target muscle
has no mesh on the page, its parent nerve has no mesh (or no centreline) on the page, or the nearest point on the
parent nerve is farther from the target than a plausible muscular-branch length (gated, not assumed close).

Covers: (1) lumbar_root_T12..L4 (the lumbar plexus forming within psoas major -- Q247's own 'L1-L4 ventral rami /
plexus within psoas' row, absent on every page); (2) femoral_n's 7 muscular branches (iliacus, pectineus, sartorius,
rectus femoris, 3 vastii) -- Q247's 'femoral muscular branches' row, absent on every page, a tier-1 item; (3)
tibial_n's muscular branches (gastrocnemius, soleus, popliteus, tibialis posterior, +plantaris where the page ships
it) and its medial calcaneal cutaneous branches -- Q247's 'tibial muscular branches' (tier 1) and 'calcaneal
branches' (tier 1) rows; (4) sciatic_n's 5 hamstring muscular branches -- Q247's 'nerve to hamstrings / sciatic
muscular branches' row (tier 1).

NOT attempted here (queued, see docs/OPEN_ITEMS_FOR_OWNER.md): accessory obturator n. (an INCONSTANT nerve, present
in only a minority of people per Gray's -- modelling it as present on every page would overstate certainty, and it
has no existing registry citation to build against; adding one would need a fresh literature check this round did
not have time for); the obturator nerve's anterior/posterior division + muscular-branch separation and the
genitofemoral nerve's genital-branch separation (both currently shipped only as a single merged Z mesh under their
trunk's own id) -- investigated this round (the Z `obturator_n` mesh is actually 7 disconnected mesh components and
`genitofemoral_n` is 3, confirmed by `trimesh.Trimesh.split()`, so SOME separation is geometrically possible) but
NOT shipped: confidently assigning each disconnected piece to the correct named branch needs more individual
verification than this round had time for, and mislabelling real geometry with the wrong anatomical identity would
be worse than leaving it merged; lateral sural cutaneous n. and perforating cutaneous n. (S2-S3) -- lower tier,
out of time this round."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q259"))
import rulelig as RL              # noqa: E402
import guards as GD               # noqa: E402
import nervelib as NL             # noqa: E402
import lm as LMK                  # noqa: E402
from rulenerve import Builder as RBuilder  # noqa: E402
import lmk                        # noqa: E402

SG = {"l": -1.0, "r": 1.0}
SOURCE = "Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.6; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed. -- lumbar and sacral plexus sections; Terminologia Anatomica (FICAT 1998)."
ERR_BRANCH = 25.0
ERR_BRANCH_TEXT = ("landmark-rule allowance for a muscular branch's origin along its parent trunk: no publication found giving this branch's own precise arborisation fraction, so the origin is this nerve's own real "
                   "centreline point closest to the target muscle (a closest-approach heuristic, a MODELLING CHOICE, not a measured origin) -- the target end itself is the muscle's own real shipped surface.")
CAL_BRANCH = "no published diameter found for this individual muscular branch; 1.0 mm = ASSUMPTION (a small named muscular branch, this atlas' own convention for comparable branches, e.g. Q249's nerve_to_piriformis 3.0 mm trunk / fine twigs 1.0 mm)"


class _S:
    pass


def _mk_spine(E, ctx, key):
    Sx = _S(); Sx.E = E; Sx.ctx = ctx; Sx.key = key; Sx.xm = ctx.F["x_mid"]
    return Sx


def centerline(E, mid, n=40):
    if mid not in E:
        return None
    return LMK.centerline(E[mid]["v"], E[mid]["f"], n)


def find(E, *cands):
    for c in cands:
        if c in E:
            return c
    return None


def side_centerline(E, xm, base, s, n=40):
    """the parent trunk's centreline for side s, coping with this atlas' own inconsistent own-page nerve naming --
    checked directly this round, not assumed: some own-page trunks are suffixed ('femoral_n_l' + bare 'femoral_n'
    for the OTHER side), some have only a bare id for one side with no mirror at all (own_m 'tibial_n' = his own
    LEFT, 'tibial_n_r' = a mirror; own_f 'femoral_n' = her own RIGHT, 'femoral_n_l' = a mirror -- the bare id is
    NOT a fixed side across pages), and 'sciatic_n' is ONE bare mesh covering BOTH sides in one object (Q247's own
    note). Resolution: never trust the suffix alone -- classify every candidate id (bare and suffixed) by its OWN
    vertices' mean x position relative to the page's own midline, and if the only candidate spans both sides
    (sciatic_n), filter ITS OWN faces to side s first (the exact method rule_nerves.py's own pfcn() already uses for
    this same sciatic_n mesh) before taking a centreline, rather than ever guessing from the name."""
    sg = SG[s]
    for cand in (f"{base}_{s}", base, f"{base}_{'r' if s == 'l' else 'l'}"):
        if cand not in E:
            continue
        v, f = E[cand]["v"], E[cand]["f"]
        xr = v[:, 0] - xm
        frac_this_side = float((sg * xr > 0).mean())
        if frac_this_side > 0.95:
            return LMK.centerline(v, f, n)
        if 0.15 < frac_this_side < 0.85:
            ok = (sg * (xr[f[:, 0]]) > 0) & (sg * (xr[f[:, 1]]) > 0) & (sg * (xr[f[:, 2]]) > 0)
            if ok.sum() > 50:
                return LMK.centerline(v, f[ok], n)
        # otherwise this candidate is predominantly the OTHER side (a mirror / asymmetric id): keep looking
    return None


def muscular_branch(B, soft, E, nid, name, latin, side, sw, lat, nerve_id, target_cands, region, d=1.0, max_dist=130.0,
                     extra_course="", skin=False, xm=None):
    C = side_centerline(E, xm, nerve_id, side) if xm is not None else centerline(E, nerve_id)
    if C is None:
        B.hold(nid, name, f"no {nerve_id} centreline on this page (mesh absent or degenerate)", side=side)
        return
    tgt_id = find(E, *target_cands)
    if tgt_id is None:
        B.hold(nid, name, f"no {target_cands[0]} on this page", side=side)
        return
    if skin:
        # the generic point nearest the nerve's OWN distal end (own pages' one closed skin envelope has no named
        # regional patches, so the distal end of the nerve's own real segment is the best available query point)
        q = C[-1] if C[0][1] > C[-1][1] else C[0]
        pt, _ = soft.surface_point(tgt_id, q, margin=0.5, maxdist=max_dist)
        j = int(np.argmin(np.linalg.norm(C - q, axis=1)))
        origin = C[j]
    else:
        cen = E[tgt_id]["v"].mean(0)
        # own pages: some trunks are only PARTIAL real segments (e.g. the tibial nerve is tracked only near the
        # ankle, not through the popliteal fossa where its gastrocnemius/soleus/popliteus branches really arise --
        # checked directly this round). A Euclidean closest-approach alone can still find a geometrically 'valid'
        # (non-bone-crossing, plausible-length) path from a WRONG part of the trunk to the muscle, which would be
        # an anatomically misleading branch origin even though every other check passes. Guard: hold instead when
        # the target muscle's own height is well outside the tracked segment's own height range (the segment
        # genuinely does not reach the region this branch arises in), rather than trusting distance alone.
        y_lo, y_hi = C[:, 1].min() - 35.0, C[:, 1].max() + 35.0
        if not (y_lo <= cen[1] <= y_hi):
            B.hold(nid, name, f"this page's own {nerve_id} segment (y {C[:,1].min():.0f}..{C[:,1].max():.0f} mm) does not reach the height of {tgt_id} (y {cen[1]:.0f} mm): the real branch-origin region is not covered by this page's tracked segment", side=side)
            return
        d_c = np.linalg.norm(C - cen, axis=1)
        j = int(np.argmin(d_c))
        origin = C[j]
        pt, _ = soft.surface_point(tgt_id, origin, margin=0.3, maxdist=max_dist)
    if pt is None:
        B.hold(nid, name, f"{tgt_id} is farther than {max_dist:g} mm from the nearest point of {nerve_id}'s own centreline on this page", side=side)
        return
    if np.linalg.norm(origin - pt) < 2.0:
        B.hold(nid, name, f"the nerve's own centreline and the {tgt_id} surface are within 2 mm of each other on this page (no real length for a separate branch)", side=side)
        return
    mid_pt = 0.5 * (origin + pt)
    B.mk(nid, name, latin, side, [origin, mid_pt, pt], d, region=region,
         course=(f"{'cutaneous' if skin else 'muscular'} branch of {nerve_id}: leaves the trunk at the point of its own shipped centreline "
                 f"{'nearest its own distal end' if skin else 'closest to ' + tgt_id}, runs {np.linalg.norm(origin - pt):.0f} mm to the real surface of {tgt_id}. {extra_course}"),
         calibre=CAL_BRANCH, calibre_kind="assumption", source=SOURCE, err_mm=ERR_BRANCH, err_text=ERR_BRANCH_TEXT,
         len_range=(3, max_dist + 20), min_skin=None, softpush=((tgt_id, 0.3),))


FEMORAL_TARGETS = [
    ("femoral_n_branch_to_iliacus", "Femoral nerve branch to iliacus", "Ramus muscularis nervi femoralis ad musculum iliacum", ["iliopsoas_{s}", "zan_iliacus_muscle_{s}"]),
    ("femoral_n_branch_to_pectineus", "Femoral nerve branch to pectineus", "Ramus muscularis nervi femoralis ad musculum pectineum", ["pectineus_{s}", "zan_pectineus_{s}"]),
    ("femoral_n_branch_to_sartorius", "Femoral nerve branch to sartorius", "Ramus muscularis nervi femoralis ad musculum sartorium", ["sartorius_{s}"]),
    ("femoral_n_branch_to_rectus_femoris", "Femoral nerve branch to rectus femoris", "Ramus muscularis nervi femoralis ad musculum rectum femoris", ["rectus_femoris_{s}"]),
    ("femoral_n_branch_to_vastus_lateralis", "Femoral nerve branch to vastus lateralis", "Ramus muscularis nervi femoralis ad musculum vastum lateralem", ["vastus_lateralis_{s}"]),
    ("femoral_n_branch_to_vastus_medialis", "Femoral nerve branch to vastus medialis", "Ramus muscularis nervi femoralis ad musculum vastum medialem", ["vastus_medialis_{s}"]),
    ("femoral_n_branch_to_vastus_intermedius", "Femoral nerve branch to vastus intermedius", "Ramus muscularis nervi femoralis ad musculum vastum intermedium", ["vastus_intermedius_{s}"]),
]
TIBIAL_TARGETS = [
    ("tibial_n_branch_to_gastrocnemius", "Tibial nerve branch to gastrocnemius", "Ramus muscularis nervi tibialis ad musculum gastrocnemium", ["gastrocnemius_{s}"]),
    ("tibial_n_branch_to_soleus", "Tibial nerve branch to soleus", "Ramus muscularis nervi tibialis ad musculum soleum", ["soleus_{s}"]),
    ("tibial_n_branch_to_popliteus", "Tibial nerve branch to popliteus", "Ramus muscularis nervi tibialis ad musculum popliteum", ["popliteus_{s}"]),
    ("tibial_n_branch_to_tibialis_posterior", "Tibial nerve branch to tibialis posterior", "Ramus muscularis nervi tibialis ad musculum tibialem posteriorem", ["tibialis_posterior_{s}"]),
    ("tibial_n_branch_to_plantaris", "Tibial nerve branch to plantaris", "Ramus muscularis nervi tibialis ad musculum plantarem", ["plantaris_{s}"]),
]
HAMSTRING_TARGETS = [
    ("sciatic_n_branch_to_semitendinosus", "Sciatic nerve branch to semitendinosus", "Ramus muscularis nervi ischiadici ad musculum semitendinosum", ["semitendinosus_{s}"]),
    ("sciatic_n_branch_to_semimembranosus", "Sciatic nerve branch to semimembranosus", "Ramus muscularis nervi ischiadici ad musculum semimembranosum", ["semimembranosus_{s}"]),
    ("sciatic_n_branch_to_biceps_femoris_long_head", "Sciatic nerve branch to biceps femoris (long head)", "Ramus muscularis nervi ischiadici ad caput longum musculi bicipitis femoris", ["biceps_femoris_long_head_{s}"]),
    ("sciatic_n_branch_to_biceps_femoris_short_head", "Sciatic nerve branch to biceps femoris (short head)", "Ramus muscularis nervi ischiadici ad caput breve musculi bicipitis femoris", ["biceps_femoris_short_head_{s}"]),
    ("sciatic_n_branch_to_adductor_magnus_hamstring_part", "Sciatic nerve branch to adductor magnus (hamstring part)", "Ramus muscularis nervi ischiadici ad partem ischiocondylarem musculi adductoris magni", ["adductor_magnus_{s}"]),
]


def build(key, root="build/q259"):
    ctx = RL.Ctx(key, root=root)
    E = ctx.E
    gd = GD.Guards(E)
    soft = NL.Soft(E, gd)
    Sx = _mk_spine(E, ctx, key)
    B = RBuilder(Sx)
    S = lmk.Spine(key, root=root)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"

        # ---- lumbar roots T12..L4 (ventral rami) WITHIN psoas major -- Q247 'L1-L4 ventral rami / plexus within
        # psoas' row. Each root exits at the vertebra's own lateral extent (lmk.lateral_point, reused) and ends at
        # the nearest real surface point of psoas major (iliopsoas on own pages) -- a short segment, matching the
        # textbook ('the lumbar plexus is formed WITHIN the substance of psoas major', Gray's ch.6).
        psoas_id = find(E, f"iliopsoas_{s}", f"psoas_major_{s}", f"zan_psoas_major_{s}")
        for lvl, nid_lvl in (("t12", "lumbar_root_T12"), ("l1", "lumbar_root_L1"), ("l2", "lumbar_root_L2"), ("l3", "lumbar_root_L3"), ("l4", "lumbar_root_L4")):
            nid = f"{nid_lvl}_{s}"
            name = f"{nid_lvl.replace('_', ' ')} ventral ramus (lumbar plexus root, {sw})"
            if psoas_id is None:
                B.hold(nid, name, "no psoas major / iliopsoas on this page", side=s); continue
            W = S.lateral(lvl, s, frac_pctl=96.0) if lvl.startswith("l") else S.lateral("t12", s, frac_pctl=96.0)
            if W is None:
                B.hold(nid, name, f"vertebra for {lvl} not found on this page", side=s); continue
            pt, _ = soft.surface_point(psoas_id, W, margin=0.3, maxdist=90.0)
            if pt is None:
                B.hold(nid, name, f"{psoas_id} farther than 90 mm from the {lvl} exit point on this page", side=s); continue
            if np.linalg.norm(W - pt) < 3.0:
                B.hold(nid, name, f"the {lvl} vertebral exit point and the nearest {psoas_id} surface are within 3 mm of each other on this page (no real length for a separate root segment)", side=s); continue
            mid_pt = 0.5 * (W + pt)
            B.mk(nid, name, f"Ramus ventralis nervi spinalis {nid_lvl.upper()} {lat}", s, [W, mid_pt, pt], 2.0, region="abdomen",
                     course=(f"ventral ramus of the {nid_lvl.upper()} spinal nerve, exits at the vertebra's own lateral extent (this page's own {S.vid(lvl if lvl.startswith('l') else 't12')}) and runs into the "
                             f"substance of psoas major ({psoas_id}), where it joins the lumbar plexus -- 'the lumbar plexus is formed within psoas major' (Gray's Anatomy for Students ch.6)."),
                     calibre="no published isolated root diameter found; 2.0 mm = ASSUMPTION (a spinal ventral ramus near its vertebral exit, between the dorsal-ramus medial branch 1.0 mm and a named plexus trunk)",
                     calibre_kind="assumption", source=SOURCE, err_mm=15.0, err_text="landmark-rule allowance (vertebral lateral-extent sampling, q259/lmk.py's own method, +-9 mm there, widened here for the psoas entry point which is not independently measured)",
                     len_range=(5, 110), softpush=((psoas_id, 0.3),))

        # ---- femoral nerve muscular branches
        for nid_base, name, latin, cands in FEMORAL_TARGETS:
            nid = f"{nid_base}_{s}"
            targets = [c.format(s=s) for c in cands]
            muscular_branch(B, soft, E, nid, f"{name} ({sw})", latin, s, sw, lat, "femoral_n", targets, "thigh", d=1.0, max_dist=140.0, xm=Sx.xm,
                             extra_course="Femoral nerve muscular branches arise in the femoral triangle and upper thigh (Gray's ch.6).")

        # ---- tibial nerve muscular branches + medial calcaneal cutaneous
        for nid_base, name, latin, cands in TIBIAL_TARGETS:
            nid = f"{nid_base}_{s}"
            targets = [c.format(s=s) for c in cands]
            muscular_branch(B, soft, E, nid, f"{name} ({sw})", latin, s, sw, lat, "tibial_n", targets, "leg", d=1.0, max_dist=160.0, xm=Sx.xm,
                             extra_course="Tibial nerve muscular branches arise in the popliteal fossa and proximal calf (Gray's ch.6).")
        heel_targets = [f"zan_skin_heel_region_{s}", "skin"]
        muscular_branch(B, soft, E, f"tibial_n_medial_calcaneal_branches_{s}", f"Tibial nerve medial calcaneal branches ({sw})",
                         f"Rami calcanei mediales nervi tibialis {lat}", s, sw, lat, "tibial_n", heel_targets, "ankle", d=1.0, max_dist=180.0, skin=True, xm=Sx.xm,
                         extra_course="Medial calcaneal branches leave the tibial nerve proximal to the tarsal tunnel and supply the skin of the heel (Gray's ch.6).")

        # ---- sciatic nerve hamstring muscular branches
        for nid_base, name, latin, cands in HAMSTRING_TARGETS:
            nid = f"{nid_base}_{s}"
            targets = [c.format(s=s) for c in cands]
            muscular_branch(B, soft, E, nid, f"{name} ({sw})", latin, s, sw, lat, "sciatic_n", targets, "thigh", d=1.0, max_dist=150.0, xm=Sx.xm,
                             extra_course="Sciatic nerve branches to the hamstrings arise from its tibial division in the posterior thigh (Gray's ch.6).")
    return B.out, {}
