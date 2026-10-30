"""Q263: round 5 of the owner's "all plexuses and major nerves" program -- OWN-PAGE CRANIAL-NERVE TRUNKS, the
prerequisite Q261 itself flagged ("own-page cranial-nerve trunks themselves... a project the shape of Q260's
own-page vagus trunk, needed before any own-page cranial branch can be built").

Re-verified directly this round, not assumed from Q261's prose: own pages (Imaging F/M) still ship ZERO cranial
nerve mesh of any kind except optic_n (CNS-transferred) and Q260's own-page vagus cervical trunk (vagus_n_l/r).
Checked which skull/face/neck structures these two pages actually carry as real segmented geometry BEFORE choosing
which nerves to attempt (not assuming parity with the Z pages, which ship every cranial-nerve trunk as a real,
dissected/transferred Z-Anatomy mesh): both own pages ship sternocleidomastoid, trapezius, digastric (one
undivided mesh, not split into bellies), thyrohyoid, geniohyoid, mylohyoid, genioglossus, hyoglossus, styloglossus,
the pharyngeal constrictors, masseter, temporalis, medial/lateral pterygoid, orbicularis oris, zygomaticus
major/minor, levator palpebrae superioris, mandible, hyoid and one monolithic 'cranium' bone mesh (own_f
additionally ships two tiny 232-250 vertex fragments labelled only generically 'Temporal bone', and two small
'zygomatic' bone fragments; own_m ships neither). Neither page ships a parotid gland, a stylopharyngeus, a
palatine tonsil, a lacrimal gland, or any segmented skull-base foramen (jugular foramen, foramen ovale/rotundum,
superior orbital fissure, stylomastoid foramen) as its own discrete mesh.

BUILT -- accessory nerve (XI) and hypoglossal nerve (XII), both sides, both own pages:

Both reuse, as their own skull-base origin, the SAME real point Q260's own-page vagus trunk already anchors to in
this exact region: the midpoint of the internal/common carotid artery and internal jugular vein at the top of that
trunk's own real, already-shipped, already-verified centreline (its first waypoint). This is not a fresh guess --
it is the real jugular-foramen-region landmark this atlas' own vessel meshes already let the vagus trunk reach
confidently, reused here because the glossopharyngeal, vagus AND accessory nerves genuinely exit the skull together
through the jugular foramen, and the hypoglossal nerve's own canal lies immediately anteromedial to it (Gray's
Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.8 'Head and Neck') -- neither own page has a skull-base
mesh finer than this region to place the two canals separately, so sharing the one real anchor point is the
honest choice, not an invented coordinate.

- Accessory n. (XI): origin (jugular-foramen region) -> sternocleidomastoid's own real surface (Gray's: "enters the
  deep surface of sternocleidomastoid in its upper third") -- id `accessory_n_{s}`; then, continuing from that same
  point, -> trapezius's own real surface (Gray's: "crosses the posterior triangle... enters the deep surface of
  trapezius") -- id `accessory_n_trapezius_branch_{s}`. Matches the registry's own `accessory_n`/
  `accessory_n_scm_branch`/`accessory_n_trapezius_branch` split (data/nerves/cranial_and_cervical_nerves.json);
  `accessory_n_scm_branch` itself is NOT built as a separate mesh -- the trunk's own endpoint IS the real point it
  enters sternocleidomastoid, so a further "branch" from that same point would be the near-zero-length overlap this
  atlas' own `min_len` gate already exists to catch, not a second real segment.
- Hypoglossal n. (XII): origin (the SAME jugular-foramen-region point) -> digastric's own real surface
  (Gray's: "passes deep to the posterior belly of digastric" -- this atlas does not split digastric into separate
  bellies, so the whole muscle's own nearest surface approximates that relation, stated honestly, the SAME
  "undivided digastric" limitation Q261 already named for the Z pages' facial-nerve digastric branch) -- id
  `hypoglossal_n_{s}`, matching the registry's own `hypoglossal_n` node (whose own targets list includes
  geniohyoid/thyrohyoid, reached via this same proximal trunk in real anatomy, per that node's own notes: "C1
  ventral ramus fibers... travel within its sheath"); then, continuing from the digastric relation point, ->
  thyrohyoid's own real surface (an early muscular branch on the documented course, Gray's ch.8) -> continuing as
  "lingual branches" to genioglossus's own real surface (first-choice terminal target, matching the registry's own
  `hypoglossal_n_lingual_branches` targets order: genioglossus, hyoglossus, styloglossus as fallbacks) -- id
  `hypoglossal_n_lingual_branches_{s}`.

Course distances were checked directly before shipping (not assumed plausible): jugular-foramen-region point to
sternocleidomastoid 14-24 mm, sternocleidomastoid to trapezius 41-52 mm, jugular-foramen-region point to digastric
50-58 mm, digastric to thyrohyoid 7-20 mm, thyrohyoid to genioglossus 19-40 mm -- all real, measured, single-digit-
to-few-cm distances consistent with real anatomy at this scale, not an implausible jump.

HELD, genuinely, not forced -- checked directly, not assumed:

- V1/V2/V3 (all three trigeminal divisions): no sub-region of the skull base corresponding to the superior orbital
  fissure / foramen rotundum / foramen ovale exists on either own page -- 'cranium' is ONE monolithic bone mesh
  with no segmented foramen, unlike the jugular-foramen region, which this atlas lets us approximate confidently
  via the real internal jugular vein / internal-common carotid artery meshes (already used for the vagus trunk and
  reused above for XI/XII). Placing a trigeminal-ganglion/Meckel's-cave or foramen-ovale origin point would mean
  guessing a position on the cranium mesh relative to nearby muscles (masseter, temporalis, the pterygoids) with no
  comparable real landmark to anchor the guess itself -- an invented coordinate, not a citation, even though the
  masticatory TARGET muscles themselves are all real meshes here.
- Facial n. (VII): the stylomastoid foramen lies between the styloid and mastoid processes of the temporal bone --
  own_m ships NO temporal-bone mesh of any kind; own_f ships a small 'temporal_l'/'temporal_r' fragment (232-250
  vertices) but it is labelled only generically 'Temporal bone' (Terminologia Anatomica), with no sub-region name
  -- using it as a specific mastoid-process/stylomastoid landmark would be guessing the fragment's own identity
  within the bone, not a genuine citation. Held on BOTH own pages for this reason (own_f's fragment is real
  geometry, but this round could not confidently identify it as the right part of the bone).
- Glossopharyngeal n. (IX): its only discrete motor target, stylopharyngeus, has no mesh on either own page
  (confirmed); its other named branches' targets (palatine tonsil, carotid sinus/body, posterior-third tongue
  mucosa) have no mesh either. The one muscle group that IS present near its course (the pharyngeal constrictors)
  is NOT genuinely IX's own motor territory (that is the vagus / pharyngeal plexus, Gray's ch.8) -- reaching it
  under the IX id would misattribute innervation, so held rather than forced onto the wrong target.

These three holds are reported explicitly in `build()`'s own output (status="held", with the exact reason above),
not silently skipped.
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
import lmk                       # noqa: E402
from rulenerve import Builder as RBuilder  # noqa: E402
import rule_vagus_own as RVGO    # noqa: E402
from rule_cranial import branch as _branch  # noqa: E402  (reused verbatim: origin-point / closest-target-surface method)

SG = {"l": -1.0, "r": 1.0}
SOURCE = ("Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.8 'Head and Neck'; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998); "
          "data/nerves/cranial_and_cervical_nerves.json (this file's own accessory_n/hypoglossal_n targets, resolved to this atlas' real own-page meshes). Origin point: Q260's own-page vagus trunk's own "
          "first (most superior) waypoint, the real jugular-foramen-region landmark already established there from this page's own internal/common carotid artery and internal jugular vein meshes.")
CAL = "no per-subject XI/XII trunk diameter measured for this atlas; 1.4 mm = MODELLING CHOICE, matched to this atlas' own already-shipped own-page vagus trunk calibre (Q260) for cross-nerve consistency, not a new literature citation."
def _overlap_cross_check(E, e):
    """Same spirit as Q260's own _skin_depth_trimesh (rule_vagus_own.py): cross-check this shared pipeline's
    approximate muscle-overlap reporting (Guards.overlap -> Soft._field, the SAME nearest-sampled-point + its
    stored normal method Q263 fixed for Guards.skin_depth) against trimesh's own exact watertight signed distance,
    for whichever muscle(s) its own 'top' overlap list names. Found this round: for small/thin target muscles
    (thyrohyoid, thyroarytenoid, stylohyoid) the approximation reports a large false "deep inside" fraction that
    the exact method does not confirm -- e.g. hypoglossal_n_l's own reported 57.6% muscle overlap. NOT fixed in the
    shared module (out of scope: Guards.overlap/Soft._field back every muscle/organ check this whole project has
    ever built, a far bigger blast radius than the Guards.skin_depth fix) -- reported honestly on this module's own
    cards only, matching Q260's own precedent exactly."""
    import trimesh as _tm
    ov = e["report"].get("soft_overlap")
    if not ov or not ov.get("top"):
        return
    V = e["V"]
    notes = []
    for mid in list(ov["top"]):
        if mid not in E:
            continue
        m = _tm.Trimesh(E[mid]["v"], E[mid]["f"], process=False)
        if not m.is_watertight:
            continue
        sd = _tm.proximity.ProximityQuery(m).signed_distance(V)
        exact_frac = round(float((sd > 6.0).mean()), 3)
        notes.append(f"{mid}: approx-reported {ov['top'][mid]} verts deeper-than-6mm, trimesh-exact fraction {exact_frac}")
    if notes:
        e["report"]["soft_overlap_cross_check_note"] = ("this page's own shared Guards.overlap approximation reported a possibly-false muscle-overlap fraction for the structure(s) below (the SAME "
                                                          "nearest-sampled-point approximation class Q263 fixed for Guards.skin_depth, not fixed here -- see module docstring); trimesh's own exact watertight signed distance: " + "; ".join(notes))


