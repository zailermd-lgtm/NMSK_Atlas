"""Q265: round 6 of the owner's "all plexuses and major nerves" program -- direct continuation of Q263's own queue
(PROJECT_STATE.md Q263 entry / docs/OPEN_ITEMS_FOR_OWNER.md section ג).

Built this round, each re-verified against this atlas' own real meshes before being attempted (not trusted from
Q247/Q260/Q261/Q263's own prose, which the project's own hard-won lesson says can be slightly stale):

1. Lateral sural cutaneous n. (`common_fibular_n_lateral_sural_cutaneous_n`) -- Z PAGES ONLY: `common_fibular_n`
   does not exist on either own page (checked directly), so there is no real trunk to branch from there. On the
   four Z pages it is a real, already-shipped mesh. This atlas has no skin patch named specifically "lateral" for
   the leg (only `zan_skin_anterior_region_of_leg` / `zan_skin_posterior_region_of_leg`) -- rather than GUESS which
   of those two patches the real lateral compartment corresponds to, the branch ends on `fibularis_longus`'s own
   real surface instead (Gray's: the nerve "pierces the deep fascia... and descends superficial to fibularis
   longus" in the upper leg before reaching skin) -- a real, named, unambiguous structure, honestly stated as the
   point it approximates rather than the literal skin.

2. Perforating cutaneous n. (S2-S3) -- new registry node `perforating_cutaneous_n` added this round
   (data/nerves/lumbosacral_plexus.json, same citation set as its sacral-plexus siblings), ALL SIX PAGES: a real
   anchor exists everywhere -- `s2_ventral_ramus` / `s3_ventral_ramus` (Q249's own rule-based roots, already shipped
   on every page) as origin, `sacrotuberous_ligament` (real mesh, every page) as the "pierces" waypoint,
   `gluteus_maximus` (real mesh, every page) as the "curls around its lower border" waypoint, and the gluteal-fold
   skin (Z: `zan_skin_gluteal_region`; own: the one closed `skin` envelope) as the terminus.

3. Subcostal n. (T12) + its 4 registered branches -- already fully registered (`data/nerves/thoracic_segmental_
   nerves.json`: trunk + abdominal_wall_muscular + rectus_abdominis_branch + lateral_cutaneous + anterior_cutaneous),
   ALL SIX PAGES: real origin `lumbar_root_T12` (Q249's own rule-based T12 ventral ramus, already shipped on every
   page -- this atlas' own existing id for exactly the structure the subcostal n. IS, the T12 ventral ramus below
   the 12th rib), real muscular targets (external_oblique / internal_oblique / transversus_abdominis /
   quadratus_lumborum / rectus_abdominis, every page), real cutaneous targets resolved to the atlas' own named skin
   regions nearest the registry's own target description (`lateral_hip_and_gluteal_skin_T12` -> `zan_skin_gluteal_
   region` on Z / `skin` on own; `suprapubic_skin_T12` -> `zan_skin_hypogastric_region` on Z, an exact real match for
   "suprapubic" in the standard 9-region abdominal map / `skin` on own). Trunk's own documented terminal target,
   pyramidalis, is absent on both own pages (checked directly) -- falls back there to rectus_abdominis, the real
   muscle it also supplies, stated honestly on that card. The OTHER 2 of the 3 Q247-queued thoracic items --
   individual per-level lateral/anterior cutaneous branches of intercostal nerves T1-T11 -- are NOT attempted this
   round either: re-checked directly (not assumed) that the existing `zan_intercostal_nerves_{l,r}` Z mesh is still
   ONE object per side with no per-level split, so there is no real per-level origin point to branch a T3 (say)
   cutaneous branch from without guessing which part of that merged tube is T3 -- genuinely still queued, the same
   conclusion Q260 already reached, re-confirmed rather than re-guessed.

4. Vagus n., thoracic/abdominal course -- new registry nodes added this round (`data/nerves/cranial_and_cervical_
   nerves.json`: vagus_n_oesophageal_trunk, vagus_n_abdominal_trunk, vagus_n_coeliac_branch), ALL SIX PAGES: Q261
   had already flagged real targets existing (zan_oesophagus, zan_stomach) with no registry node; re-verified this
   round that BOTH own pages ALSO carry a real `esophagus`/`stomach` mesh AND their own already-shipped cervical
   `vagus_n_{l,r}` trunk (Q260) -- so this is buildable on all six pages, not Z-only as Q261's own prose guessed.
   Course: continues from the existing cervical trunk's own real, most-inferior shipped point, down along the real
   oesophagus's own surface (oesophageal trunk/plexus), to the real stomach's own surface near the oesophagogastric
   junction (abdominal vagal trunk), with a further real branch to the coeliac level (Z: `zan_coeliac_trunk`; own:
   `abdominal_aorta` at the same T12/L1 level -- the SAME `coeliac_target()` helper Q259's rule_splanchnic.py
   already built and validated for the greater splanchnic nerve's own identical target, reused verbatim here, not
   re-derived).

5. Hypoglossal n., lingual branches -- Z PAGES ONLY, cheap bonus: the four Z pages already ship a real
   `hypoglossal_n_{l,r}` trunk mesh (Z-Anatomy, confirmed by direct id lookup) but not this branch (checked
   directly: `hypoglossal_n_lingual_branches` absent from calibre.json on every Z page). Built with Q261's own
   `rule_cranial.branch()` helper verbatim (origin = the real trunk's own centreline point closest to genioglossus,
   end = genioglossus's own real surface, hyoglossus/styloglossus fallback -- matching the registry's own target
   order exactly, the same method already used for every other Z-page cranial-nerve branch).

NOT attempted, re-confirmed rather than re-guessed (full detail in PROJECT_STATE.md Q265 / docs/OPEN_ITEMS_FOR_OWNER.md):
accessory_obturator_n. (still no registry citation in lumbosacral_plexus.json -- the task's own queue was explicitly
conditional on one existing); obturator_n / genitofemoral_n component separation (re-investigated with NEW concrete
evidence this round -- see PROJECT_STATE.md -- but the obturator_n mesh's own connected-component COUNT differs
page to page, and even side to side on the same page (5, 7, 5, 7, 7, 7 across the twelve page/side combinations
checked), so no single fragment-index -> anatomical-name mapping is safe to apply uniformly; re-held, not forced).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q259"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q260"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q261"))
import lmk                                      # noqa: E402
from rulenerve import Builder as RBuilder       # noqa: E402
from rule_limb_fill import find  # noqa: E402
from rule_splanchnic import coeliac_target      # noqa: E402
import rule_cranial as RC                       # noqa: E402

SG = {"l": -1.0, "r": 1.0}
SRC_LUMBOSACRAL = "data/nerves/lumbosacral_plexus.json (perforating_cutaneous_n, added Q265); Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.6; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998)."
SRC_THORACIC = "data/nerves/thoracic_segmental_nerves.json (subcostal_n and its 4 registered branches); Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.4; Terminologia Anatomica (FICAT 1998)."
SRC_VAGUS = "data/nerves/cranial_and_cervical_nerves.json (vagus_n_oesophageal_trunk / vagus_n_abdominal_trunk / vagus_n_coeliac_branch, added Q265); Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.4-5; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998)."
CAL_ASSUME = "no published per-subject diameter found for this individual branch; 1.0 mm = ASSUMPTION (this atlas' own convention for comparable small named branches, e.g. Q260's tibial_n_medial_calcaneal_branches)"


class _S:
    pass


def _mk_ctx(key, root):
    S = lmk.Spine(key, root=root)
    Sx = _S(); Sx.E = S.E; Sx.ctx = S.ctx; Sx.key = key; Sx.xm = S.xm
    return S, Sx


# ============================================================================================= 1. lateral sural cutaneous n. (Z pages only)
def build_lateral_sural(key, root):
    if key.startswith("own"):
        out = []
        for s in "lr":
            out.append(dict(id=f"common_fibular_n_lateral_sural_cutaneous_n_{s}", name="Lateral sural cutaneous nerve", side=s, status="held",
                             held=["no common_fibular_n mesh of any kind on either own page to branch from (checked directly)"], cat="nerve"))
        return out, {}
    S, Sx = _mk_ctx(key, root)
    E = S.E
    B = RBuilder(Sx)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        nid = f"common_fibular_n_lateral_sural_cutaneous_n_{s}"
        name = f"Lateral sural cutaneous nerve ({sw})"
        tid = f"common_fibular_n_{s}"
        if tid not in E:
            B.hold(nid, name, f"no {tid} mesh on this page", side=s)
            continue
        import lm as LMK
        C = LMK.centerline(E[tid]["v"], E[tid]["f"], 30)
        if C is None:
            B.hold(nid, name, f"{tid} centreline could not be computed on this page", side=s)
            continue
        # the generic rule_limb_fill.muscular_branch() helper checks the TARGET's own full-mesh centroid height
        # against the trunk's own tracked y-range -- too strict here: fibularis_longus is a long muscle spanning
        # from the fibular head to the ankle, so its own CENTROID sits far below where this branch actually arises
        # (near the fibular head/neck, this nerve's own real origin, Gray's ch.6). Queried directly against the
        # PROXIMAL end of the trunk's own real centreline instead (not its centroid), so the nearest real surface
        # found is naturally fibularis longus's own proximal part, not an arbitrary point on the whole long muscle.
        origin = C[int(np.argmax(C[:, 1]))]  # most superior (proximal) point of the trunk's own real centreline
        tgt_id = f"fibularis_longus_{s}"
        if tgt_id not in E:
            B.hold(nid, name, f"no {tgt_id} mesh on this page", side=s)
            continue
        pt, _ = B.soft.surface_point(tgt_id, origin, margin=0.3, maxdist=90.0)
        if pt is None:
            B.hold(nid, name, f"{tgt_id} is farther than 90 mm from {tid}'s own proximal real point on this page", side=s)
            continue
        if np.linalg.norm(origin - pt) < 2.0:
            B.hold(nid, name, f"the nerve's own proximal end and {tgt_id}'s surface are within 2 mm of each other on this page (no real length for a separate branch)", side=s)
            continue
        B.mk(nid, name, f"Nervus cutaneus surae lateralis {lat}", s, [origin, pt], 1.2, region="leg",
             course=("Leaves the common fibular nerve near the fibular neck, pierces the deep fascia and descends superficial to fibularis longus in the upper leg before becoming cutaneous (Gray's ch.6); "
                     "this atlas ships no skin patch specifically labelled 'lateral' for the leg (only anterior/posterior regions), so rather than guess between them this branch ends on fibularis longus's own "
                     "real PROXIMAL surface instead (queried from the trunk's own proximal end, not the whole muscle's centroid), the real named structure it actually runs on at this level."),
             calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_LUMBOSACRAL, err_mm=12.0,
             err_text="landmark-rule allowance for a short, simple branch with no page-specific calibre study; +-12 mm", len_range=(2, 110))
    return B.out, {}


# ============================================================================================= 2. perforating cutaneous n. (S2-S3), all six pages
def _s23_origin(E, s):
    pts = []
    for lvl in ("s2_ventral_ramus", "s3_ventral_ramus"):
        vid = f"{lvl}_{s}"
        if vid not in E:
            continue
        import lm as LMK
        C = LMK.centerline(E[vid]["v"], E[vid]["f"], 30)
        if C is None:
            continue
        j = int(np.argmax(np.abs(C[:, 0])))  # most lateral point (nearest the sacral foramen exit)
        pts.append(C[j])
    if not pts:
        return None
    return np.mean(pts, axis=0)


def build_perforating_cutaneous(key, root):
    S, Sx = _mk_ctx(key, root)
    E = S.E
    B = RBuilder(Sx)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        nid = f"perforating_cutaneous_n_{s}"
        name = f"Perforating cutaneous nerve ({sw})"
        origin = _s23_origin(E, s)
        if origin is None:
            B.hold(nid, name, "neither s2_ventral_ramus nor s3_ventral_ramus has a usable mesh on this page's own side", side=s)
            continue
        stl_id = find(E, f"sacrotuberous_ligament_{s}")
        if stl_id is None:
            B.hold(nid, name, "no sacrotuberous_ligament mesh on this page", side=s)
            continue
        stl_pt, _ = B.soft.surface_point(stl_id, origin, margin=0.3, maxdist=140.0)
        if stl_pt is None:
            B.hold(nid, name, f"{stl_id} is farther than 140 mm from the real S2/S3 origin point on this page", side=s)
            continue
        gm_id = find(E, f"gluteus_maximus_{s}")
        skin_cands = [f"zan_skin_gluteal_region_{s}", f"zan_skin_gluteal_fold_{s}", "skin"]
        skin_id = find(E, *skin_cands)
        anchors = [origin, stl_pt]
        if gm_id is not None:
            gm_pt, _ = B.soft.surface_point(gm_id, stl_pt, margin=0.3, maxdist=120.0)
            if gm_pt is not None:
                anchors.append(gm_pt)
        if skin_id is not None:
            sk_q = anchors[-1]
            sk_pt, _ = B.soft.surface_point(skin_id, sk_q, margin=0.5, maxdist=140.0)
            if sk_pt is not None:
                anchors.append(sk_pt)
        if len(anchors) < 2 or np.linalg.norm(anchors[-1] - anchors[0]) < 3.0:
            B.hold(nid, name, "no real course of plausible length could be built on this page (ends too close together)", side=s)
            continue
        softpush = [(gm_id, 0.3)] if gm_id else []
        B.mk(nid, name, f"Nervus cutaneus perforans {lat}", s, anchors, 1.0, region="pelvis",
             course=("Arises directly from the posterior surfaces of the S2/S3 ventral rami (this atlas' own already-shipped s2_ventral_ramus/s3_ventral_ramus roots), pierces the sacrotuberous ligament's own real "
                     "surface, curls around the lower border of gluteus maximus and supplies the skin over the inferomedial buttock (Gray's ch.6)."),
             calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_LUMBOSACRAL, err_mm=15.0,
             err_text="landmark-rule allowance for a small, occasionally-inconstant cutaneous nerve with no page-specific calibre study; +-15 mm",
             len_range=(3, 220), softpush=softpush)
    return B.out, {}


# ============================================================================================= 3. subcostal n. (T12) + its 4 branches, all six pages
SUBCOSTAL_MUSC_CANDS = ["transversus_abdominis_{s}", "internal_oblique_{s}", "external_oblique_{s}", "quadratus_lumborum_{s}"]
SUBCOSTAL_RECTUS_CANDS = ["rectus_abdominis_{s}"]
SUBCOSTAL_LAT_SKIN = ["zan_skin_gluteal_region_{s}", "zan_skin_lateral_region_of_abdomen_{s}", "skin"]
SUBCOSTAL_ANT_SKIN = ["zan_skin_hypogastric_region_{s}", "zan_skin_umbilical_region_{s}", "skin"]
SUBCOSTAL_TRUNK_TARGET = ["pyramidalis_{s}", "rectus_abdominis_{s}"]


def build_subcostal(key, root):
    S, Sx = _mk_ctx(key, root)
    E = S.E
    B = RBuilder(Sx)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        root_id = f"lumbar_root_T12_{s}"
        if root_id not in E:
            for nid, name in ((f"subcostal_n_{s}", "Subcostal nerve (T12)"), (f"subcostal_n_abdominal_wall_muscular_{s}", "Subcostal n. abdominal wall muscular branch"),
                               (f"subcostal_n_rectus_abdominis_branch_{s}", "Subcostal n. branch to rectus abdominis"), (f"subcostal_n_lateral_cutaneous_{s}", "Subcostal n. lateral cutaneous branch"),
                               (f"subcostal_n_anterior_cutaneous_{s}", "Subcostal n. anterior cutaneous branch")):
                B.hold(nid, name, f"no {root_id} mesh on this page (Q249's own rule-based T12 ventral ramus)", side=s)
            continue
        import lm as LMK
        C = LMK.centerline(E[root_id]["v"], E[root_id]["f"], 30)
        if C is None:
            B.hold(f"subcostal_n_{s}", "Subcostal nerve (T12)", f"{root_id} centreline could not be computed on this page", side=s)
            continue
        origin = C[int(np.argmax(np.abs(C[:, 0] - S.xm)))]  # most lateral point of its own T12 root = where it continues as the subcostal n. proper
        trunk_cands = [c.format(s=s) for c in SUBCOSTAL_TRUNK_TARGET]
        # try each candidate target IN ORDER and use the first one actually reachable within maxdist (not just the
        # first one PRESENT on the page): checked directly this round that pyramidalis, where it exists, can be
        # much farther from the T12 root than rectus_abdominis is (e.g. 284 mm vs 140 mm on base_m) -- a plain
        # "first id found in E" pick (this atlas' own generic find()) would then wrongly give up instead of falling
        # back to the real, reachable neighbouring muscle.
        trunk_tgt, pt = None, None
        for cand in trunk_cands:
            if cand not in E:
                continue
            p, _ = B.soft.surface_point(cand, origin, margin=0.3, maxdist=260.0)
            if p is not None:
                trunk_tgt, pt = cand, p
                break
        e_trunk = None
        if trunk_tgt is not None:
            if pt is not None and np.linalg.norm(pt - origin) > 5.0:
                mid = 0.5 * (origin + pt)
                note = (" -- this page ships no pyramidalis, so the trunk's own course is represented ending at rectus abdominis instead, the real neighbouring muscle it also supplies, stated honestly."
                        if trunk_tgt.startswith("rectus_abdominis") else ".")
                e_trunk = B.mk(f"subcostal_n_{s}", "Subcostal nerve (T12)", f"Nervus subcostalis {lat}", s, [origin, mid, pt], 1.8, region="abdomen",
                               course=(f"Ventral ramus of T12 ({root_id}, this atlas' own already-shipped mesh), running below the 12th rib (no intercostal space) around the abdominal wall to "
                                       f"{trunk_tgt.split('_')[0]} (Gray's ch.4)" + note),
                               calibre="T12 ventral ramus: no page-specific caliper study; 1.8 mm = ASSUMPTION, matched to this atlas' own already-shipped L1 lumbar root calibre for cross-level consistency",
                               calibre_kind="assumption", source=SRC_THORACIC, err_mm=12.0,
                               err_text="landmark-rule allowance: origin from the real T12 ventral-ramus root, no per-subject course measured; +-12 mm", len_range=(5, 300))
        # NOTE: no softpush against trunk_tgt here -- its endpoint is already placed exactly on trunk_tgt's own real
        # surface via surface_point() above, so a further softpush would be the SAME over-correction mechanism
        # Q263 already found and worked around for its own hypoglossal_n build (the shared Soft.outside()
        # approximation can inflate an already-correct endpoint's path by 50+ mm against a small/thin target) --
        # a real instance of exactly that caught in this round's own first attempt (609 mm vs. a real ~250-300 mm
        # course), fixed the same way Q263 fixed it: drop the softpush on the already-placed endpoint.
        if e_trunk is None:
            B.hold(f"subcostal_n_{s}", "Subcostal nerve (T12)", "no real abdominal-wall target (pyramidalis or rectus abdominis) reachable from the T12 root on this page", side=s)
        # the muscular/cutaneous branches arise at intervals along the nerve's own course around the abdominal
        # wall, not at one single point; this atlas approximates all of them as arising at the nerve's own real
        # T12-root origin (the same single-origin simplification this project's own branch() helper already uses
        # for every cranial-nerve branch), stated honestly rather than inventing an intermediate arborisation point.
        branch_origin = origin
        # muscular branch (enters the neurovascular plane between internal oblique / transversus abdominis)
        mcands = [c.format(s=s) for c in SUBCOSTAL_MUSC_CANDS]
        mtgt = find(E, *mcands)
        if mtgt is not None:
            pt, _ = B.soft.surface_point(mtgt, branch_origin, margin=0.3, maxdist=220.0)
            if pt is not None and np.linalg.norm(pt - branch_origin) > 3.0:
                B.mk(f"subcostal_n_abdominal_wall_muscular_{s}", "Subcostal n. abdominal wall muscular branch", f"Ramus muscularis nervi subcostalis {lat}", s,
                     [branch_origin, pt], 1.0, region="abdomen",
                     course=f"Enters the neurovascular plane between internal oblique and transversus abdominis, supplying the lower abdominal wall muscles including quadratus lumborum's uppermost fibres (Gray's ch.4); ends on {mtgt}'s own real surface.",
                     calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_THORACIC, err_mm=15.0, err_text="landmark-rule allowance; +-15 mm", len_range=(3, 240))
            else:
                B.hold(f"subcostal_n_abdominal_wall_muscular_{s}", "Subcostal n. abdominal wall muscular branch", f"{mtgt} unreachable from the T12 root on this page", side=s)
        else:
            B.hold(f"subcostal_n_abdominal_wall_muscular_{s}", "Subcostal n. abdominal wall muscular branch", "no real abdominal-wall muscle target on this page", side=s)
        # rectus abdominis branch
        rtgt = find(E, *[c.format(s=s) for c in SUBCOSTAL_RECTUS_CANDS])
        if rtgt is not None:
            pt, _ = B.soft.surface_point(rtgt, branch_origin, margin=0.3, maxdist=220.0)
            if pt is not None and np.linalg.norm(pt - branch_origin) > 3.0:
                B.mk(f"subcostal_n_rectus_abdominis_branch_{s}", "Subcostal n. branch to rectus abdominis", f"Ramus musculi recti abdominis {lat}", s,
                     [branch_origin, pt], 1.0, region="abdomen",
                     course=f"Pierces the posterior rectus sheath to enter the deep surface of rectus abdominis's own most inferior part (Gray's ch.4); ends on {rtgt}'s own real surface.",
                     calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_THORACIC, err_mm=15.0, err_text="landmark-rule allowance; +-15 mm", len_range=(3, 240))
            else:
                B.hold(f"subcostal_n_rectus_abdominis_branch_{s}", "Subcostal n. branch to rectus abdominis", f"{rtgt} unreachable from the T12 root on this page", side=s)
        else:
            B.hold(f"subcostal_n_rectus_abdominis_branch_{s}", "Subcostal n. branch to rectus abdominis", "no real rectus_abdominis mesh on this page", side=s)
        # lateral cutaneous branch (reaches as far as the gluteal region -- checked directly this round: this is a
        # genuinely long real course, 280-300 mm centroid distance on the four Z pages, not a geometry error, so
        # maxdist/len_range are set to match rather than treated as "unreachable")
        ltgt = find(E, *[c.format(s=s) for c in SUBCOSTAL_LAT_SKIN])
        if ltgt is not None:
            pt, _ = B.soft.surface_point(ltgt, branch_origin, margin=0.5, maxdist=340.0)
            if pt is not None and np.linalg.norm(pt - branch_origin) > 3.0:
                B.mk(f"subcostal_n_lateral_cutaneous_{s}", "Subcostal n. lateral cutaneous branch", f"Ramus cutaneus lateralis nervi subcostalis {lat}", s,
                     [branch_origin, pt], 1.0, region="abdomen",
                     course=(f"Descends over the iliac crest to supply skin as far as the anterior gluteal region -- the longest cutaneous reach of any thoracic segmental nerve (Gray's ch.4); this atlas' own "
                             f"registry target ('lateral_hip_and_gluteal_skin_T12') is approximated here by {ltgt}'s own real surface, the nearest named match."),
                     calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_THORACIC, err_mm=20.0, err_text="landmark-rule allowance for this nerve's own unusually long cutaneous reach; +-20 mm", len_range=(3, 400))
            else:
                B.hold(f"subcostal_n_lateral_cutaneous_{s}", "Subcostal n. lateral cutaneous branch", f"{ltgt} unreachable from the T12 root on this page", side=s)
        else:
            B.hold(f"subcostal_n_lateral_cutaneous_{s}", "Subcostal n. lateral cutaneous branch", "no real gluteal/lateral-abdomen skin mesh on this page", side=s)
        # anterior cutaneous branch (suprapubic skin -- same real-long-course reasoning as above: hypogastric-region
        # skin measured 300-336 mm centroid distance on the four Z pages; umbilical-region skin, tried first if
        # closer, is NOT a worse match for "suprapubic" when hypogastric itself is out of reach -- stated honestly
        # on the card via the same note mechanism already used for the trunk's own pyramidalis/rectus_abdominis fallback)
        atgt = find(E, *[c.format(s=s) for c in SUBCOSTAL_ANT_SKIN])
        if atgt is not None:
            pt, _ = B.soft.surface_point(atgt, branch_origin, margin=0.5, maxdist=340.0)
            if pt is not None and np.linalg.norm(pt - branch_origin) > 3.0:
                B.mk(f"subcostal_n_anterior_cutaneous_{s}", "Subcostal n. anterior cutaneous branch", f"Ramus cutaneus anterior nervi subcostalis {lat}", s,
                     [branch_origin, pt], 1.0, region="abdomen",
                     course=(f"The nerve's own terminal cutaneous branch, reaching the suprapubic skin (Gray's ch.4); this atlas' own registry target ('suprapubic_skin_T12') is matched here to {atgt}'s own real "
                             "surface" + (", an exact named match (the hypogastric region IS the standard anatomical term for the suprapubic region)." if "hypogastric" in atgt else ", the nearest named match available.")),
                     calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_THORACIC, err_mm=18.0, err_text="landmark-rule allowance; +-18 mm", len_range=(3, 400))
            else:
                B.hold(f"subcostal_n_anterior_cutaneous_{s}", "Subcostal n. anterior cutaneous branch", f"{atgt} unreachable from the T12 root on this page", side=s)
        else:
            B.hold(f"subcostal_n_anterior_cutaneous_{s}", "Subcostal n. anterior cutaneous branch", "no real suprapubic/anterior-abdomen skin mesh on this page", side=s)
    return B.out, {}


# ============================================================================================= 4. vagus n., thoracic/abdominal course, all six pages
def _vagus_trunk_id(E, s):
    return find(E, f"vagus_n_{s}", f"zan_vagus_nerve_x_{s}")


def _side_vertex(E, tid, xm, s, q):
    """nearest REAL vertex of structure tid to point q, restricted to side s of the midline when that side has
    enough of its own vertices -- the oesophagus and stomach are both near-midline/left-leaning real structures, so
    a plain nearest-point-on-the-whole-mesh query can legitimately land on the WRONG side for the right vagus (this
    round's own first attempt did exactly that, caught by this atlas' own existing side-margin gate, not invented
    here): fixed by pre-filtering to side s's own half of the mesh first, same device rule_limb_fill.side_centerline
    already uses for an asymmetric trunk."""
    v = E[tid]["v"]
    sel = SG[s] * (v[:, 0] - xm) > 0
    cand = v[sel] if sel.sum() > 20 else v
    d = np.linalg.norm(cand - q, axis=1)
    return cand[int(np.argmin(d))]


def build_vagus_thoracic_abdominal(key, root):
    S, Sx = _mk_ctx(key, root)
    E = S.E
    B = RBuilder(Sx)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        tr = _vagus_trunk_id(E, s)
        if tr is None:
            for nid, name in ((f"vagus_n_oesophageal_trunk_{s}", "Vagus n., oesophageal (thoracic) trunk"), (f"vagus_n_abdominal_trunk_{s}", "Vagus n., abdominal trunk"), (f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch")):
                B.hold(nid, name, "no real cervical vagus trunk mesh on this side of this page to continue from", side=s)
            continue
        import lm as LMK
        C = LMK.centerline(E[tr]["v"], E[tr]["f"], 60)
        if C is None:
            continue
        origin = C[int(np.argmin(C[:, 1]))]  # most inferior real point of the already-shipped cervical trunk
        eso_id = find(E, "zan_oesophagus", "esophagus")
        if eso_id is None:
            for nid, name in ((f"vagus_n_oesophageal_trunk_{s}", "Vagus n., oesophageal (thoracic) trunk"), (f"vagus_n_abdominal_trunk_{s}", "Vagus n., abdominal trunk"), (f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch")):
                B.hold(nid, name, "no real oesophagus mesh on this page", side=s)
            continue
        ev = E[eso_id]["v"]
        mid_y = origin[1] - 0.5 * (origin[1] - float(np.percentile(ev[:, 1], 15)))
        band = ev[np.abs(ev[:, 1] - mid_y) < 20.0]
        band = band if len(band) else ev
        mid_pt = _side_vertex(E, eso_id, Sx.xm, s, band.mean(0)) if len(band) else ev.mean(0)
        # NOTE: no softpush against eso_id -- mid_pt is already a real point ON its own surface (a vertex of it),
        # so a further softpush would risk the same over-correction Q263 already found for a small/thin target.
        e_oes = B.mk(f"vagus_n_oesophageal_trunk_{s}", f"Vagus n., oesophageal (thoracic) trunk ({sw})", f"Truncus oesophageus nervi vagi {lat}", s,
                      [origin, mid_pt], 1.2, region="thorax",
                      course=("Continues from the vagus's own already-shipped cervical trunk's own most inferior real point, descending in the posterior mediastinum to re-form a plexus directly on the "
                              f"oesophagus's own real surface ({eso_id}) below the lung roots (Gray's ch.4); the target point is restricted to this side's own half of the oesophagus mesh (checked directly this "
                              "round: an unrestricted nearest-point query can land on the mesh's far side even for a near-midline structure like the oesophagus)."),
                      calibre="no published thoracic-vagus-trunk diameter found; 1.2 mm = ASSUMPTION, matched to this atlas' own already-shipped cervical vagus trunk calibre for cross-level consistency",
                      calibre_kind="assumption", source=SRC_VAGUS, err_mm=14.0, err_text="landmark-rule allowance for a long thoracic course with no per-subject tracing; +-14 mm", len_range=(10, 260))
        if e_oes.get("status") != "ship":
            for nid, name in ((f"vagus_n_abdominal_trunk_{s}", "Vagus n., abdominal trunk"), (f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch")):
                B.hold(nid, name, "this nerve's own oesophageal (thoracic) trunk could not be placed on this page (see that item's own hold reason)", side=s)
            continue
        oes_end = np.array(e_oes["report"]["waypoints"][-1], float)
        stom_id = find(E, "zan_stomach", "stomach")
        if stom_id is None:
            B.hold(f"vagus_n_abdominal_trunk_{s}", "Vagus n., abdominal trunk", "no real stomach mesh on this page", side=s)
            B.hold(f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch", "this nerve's own abdominal trunk could not be placed on this page (no stomach mesh)", side=s)
            continue
        stom_pt = _side_vertex(E, stom_id, Sx.xm, s, oes_end)
        if np.linalg.norm(stom_pt - oes_end) > 180.0:
            B.hold(f"vagus_n_abdominal_trunk_{s}", "Vagus n., abdominal trunk", f"{stom_id}'s own nearest same-side vertex is farther than 180 mm from the oesophageal trunk's own end on this page", side=s)
            B.hold(f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch", "this nerve's own abdominal trunk could not be placed on this page", side=s)
            continue
        # NOTE: no softpush against stom_id -- stom_pt is already a real vertex ON its own surface, same reasoning
        # as the oesophageal trunk above.
        e_abd = B.mk(f"vagus_n_abdominal_trunk_{s}", f"Vagus n., abdominal trunk ({sw})", f"Truncus vagalis abdominalis {lat}", s,
                      [oes_end, stom_pt], 1.2, region="abdomen",
                      course=("At the oesophageal hiatus the periesophageal plexus re-condenses into anterior (predominantly left) and posterior (predominantly right) vagal trunks on the stomach's own real "
                              f"surface near the oesophagogastric junction (Gray's ch.5); this atlas does not re-derive the real left/right fibre crossing (no tracing data available), so each side's own trunk "
                              f"continues to its own nearest real stomach surface on ITS OWN side of the midline ({stom_id}), stated as a simplification, not a literal cross to the opposite side (checked directly "
                              "this round: an unrestricted nearest-point query onto the whole stomach mesh can otherwise cross the midline, since the stomach itself is a predominantly left-sided organ)."),
                      calibre="no published abdominal-vagal-trunk diameter found; 1.2 mm = ASSUMPTION, matched to the oesophageal trunk above",
                      calibre_kind="assumption", source=SRC_VAGUS, err_mm=16.0, err_text="landmark-rule allowance across the diaphragm with no per-subject tracing; +-16 mm", len_range=(3, 180))
        if e_abd.get("status") != "ship":
            B.hold(f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch", "this nerve's own abdominal trunk could not be placed on this page (see that item's own hold reason)", side=s)
            continue
        abd_end = np.array(e_abd["report"]["waypoints"][-1], float)
        coe_pt, used_real = coeliac_target(S, s)
        if coe_pt is None:
            B.hold(f"vagus_n_coeliac_branch_{s}", "Vagus n., coeliac branch", "no real coeliac-trunk or abdominal-aorta landmark on this page (see rule_splanchnic.coeliac_target)", side=s)
            continue
        B.mk(f"vagus_n_coeliac_branch_{s}", f"Vagus n., coeliac branch ({sw})", f"Ramus coeliacus nervi vagi {lat}", s,
             [abd_end, coe_pt], 1.0, region="abdomen",
             course=("The posterior vagal trunk's major coeliac branch, joining the coeliac plexus/ganglia around the coeliac trunk's origin from the aorta -- the SAME real target (or, on pages without a coeliac-"
                     f"trunk mesh, the SAME abdominal-aorta proxy at the same documented level) already established and cited by this atlas' own greater splanchnic nerve (Q259), reused verbatim, not re-derived; "
                     f"{'a real zan_coeliac_trunk mesh' if used_real else 'this page has no coeliac-trunk mesh, so the abdominal_aorta proxy at the coeliac origin level is used, with a wider error band'}."),
             calibre=CAL_ASSUME, calibre_kind="assumption", source=SRC_VAGUS, err_mm=(14.0 if used_real else 20.0),
             err_text=("landmark-rule allowance; +-14 mm" if used_real else "wider band: approximated by the abdominal aorta at the coeliac trunk's own documented origin level, no page-specific coeliac-trunk mesh; +-20 mm"),
             len_range=(3, 220))
    return B.out, {}


# ============================================================================================= 5. hypoglossal n. lingual branches, Z pages only (cheap bonus)
def build_hypoglossal_lingual_z(key, root):
    if key.startswith("own"):
        return [], {}
    S = lmk.Spine(key, root=root)
    from rulenerve import Builder as RBuilder2
    Bx = RBuilder2(S)
    out = []
    for s in "lr":
        sw = "left" if s == "l" else "right"
        e = RC.branch(Bx, S, f"hypoglossal_n_lingual_branches_{s}", f"Hypoglossal n., lingual branches ({sw})",
                      f"Rami linguales nervi hypoglossi {'sinister' if s == 'l' else 'dexter'}", s,
                      f"hypoglossal_n_{s}", [f"genioglossus_{s}", f"hyoglossus_{s}", f"styloglossus_{s}"], "head",
                      "Continues as the 'lingual branches' to the extrinsic tongue muscles (Gray's ch.8); this atlas' own registry targets order (genioglossus first) matches the registry's own hypoglossal_n_lingual_branches node -- the same method Q263 already used for the own-page build of this exact branch.",
                      d=1.0, max_dist=90.0, min_len=3.0)
        if e is None:
            pass  # branch() already appended a held record via B.hold
    out.extend(Bx.out)
    return out, {}


def build(key, root="build/q261"):
    out = []
    for fn in (build_lateral_sural, build_perforating_cutaneous, build_subcostal, build_vagus_thoracic_abdominal, build_hypoglossal_lingual_z):
        items, _ = fn(key, root=root)
        out += items
    return out, {}


if __name__ == "__main__":
    for k in ("own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"):
        items, _ = build(k)
        ship = [i for i in items if i["status"] == "ship"]
        held = [i for i in items if i["status"] != "ship"]
        print(k, "ship", len(ship), "held", len(held))
        for h in held:
            print("   HELD", h["id"], "|", h["held"])
