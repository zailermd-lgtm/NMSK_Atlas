"""Q261: CRANIAL NERVES' OTHER 10 ABSENT ROWS (Q247's cranial-nerve audit table, data/derived/Q247_nerve_coverage.md
section 'Cranial'), re-verified directly this round rather than trusted from that now-stale (Q258/Q259/Q260-era)
table: V1/V2 sensory branches, V3's masticatory-motor branches + auriculotemporal n., VII's 5+2 terminal branches
+ greater petrosal n., IX's 5 named branches, X's superior-laryngeal/pharyngeal/cardiac branches (the recurrent
laryngeal branch itself was already built by Q259), and XI's distal course to trapezius.

Z PAGES ONLY (base_m/base_f/comb_m/comb_f) -- re-verified directly, not assumed: the own pages (Imaging F/M) ship
NO cranial-nerve trunk mesh of any kind except optic_n (CNS-transferred) and the vagus cervical trunk Q260 itself
just built; there is no facial_n / trigeminal_n / glossopharyngeal_n / accessory_n trunk there to branch FROM, so
building isolated branches on the own pages would be exactly the same "unanchored guess" problem Q259 avoided for
the own-page vagus RLN -- held entirely, queued for whichever future round builds the own-page cranial-nerve trunks
themselves (a bigger, separate project, like Q260's own-page vagus trunk was).

On the four Z pages, every one of the 10 absent rows' PARENT TRUNK already ships as a real Z-Anatomy mesh under its
OWN (non-registry) id -- zan_ophthalmic_nerve, zan_maxillary_nerve, zan_anterior_division_of_mandibular_nerve /
zan_posterior_division_of_mandibular_nerve, zan_facial_nerve_vii, glossopharyngeal_n, zan_vagus_nerve_x,
zan_accessory_nerve_xi -- confirmed present, bilateral, on all four Z pages before any code was written (see
scratch/q261_anchor_check.py-style probe this round ran interactively). No new trunk is built here (that would
duplicate real, already-shipped geometry): every item below is a BRANCH, reusing the SAME rule-based method as
Q258/Q259/Q260 (spline through cited waypoints, pushed clear of bone, round tube, closed caps, badge with error
bound) but with the origin taken from the REAL trunk mesh's own centreline (closest point to the real target) and
the end on the REAL target's own shipped surface -- the same "closest-approach to a real, already-shipped mesh"
method Q260's rule_limb_fill.muscular_branch() established for muscular branches, extended here to any named
branch (muscular, cutaneous, mucosal/dental, glandular) of a cranial nerve.

Registry targets (data/nerves/cranial_and_cervical_nerves.json's own `targets` field) are often FINER than this
atlas' real segmentation (e.g. 'masseter_r_superficial' / 'masseter_r_deep', this atlas only ships one undivided
masseter_r) -- `resolve_target()` below strips the registry's own fascicle/part suffixes to find the real parent
mesh that actually ships, stated per structure, never inventing a finer mesh that does not exist.

HELD, not attempted (genuinely no anchor anywhere in this atlas, checked directly): trigeminal_n_v3_tensor_tympani_branch
/ trigeminal_n_v3_tensor_veli_palatini_branch (their OWN registry targets already say '(middle ear muscle / soft
palate muscle, not yet modeled in this pass)' -- confirmed still true, no tensor_tympani or tensor_veli_palatini
mesh on any page); greater_petrosal_n, lesser_petrosal_n, otic_ganglion, pterygopalatine_ganglion, ciliary_ganglion,
submandibular_ganglion (autonomic ganglia are categorically NOT round nerve-tube structures -- representing a
ganglion as a nerve tube would misrepresent its anatomy, and none of these four has any mesh, even a placeholder,
on any page to anchor a tube-shaped approximation to in the first place); the vagus's thoracic/abdominal course
(oesophageal plexus, anterior/posterior vagal trunks, pulmonary plexus) -- real targets DO exist (zan_oesophagus,
zan_stomach, lung meshes) but no registry node exists for them yet (unlike the lumbar/sacral splanchnic nerves
Q259 added with a fresh citation) -- queued precisely rather than inventing new ids under this round's time budget.
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
import lmk                     # noqa: E402  (q259's generic Spine wrapper -- reused for its Ctx/centerline/find plumbing only; no vertebra method used here)
from rulenerve import Builder  # noqa: E402

ROOT_DEFAULT = "build/q260"
SG = {"l": -1.0, "r": 1.0}
SOURCE = "Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.8 'Head and Neck'; Terminologia Anatomica (FICAT 1998); data/nerves/cranial_and_cervical_nerves.json (this round's own targets field, resolved to this atlas' real meshes)."
ERR = 10.0
ERR_TEXT = "landmark-rule allowance for a cranial-nerve branch (no page-specific calibre or caliper study exists for these small branches): origin = the real parent-nerve mesh's own centreline point closest to the real target, end = the target's own real surface; +-10 mm"
CAL = "no published diameter found for this individual cranial-nerve branch; 1.0 mm = ASSUMPTION (comparable small named branch, this atlas' own convention for comparable Q258/Q259/Q260 branches)"

# registry target id -> the suffix families this atlas' real segmentation does not carry (stripped in order; first match wins)
SUFFIXES = ["_superficial", "_deep", "_anterior", "_posterior", "_upper", "_middle", "_lower",
            "_orbital", "_palpebral", "_transverse_part", "_alar_part", "_main", "_sternal", "_clavicular"]


def resolve_target(E, cand):
    """one registry target string -> a real mesh id on this page, or None. Strips this atlas' own finer-than-shipped
    fascicle/part suffixes (see module docstring) before giving up; never fabricates a mesh that is not in E."""
    if cand in E:
        return cand
    for suf in SUFFIXES:
        if cand.endswith(suf):
            base = cand[: -len(suf)]
            if base in E:
                return base
    return None


def find_target(E, *cands):
    for c in cands:
        r = resolve_target(E, c)
        if r:
            return r
    return None


def branch(B, S, nid, name, latin, side, trunk_id, target_cands, region, extra_course, *, origin_pt=None,
           d=1.0, max_dist=140.0, min_len=2.0, note_targets=""):
    """one cranial-nerve branch: origin = (given point, or) the point on the real TRUNK mesh's own centreline closest
    to the real TARGET's centroid; end = the target's own real surface. Held, not guessed, if the trunk or target
    mesh is absent, the nearest trunk point is implausibly far from the target, or the two ends are too close to
    hold a separate branch's worth of length."""
    E = S.E
    sw = "left" if side == "l" else "right"
    lat = "sinister" if side == "l" else "dexter"
    tr = S.find(trunk_id)
    if tr is None and origin_pt is None:
        B.hold(nid, name, f"no {trunk_id} mesh on this page to branch from", side=side)
        return None
    tgt_id = find_target(E, *target_cands)
    if tgt_id is None:
        B.hold(nid, name, f"no real mesh on this page resolves any of this branch's registry targets ({target_cands[0]} ...)", side=side)
        return None
    cen = E[tgt_id]["v"].mean(0)
    if origin_pt is not None:
        origin = np.asarray(origin_pt, float)
    else:
        C = S.centerline(tr, n=40)
        if C is None:
            B.hold(nid, name, f"{trunk_id} centreline could not be computed on this page", side=side)
            return None
        j = int(np.argmin(np.linalg.norm(C - cen, axis=1)))
        origin = C[j]
    pt, _ = B.soft.surface_point(tgt_id, origin, margin=0.35, maxdist=max_dist)
    if pt is None:
        B.hold(nid, name, f"{tgt_id} is farther than {max_dist:g} mm from {trunk_id}'s nearest centreline point on this page", side=side)
        return None
    if np.linalg.norm(origin - pt) < min_len:
        B.hold(nid, name, f"the branch point and the {tgt_id} surface are within {min_len:g} mm of each other on this page (no real length for a separate branch)", side=side)
        return None
    mid = 0.5 * (origin + pt)
    e = B.mk(nid, name, latin, side, [origin, mid, pt], d, region=region,
             course=(f"branch of {trunk_id if tr else 'its parent branch'}: leaves at the point of its own real centreline closest to {tgt_id}, runs "
                     f"{np.linalg.norm(origin - pt):.0f} mm to that structure's own real surface. {extra_course} {note_targets}"),
             calibre=CAL, calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT,
             len_range=(min_len, max_dist + 25), softpush=((tgt_id, 0.3),))
    return e