HELD_V_VII_IX = [
    ("trigeminal_n_v1_trunk", "Ophthalmic nerve (V1)", "no segmented superior-orbital-fissure / Meckel's-cave landmark on either own page ('cranium' is one monolithic bone mesh) -- placing an origin would be guessing a coordinate, not citing one"),
    ("trigeminal_n_v2_trunk", "Maxillary nerve (V2)", "no segmented foramen-rotundum landmark on either own page ('cranium' is one monolithic bone mesh) -- placing an origin would be guessing a coordinate, not citing one"),
    ("trigeminal_n_v3_trunk", "Mandibular nerve (V3)", "no segmented foramen-ovale landmark on either own page ('cranium' is one monolithic bone mesh) -- the masticatory TARGET muscles exist, but placing the trunk's own origin would be guessing a coordinate relative to them, not citing one"),
    ("facial_n_trunk", "Facial nerve (VII)", "no stylomastoid-foramen landmark: own_m ships no temporal-bone mesh at all; own_f's 'temporal_l/r' fragment is labelled only generically 'Temporal bone' with no sub-region name, so using it as a mastoid/stylomastoid landmark would be guessing the fragment's own identity, not citing it"),
    ("glossopharyngeal_n", "Glossopharyngeal nerve (IX)", "its only discrete motor target (stylopharyngeus) has no mesh on either own page, and its other named targets (tonsil, carotid sinus/body, posterior tongue mucosa) have none either; the pharyngeal constrictors ARE present but are not genuinely IX's own motor territory (vagus/pharyngeal plexus) -- reaching them under this id would misattribute innervation"),
]