def build(key, root=ROOT_DEFAULT):
    out = []
    if key.startswith("own"):
        for nid, name in HELD_OWN:
            out.append(dict(id=nid, name=name, side=None, status="held",
                             held=["own pages ship no facial_n/trigeminal_n/glossopharyngeal_n/accessory_n trunk mesh of any kind to branch from -- see module docstring"], cat="nerve"))
        return out, {}
    S = lmk.Spine(key, root=root)
    B = Builder(S)
    E = S.E
    for s in "lr":
        sw = "left" if s == "l" else "right"
        # ================================================================= V1 (ophthalmic), trunk zan_ophthalmic_nerve
        trunk_v1 = f"zan_ophthalmic_nerve_{s}"
        e_lac = branch(B, S, f"trigeminal_n_v1_lacrimal_branch_{s}", f"Lacrimal nerve ({sw})", f"Nervus lacrimalis {('sinister' if s=='l' else 'dexter')}", s,
                        trunk_v1, [f"lacrimal_{s}"], "head",
                        "Runs along the superolateral orbital wall to the lacrimal gland (Gray's ch.8); also carries the lacrimal gland's secretomotor fibres received via a documented V2 detour (not separately modelled).")
        e_frontal = branch(B, S, f"trigeminal_n_v1_frontal_branch_{s}", f"Frontal nerve ({sw})", f"Nervus frontalis {('sinister' if s=='l' else 'dexter')}", s,
                            trunk_v1, [f"levator_palpebrae_superioris_{s}"], "head",
                            "Runs along the roof of the orbit, superior to levator palpebrae superioris (Gray's ch.8), before dividing into the supraorbital and supratrochlear nerves; represented here as reaching that muscle's own real surface, the shared point of division.")
        if e_frontal and e_frontal.get("status") == "ship":
            fend = e_frontal["report"]["waypoints"][-1]
            branch(B, S, f"trigeminal_n_v1_supraorbital_branch_{s}", f"Supraorbital nerve ({sw})", f"Nervus supraorbitalis {('sinister' if s=='l' else 'dexter')}", s,
                   None, [f"zan_skin_frontal_region_{s}"], "head",
                   "Continues from the frontal nerve's own division point through the supraorbital notch/foramen to the skin of the forehead and scalp (Gray's ch.8); this atlas ships one named frontal-region skin patch rather than a segmented notch, so the branch ends on that patch's own real surface, biased laterally (no separate supraorbital vessel to anchor to on this page, unlike supratrochlear below).",
                   origin_pt=fend, min_len=3.0)
            branch(B, S, f"trigeminal_n_v1_supratrochlear_branch_{s}", f"Supratrochlear nerve ({sw})", f"Nervus supratrochlearis {('sinister' if s=='l' else 'dexter')}", s,
                   None, [f"zan_supratrochlear_artery_{s}", f"zan_skin_frontal_region_{s}"], "head",
                   "Continues from the frontal nerve's own division point, medial to the supraorbital nerve, exiting near the trochlea to the medial forehead (Gray's ch.8); anchored here to this page's own real supratrochlear artery, which runs the same course (Gray's: the supratrochlear vessels and nerve run together).",
                   origin_pt=fend, min_len=3.0)
        else:
            for nid, name in ((f"trigeminal_n_v1_supraorbital_branch_{s}", f"Supraorbital nerve ({sw})"), (f"trigeminal_n_v1_supratrochlear_branch_{s}", f"Supratrochlear nerve ({sw})")):
                B.hold(nid, name, "this branch's own parent (the frontal nerve) could not be placed on this page (see that branch's own hold reason)", side=s)
        e_nc = branch(B, S, f"trigeminal_n_v1_nasociliary_branch_{s}", f"Nasociliary nerve ({sw})", f"Nervus nasociliaris {('sinister' if s=='l' else 'dexter')}", s,
                      trunk_v1, [f"superior_oblique_{s}"], "head",
                      "Crosses above the optic nerve to the medial orbital wall near the trochlea of superior oblique (Gray's ch.8), giving off the anterior ethmoidal and infratrochlear branches; represented here as reaching that muscle's own real surface, the shared point of its further branching.")
        if e_nc and e_nc.get("status") == "ship":
            ncend = e_nc["report"]["waypoints"][-1]
            branch(B, S, f"trigeminal_n_v1_anterior_ethmoidal_branch_{s}", f"Anterior ethmoidal nerve ({sw})", f"Nervus ethmoidalis anterior {('sinister' if s=='l' else 'dexter')}", s,
                   None, [f"zan_anterior_ethmoidal_artery_{s}", f"zan_skin_nasal_region_{s}"], "head",
                   "Continues from the nasociliary nerve's own branch point, running WITH the real anterior ethmoidal artery (Gray's ch.8: they share the same canal) to the nasal cavity and, as its external nasal branch, the skin of the nose.",
                   origin_pt=ncend, min_len=3.0)
            branch(B, S, f"trigeminal_n_v1_infratrochlear_branch_{s}", f"Infratrochlear nerve ({sw})", f"Nervus infratrochlearis {('sinister' if s=='l' else 'dexter')}", s,
                   None, [f"orbicularis_oculi_{s}"], "head",
                   "Continues from the nasociliary nerve's own branch point, passing below the trochlea to the skin of the medial eyelids and side of the nose (Gray's ch.8); represented here as reaching the medial part of orbicularis oculi's own real surface nearest that branch point.",
                   origin_pt=ncend, min_len=3.0)
        else:
            for nid, name in ((f"trigeminal_n_v1_anterior_ethmoidal_branch_{s}", f"Anterior ethmoidal nerve ({sw})"), (f"trigeminal_n_v1_infratrochlear_branch_{s}", f"Infratrochlear nerve ({sw})")):
                B.hold(nid, name, "this branch's own parent (the nasociliary nerve) could not be placed on this page (see that branch's own hold reason)", side=s)

        # ================================================================= V2 (maxillary), trunk zan_maxillary_nerve
        trunk_v2 = f"zan_maxillary_nerve_{s}"
        branch(B, S, f"trigeminal_n_v2_infraorbital_branch_{s}", f"Infraorbital nerve ({sw})", f"Nervus infraorbitalis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_v2, [f"zan_infra_orbital_artery_{s}", f"zan_skin_infra_orbital_region_{s}"], "head",
               "The maxillary nerve's direct continuation through the infraorbital groove/canal/foramen (Gray's ch.8); anchored here to this page's own real infraorbital artery, which travels in the same canal, to the named infraorbital-region skin.")
        branch(B, S, f"trigeminal_n_v2_superior_alveolar_branches_{s}", f"Superior alveolar nerves ({sw})", f"Nervi alveolares superiores {('sinister' if s=='l' else 'dexter')}", s,
               trunk_v2, [f"zan_posterior_superior_alveolar_artery_{s}", f"zan_upper_first_molar_tooth_{s}", f"maxilla_{s}"], "head",
               "Descend in the posterior/lateral wall of the maxillary sinus to the maxillary teeth (Gray's ch.8); anchored here to this page's own real posterior superior alveolar artery (same canal) and ending at a real upper molar tooth, representing the maxillary teeth this branch supplies (not all teeth separately).")
        branch(B, S, f"trigeminal_n_v2_zygomatic_branch_{s}", f"Zygomatic nerve ({sw})", f"Nervus zygomaticus {('sinister' if s=='l' else 'dexter')}", s,
               trunk_v2, [f"zan_skin_zygomatic_region_{s}"], "head",
               "Passes through the inferior orbital fissure and the zygomatic bone's own canals to the skin over the zygomatic prominence and temple (zygomaticofacial + zygomaticotemporal branches, Gray's ch.8; not separately modelled); ends on this page's own real named zygomatic-region skin.")
        branch(B, S, f"trigeminal_n_v2_palatine_branches_{s}", f"Palatine nerves ({sw})", f"Nervi palatini {('sinister' if s=='l' else 'dexter')}", s,
               trunk_v2, [f"zan_greater_palatine_artery_{s}", "zan_soft_palate"], "head",
               "Descend through the pterygopalatine canal to the hard and soft palate (Gray's ch.8); anchored here to this page's own real greater palatine artery (same canal), ending on the real soft palate mesh (a near-midline structure -- both sides' branches end on the same mesh, at the nearest point to each side's own course).")

        # ================================================================= V3 (mandibular) masticatory-motor + auriculotemporal
        ant_div = f"zan_anterior_division_of_mandibular_nerve_{s}"
        post_div = f"zan_posterior_division_of_mandibular_nerve_{s}"
        branch(B, S, f"trigeminal_n_v3_masseteric_branch_{s}", f"Masseteric nerve ({sw})", f"Nervus massetericus {('sinister' if s=='l' else 'dexter')}", s,
               ant_div, [f"masseter_{s}"], "head", "Crosses the mandibular notch to reach the deep surface of masseter (Gray's ch.8, a motor branch of the anterior division).")
        branch(B, S, f"trigeminal_n_v3_deep_temporal_branches_{s}", f"Deep temporal nerves ({sw})", f"Nervi temporales profundi {('sinister' if s=='l' else 'dexter')}", s,
               ant_div, [f"temporal_{s}", f"zan_temporalis_muscle_{s}"], "head", "Run up along the infratemporal fossa to the deep surface of temporalis (Gray's ch.8, motor branches of the anterior division).")
        branch(B, S, f"trigeminal_n_v3_medial_pterygoid_branch_{s}", f"Medial pterygoid nerve ({sw})", f"Nervus pterygoideus medialis {('sinister' if s=='l' else 'dexter')}", s,
               ant_div, [f"medial_pterygoid_{s}"], "head",
               "Classically arises directly from the undivided main trunk of V3, before its anterior/posterior division (Gray's ch.8); this atlas ships no separate undivided V3 trunk mesh, so this branch is approximated here as arising from the proximal part of the anterior division instead -- a stated MODELLING deviation from the exact real origin, not an invented course.")
        branch(B, S, f"trigeminal_n_v3_lateral_pterygoid_branch_{s}", f"Lateral pterygoid nerve ({sw})", f"Nervus pterygoideus lateralis {('sinister' if s=='l' else 'dexter')}", s,
               ant_div, [f"lateral_pterygoid_{s}"], "head", "A short motor branch of the anterior division to the deep surface of lateral pterygoid (Gray's ch.8).")
        branch(B, S, f"trigeminal_n_v3_auriculotemporal_branch_{s}", f"Auriculotemporal nerve ({sw})", f"Nervus auriculotemporalis {('sinister' if s=='l' else 'dexter')}", s,
               post_div, [f"zan_skin_temporal_region_{s}"], "head",
               "Arises from the posterior division, passes posterior to the temporomandibular joint and through the parotid gland to the temple (Gray's ch.8); ends on this page's own real named temporal-region skin.")

        # ================================================================= VII (facial) terminal branches, trunk zan_facial_nerve_vii
        trunk_vii = f"zan_facial_nerve_vii_{s}"
        branch(B, S, f"facial_n_temporal_branch_{s}", f"Facial n., temporal branch ({sw})", f"Ramus temporalis nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"frontalis_{s}"], "head", "One of the 5 terminal 'pes anserinus' branches within the parotid gland (Gray's ch.8); supplies frontalis and the muscles around the eye/ear (not all separately modelled -- frontalis is this atlas' own real target).")
        branch(B, S, f"facial_n_zygomatic_branch_{s}", f"Facial n., zygomatic branch ({sw})", f"Ramus zygomaticus nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"orbicularis_oculi_{s}"], "head", "Supplies orbicularis oculi and the upper-face muscles of expression (Gray's ch.8).")
        branch(B, S, f"facial_n_buccal_branch_{s}", f"Facial n., buccal branch ({sw})", f"Ramus buccalis nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"orbicularis_oris_{s}"], "head", "Supplies buccinator and the mid-face muscles of expression (Gray's ch.8); this atlas ships no separate buccinator mesh, so the branch ends on orbicularis oris, its other principal real target.")
        branch(B, S, f"facial_n_marginal_mandibular_branch_{s}", f"Facial n., marginal mandibular branch ({sw})", f"Ramus marginalis mandibulae nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"depressor_labii_inferioris_{s}", f"depressor_anguli_oris_{s}", f"mentalis_{s}"], "head", "Runs along the mandible's lower border to the lower-lip depressor muscles (Gray's ch.8).")
        branch(B, S, f"facial_n_cervical_branch_{s}", f"Facial n., cervical branch ({sw})", f"Ramus colli nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"platysma_{s}"], "head", "The most inferior terminal branch, running onto the neck to supply platysma (Gray's ch.8).")
        branch(B, S, f"facial_n_posterior_auricular_branch_{s}", f"Facial n., posterior auricular branch ({sw})", f"Ramus auricularis posterior nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"zan_skin_mastoid_region_{s}", f"zan_skin_posterior_auricular_groove_{s}"], "head",
               "Arises just after the stylomastoid foramen, before the main pes anserinus division, to the occipitalis and the tiny auricular muscles (Gray's ch.8); this atlas ships no auricular-muscle meshes, so the branch ends on the real named mastoid-region skin it also supplies.")
        branch(B, S, f"facial_n_digastric_branch_{s}", f"Facial n., digastric branch ({sw})", f"Ramus digastricus nervi facialis {('sinister' if s=='l' else 'dexter')}", s,
               trunk_vii, [f"digastric_{s}"], "head", "Arises near the posterior auricular branch, to the posterior belly of digastric and stylohyoid (Gray's ch.8); this atlas ships one undivided digastric mesh (not split into anterior/posterior bellies), so the branch ends on that whole muscle's own real surface, nearest the facial nerve's own course.")

        # ================================================================= IX (glossopharyngeal), trunk glossopharyngeal_n
        trunk_ix = f"glossopharyngeal_n_{s}"
        branch(B, S, f"glossopharyngeal_n_stylopharyngeus_branch_{s}", f"Glossopharyngeal n., branch to stylopharyngeus ({sw})", f"Ramus musculi stylopharyngei {('sinister' if s=='l' else 'dexter')}", s,
               trunk_ix, [f"stylopharyngeus_{s}"], "head", "The glossopharyngeal nerve's only motor branch, to stylopharyngeus (Gray's ch.8).")
        branch(B, S, f"glossopharyngeal_n_tympanic_branch_{s}", f"Glossopharyngeal n., tympanic branch ({sw})", f"Ramus tympanicus {('sinister' if s=='l' else 'dexter')}", s,
               trunk_ix, [f"zan_tympanic_membrane_{s}"], "head", "The nerve of Jacobson: re-enters the skull to supply the mucosa of the middle ear and the tympanic membrane's inner surface (Gray's ch.8), continuing as the lesser petrosal nerve to the otic ganglion (not modelled: no ganglion mesh on any page).")
        branch(B, S, f"glossopharyngeal_n_carotid_branch_{s}", f"Glossopharyngeal n., carotid branch ({sw})", f"Ramus sinus carotici {('sinister' if s=='l' else 'dexter')}", s,
               trunk_ix, [f"zan_internal_carotid_artery_{s}", f"zan_external_carotid_artery_{s}"], "head",
               "Descends to the carotid sinus/body at the common carotid bifurcation (Gray's ch.8); this atlas ships no separate carotid-bifurcation mesh, so the branch ends on whichever of the internal/external carotid artery's own real surface is nearest the nerve's course, the closest real approximation of that junction available on this page.")
        branch(B, S, f"glossopharyngeal_n_tonsillar_branches_{s}", f"Glossopharyngeal n., tonsillar branches ({sw})", f"Rami tonsillares {('sinister' if s=='l' else 'dexter')}", s,
               trunk_ix, [f"zan_palatine_tonsil_{s}"], "head", "Form a plexus around the palatine tonsil, supplying its mucosa and the adjacent soft palate/fauces (Gray's ch.8).")
        branch(B, S, f"glossopharyngeal_n_lingual_branch_{s}", f"Glossopharyngeal n., lingual branch ({sw})", f"Rami linguales {('sinister' if s=='l' else 'dexter')}", s,
               trunk_ix, ["zan_tongue"], "head", "Supplies general sensation and taste to the posterior third of the tongue (Gray's ch.8); ends on the real tongue mesh (a midline structure -- each side's branch reaches the nearest, i.e. its own, half).")

        # ================================================================= X (vagus) cervical branches other than the recurrent laryngeal (already shipped, Q259)
        trunk_x = f"zan_vagus_nerve_x_{s}"
        branch(B, S, f"vagus_n_superior_laryngeal_branch_{s}", f"Superior laryngeal nerve ({sw})", f"Nervus laryngeus superior {('sinister' if s=='l' else 'dexter')}", s,
               trunk_x, [f"cricothyroid_{s}"], "head",
               "Descends alongside the carotid sheath and divides into an internal branch (sensory, to laryngeal mucosa above the vocal folds -- not separately modelled, no laryngeal-mucosa mesh) and an external branch (motor, to cricothyroid -- Gray's ch.8); this branch represents the external (motor) branch, ending on cricothyroid's own real surface.")
        e_ph = branch(B, S, f"vagus_n_pharyngeal_contribution_{s}", f"Vagus n., pharyngeal plexus contribution ({sw})", f"Ramus pharyngeus {('sinister' if s=='l' else 'dexter')}", s,
                       trunk_x, [f"superior_pharyngeal_constrictor_{s}"], "head",
                       "The vagus's own contribution to the pharyngeal plexus (which also receives glossopharyngeal and sympathetic fibres, not re-modelled here), reaching the superior pharyngeal constrictor, the plexus's highest real target on this page (Gray's ch.8).")
        if e_ph and e_ph.get("status") == "ship":
            phend = e_ph["report"]["waypoints"][-1]
            branch(B, S, f"pharyngeal_plexus_to_constrictors_{s}", f"Pharyngeal plexus, branch to constrictors ({sw})", f"Rami pharyngei ad musculos constrictores {('sinister' if s=='l' else 'dexter')}", s,
                   None, [f"middle_pharyngeal_constrictor_{s}"], "head",
                   "Continues from the plexus's own real reach on the superior constrictor down to the middle pharyngeal constrictor -- a genuinely distinct real muscle at a lower real level, not the same location repeated (Gray's ch.8; the inferior constrictor's own motor supply is predominantly via the external/recurrent laryngeal nerves and is not separately represented here).",
                   origin_pt=phend, min_len=5.0)
        else:
            B.hold(f"pharyngeal_plexus_to_constrictors_{s}", f"Pharyngeal plexus, branch to constrictors ({sw})",
                   "this branch's own parent (the vagus's pharyngeal contribution) could not be placed on this page (see that branch's own hold reason)", side=s)
        branch(B, S, f"vagus_n_cardiac_branches_{s}", f"Vagal cardiac branches ({sw})", f"Rami cardiaci {('sinister' if s=='l' else 'dexter')}", s,
               trunk_x, [f"zan_right_atrium" if s == "r" else f"zan_left_atrium", "zan_right_atrium", "zan_left_atrium"], "thorax",
               "Cervical and thoracic cardiac branches descend to join the cardiac plexus at the base of the great vessels/heart (Gray's ch.4/8); this atlas ships no separate cardiac-plexus mesh, so the branch ends on a real atrium's own surface, the nearest real heart-chamber landmark to that plexus's documented location (right atrium for the right vagus, which contributes predominantly to the sinoatrial-node region; left atrium for the left, a stated simplification, not a precisely segmented plexus).",
               max_dist=220.0)

        # ================================================================= XI (accessory), trunk zan_accessory_nerve_xi
        trunk_xi = f"zan_accessory_nerve_xi_{s}"
        e_scm = branch(B, S, f"accessory_n_scm_branch_{s}", f"Accessory n., branch to sternocleidomastoid ({sw})", f"Ramus musculi sternocleidomastoidei {('sinister' if s=='l' else 'dexter')}", s,
                        trunk_xi, [f"sternocleidomastoid_{s}"], "neck", "The spinal root of CN XI pierces and supplies sternocleidomastoid before crossing the posterior triangle (Gray's ch.8).")
        if e_scm and e_scm.get("status") == "ship":
            scm_end = e_scm["report"]["waypoints"][-1]
            branch(B, S, f"accessory_n_trapezius_branch_{s}", f"Accessory n., branch to trapezius ({sw})", f"Ramus musculi trapezii {('sinister' if s=='l' else 'dexter')}", s,
                   None, [f"trapezius_{s}"], "neck",
                   "Continues from sternocleidomastoid's own posterior border across the posterior triangle of the neck to the deep surface of trapezius (Gray's ch.8) -- the row's own 'distal course to trapezius'.",
                   origin_pt=scm_end, min_len=5.0, max_dist=220.0)
        else:
            branch(B, S, f"accessory_n_trapezius_branch_{s}", f"Accessory n., branch to trapezius ({sw})", f"Ramus musculi trapezii {('sinister' if s=='l' else 'dexter')}", s,
                   trunk_xi, [f"trapezius_{s}"], "neck",
                   "Continues across the posterior triangle of the neck to the deep surface of trapezius (Gray's ch.8); built directly from the trunk since the sternocleidomastoid branch above could not be placed on this page.",
                   max_dist=220.0)
    return [e for e in B.out], {}


HELD_OWN = [
    ("trigeminal_n_v1_lacrimal_branch", "Lacrimal nerve"), ("trigeminal_n_v1_frontal_branch", "Frontal nerve"),
    ("trigeminal_n_v1_supraorbital_branch", "Supraorbital nerve"), ("trigeminal_n_v1_supratrochlear_branch", "Supratrochlear nerve"),
    ("trigeminal_n_v1_nasociliary_branch", "Nasociliary nerve"), ("trigeminal_n_v1_anterior_ethmoidal_branch", "Anterior ethmoidal nerve"),
    ("trigeminal_n_v1_infratrochlear_branch", "Infratrochlear nerve"),
    ("trigeminal_n_v2_infraorbital_branch", "Infraorbital nerve"), ("trigeminal_n_v2_superior_alveolar_branches", "Superior alveolar nerves"),
    ("trigeminal_n_v2_zygomatic_branch", "Zygomatic nerve"), ("trigeminal_n_v2_palatine_branches", "Palatine nerves"),
    ("trigeminal_n_v3_masseteric_branch", "Masseteric nerve"), ("trigeminal_n_v3_deep_temporal_branches", "Deep temporal nerves"),
    ("trigeminal_n_v3_medial_pterygoid_branch", "Medial pterygoid nerve"), ("trigeminal_n_v3_lateral_pterygoid_branch", "Lateral pterygoid nerve"),
    ("trigeminal_n_v3_auriculotemporal_branch", "Auriculotemporal nerve"),
    ("facial_n_temporal_branch", "Facial n., temporal branch"), ("facial_n_zygomatic_branch", "Facial n., zygomatic branch"),
    ("facial_n_buccal_branch", "Facial n., buccal branch"), ("facial_n_marginal_mandibular_branch", "Facial n., marginal mandibular branch"),
    ("facial_n_cervical_branch", "Facial n., cervical branch"), ("facial_n_posterior_auricular_branch", "Facial n., posterior auricular branch"),
    ("facial_n_digastric_branch", "Facial n., digastric branch"),
    ("glossopharyngeal_n_stylopharyngeus_branch", "Glossopharyngeal n., branch to stylopharyngeus"), ("glossopharyngeal_n_tympanic_branch", "Glossopharyngeal n., tympanic branch"),
    ("glossopharyngeal_n_carotid_branch", "Glossopharyngeal n., carotid branch"), ("glossopharyngeal_n_tonsillar_branches", "Glossopharyngeal n., tonsillar branches"),
    ("glossopharyngeal_n_lingual_branch", "Glossopharyngeal n., lingual branch"),
    ("vagus_n_superior_laryngeal_branch", "Superior laryngeal nerve"), ("vagus_n_pharyngeal_contribution", "Vagus n., pharyngeal plexus contribution"),
    ("pharyngeal_plexus_to_constrictors", "Pharyngeal plexus, branch to constrictors"), ("vagus_n_cardiac_branches", "Vagal cardiac branches"),
    ("accessory_n_scm_branch", "Accessory n., branch to sternocleidomastoid"), ("accessory_n_trapezius_branch", "Accessory n., branch to trapezius"),
]

if __name__ == "__main__":
    import json
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        items, _ = build(k)
        ship = [i for i in items if i["status"] == "ship"]
        held = [i for i in items if i["status"] != "ship"]
        print(k, "ship", len(ship), "held", len(held))
        for h in held:
            print("   HELD", h["id"], "|", h["held"])