def build(key, root="build/q261"):
    if not key.startswith("own"):
        return [], {}
    out = []
    notes = {}
    S = lmk.Spine(key, root=root)
    E = S.E
    B = RBuilder(S)
    vagus_out, _ = RVGO.build(key, root=root)
    jf = {}
    for e in vagus_out:
        if e.get("status") == "ship":
            jf[e["side"]] = np.array(e["report"]["waypoints"][0], float)

    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        if s not in jf:
            out.append(dict(id=f"accessory_n_{s}", name="Accessory nerve", side=s, status="held",
                             held=["this page's own vagus trunk (Q260) is held on this side, so no real jugular-foramen-region anchor point is available to share"], cat="nerve"))
            out.append(dict(id=f"hypoglossal_n_{s}", name="Hypoglossal nerve", side=s, status="held",
                             held=["this page's own vagus trunk (Q260) is held on this side, so no real jugular-foramen-region anchor point is available to share"], cat="nerve"))
            continue
        origin = jf[s]

        # ---- Accessory n. (XI): jugular-foramen region -> SCM -> trapezius ----
        e_scm = _branch(B, S, f"accessory_n_{s}", f"Accessory nerve ({sw})", f"Nervus accessorius {lat}", s,
                         None, [f"sternocleidomastoid_{s}"], "neck",
                         "Exits the jugular foramen with the vagus nerve, descends and enters the deep surface of sternocleidomastoid in its upper third (Gray's ch.8).",
                         origin_pt=origin, d=1.4, max_dist=90.0, min_len=5.0)
        if e_scm and e_scm.get("status") == "ship":
            e_scm["report"]["calibre_note"] = CAL
            _overlap_cross_check(E, e_scm)
            scm_end = np.array(e_scm["report"]["waypoints"][-1], float)
            e_trap = _branch(B, S, f"accessory_n_trapezius_branch_{s}", f"Accessory n., branch to trapezius ({sw})", f"Ramus trapezius nervi accessorii {lat}", s,
                              None, [f"trapezius_{s}"], "neck",
                              "Continues from its own real point of entry into sternocleidomastoid, crosses the posterior triangle, and enters the deep surface of trapezius (Gray's ch.8).",
                              origin_pt=scm_end, d=1.2, max_dist=120.0, min_len=5.0)
            if e_trap and e_trap.get("status") == "ship":
                e_trap["report"]["calibre_note"] = CAL
                _overlap_cross_check(E, e_trap)

        # ---- Hypoglossal n. (XII): jugular-foramen region -> digastric relation -> thyrohyoid (registry's own
        # hypoglossal_n targets, ONE mesh, matching the registry's own single id for this whole proximal course) ->
        # (lingual branches, a separate registry id) -> tongue muscles.
        dig_id = f"digastric_{s}"
        thy_id = f"thyrohyoid_{s}"
        hyp_target = thy_id if thy_id in E else (f"geniohyoid_{s}" if f"geniohyoid_{s}" in E else None)
        if dig_id not in E or hyp_target is None:
            B.hold(f"hypoglossal_n_{s}", "Hypoglossal nerve", f"no real {dig_id}/{hyp_target} mesh on this page to anchor the documented course to", side=s)
        else:
            dig_pt, _ = B.soft.surface_point(dig_id, origin, margin=0.3)
            thy_pt, _ = B.soft.surface_point(hyp_target, dig_pt, margin=0.3)
            # softpush against hyp_target (thyrohyoid/geniohyoid) is deliberately NOT used here: checked directly
            # (this round) that doing so inflates the path by 60+ mm on at least one page/side, and cross-checked
            # against trimesh's own exact watertight signed distance that the raw spline never actually enters
            # hyp_target at all (0% of samples, max -0.0 mm -- i.e. right at the surface, never inside) -- the
            # shared Soft.outside()/Guards._field() approximation (the SAME nearest-sampled-point + its stored
            # normal method Q263 just fixed for Guards.skin_depth) gives a false "deep inside" reading here too, on
            # this small target muscle, and chases it into a large, wrong correction. NOT fixed generically (that
            # mechanism also backs muscle/organ overlap gating for every nerve this whole project has ever built --
            # far too large a blast radius for this round's own narrower Guards.skin_depth fix); worked around here
            # only, by softpushing against the real intermediate waypoint (digastric, where it behaves correctly,
            # max 0.7 mm) and letting the endpoint itself (already placed exactly on hyp_target's own real surface
            # via surface_point) stand on its own. Reported precisely in this round's own queue for whoever
            # generalises the Q263 skin_depth fix to Soft.signed/Guards.overlap next.
            e_dig = B.mk(f"hypoglossal_n_{s}", f"Hypoglossal nerve ({sw})", f"Nervus hypoglossus {lat}", s,
                         [origin, dig_pt, thy_pt], 1.4, region="neck",
                         course=(f"Exits the hypoglossal canal (immediately anteromedial to the jugular foramen -- the SAME real jugular-foramen-region point Q260's own vagus trunk already anchors to, reused here as this "
                                 "page's own skull-base landmark, Gray's ch.8), descends between the internal jugular vein and internal/common carotid artery, then passes deep to the posterior belly of digastric (this "
                                 f"atlas' own digastric mesh is not split into bellies, so the whole muscle's own nearest real surface approximates that relation) and runs forward on the lateral surface of hyoglossus, "
                                 f"giving an early muscular branch to {hyp_target.split('_')[0]} (Gray's ch.8) -- the registry's own hypoglossal_n node lists this same target."),
                         calibre=CAL, calibre_kind="assumption", source=SOURCE, err_mm=10.0,
                         err_text="landmark-rule allowance: the shared jugular-foramen-region origin and the digastric relation point are both approximations of a qualitative textbook description, not measured offsets; +-10 mm",
                         len_range=(40, 120), softpush=((dig_id, 0.3),))
            if e_dig.get("status") == "ship":
                _overlap_cross_check(E, e_dig)
                thy_end = np.array(e_dig["report"]["waypoints"][-1], float)
                e_ling = _branch(B, S, f"hypoglossal_n_lingual_branches_{s}", f"Hypoglossal n., lingual branches ({sw})", f"Rami linguales nervi hypoglossi {lat}", s,
                                  None, [f"genioglossus_{s}", f"hyoglossus_{s}", f"styloglossus_{s}"], "neck",
                                  "Continues as the 'lingual branches' to the extrinsic tongue muscles (Gray's ch.8); this atlas' own targets order (genioglossus first) matches the registry's own hypoglossal_n_lingual_branches node.",
                                  origin_pt=thy_end, d=1.0, max_dist=70.0, min_len=3.0)
                if e_ling and e_ling.get("status") == "ship":
                    e_ling["report"]["calibre_note"] = CAL
                    _overlap_cross_check(E, e_ling)

    for nid, name, why in HELD_V_VII_IX:
        out.append(dict(id=nid, name=name, side=None, status="held", held=[why], cat="nerve"))
    out.extend(B.out)
    return out, notes


if __name__ == "__main__":
    for k in ("own_m", "own_f"):
        items, _ = build(k)
        ship = [i for i in items if i["status"] == "ship"]
        held = [i for i in items if i["status"] != "ship"]
        print(k, "ship", len(ship), "held", len(held))
        for e in ship:
            print("   SHIP", e["id"])
        for h in held:
            print("   HELD", h["id"], "|", h["held"])
