"""Q259: the CERVICAL PLEXUS (C1-C4 ventral rami, ansa cervicalis, phrenic nerve origin + proximal course, the
scalene/prevertebral muscular branch, and the 4 cutaneous branches) -- completely absent on all six pages today
(Q247/Q258 audit: 0 of 14 registry items, data/nerves/cranial_and_cervical_nerves.json), the single most glaring
parallel to the brachial-plexus gap Q258 just closed: same interscalene / posterior-triangle region, one level more
superior/posterior.

Method: same rule-based family as Q258's brachial plexus and Q249's pelvic nerves -- a round tube along a spline
through waypoints measured on THIS page's own cervical vertebrae (C1-C4), sternocleidomastoid, the scalenes, the
common carotid artery and (where the page ships them) the infrahyoid strap muscles, following the course described
in Gray's Anatomy for Students 4th ed. (Drake, Vogl, Mitchell) ch.8 and Terminologia Anatomica (the same two sources
already cited by every node of the registry file above) -- not segmented, not Z-Anatomy geometry (built fresh here
even on the four Z pages, which carry NONE of this plexus either, unlike the brachial plexus where only two cords
were missing there).

Explicitly OUT OF SCOPE this round, stated plainly rather than guessed: `phrenic_n_terminal` (the diaphragmatic
branches) -- the brief scopes the phrenic nerve to "origin + proximal course"; reaching the diaphragm needs a
thoracic course this round did not attempt to verify waypoint-by-waypoint. `cervical_plexus_to_scalenes_and_prevertebrals`
is built only to the scalenes themselves (scalenus anterior/medius/posterior, already real muscles on every page);
its longus colli / longus capitis / rectus capitis targets are each a separate short segmental twig in reality and
are represented here by one indicative branch to scalenus anterior rather than nine near-duplicate stubs.
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
import lmk                     # noqa: E402
from rulenerve import Builder  # noqa: E402

ROOT_DEFAULT = "build/q258"
SG = {"l": -1.0, "r": 1.0}
SOURCE = "Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.8; Terminologia Anatomica (FICAT 1998); data/nerves/cranial_and_cervical_nerves.json."
ERR = 9.0
ERR_TEXT = "landmark-rule allowance for a cervical-plexus-sized structure (no page-specific calibre or caliper study exists for this unsegmented deep plexus); +-9 mm"


def carotid_id(E, key, s):
    if key.startswith("own"):
        return f"common_carotid_a_{s}" if f"common_carotid_a_{s}" in E else None
    side_word = "left" if s == "l" else "right"
    cand = f"zan_{side_word}_common_carotid_artery"
    return cand if cand in E else None


def carotid_point_at_y(S, s, y_target):
    cid = carotid_id(S.E, S.key, s)
    if cid is None:
        return None
    C = S.centerline(cid, n=40)
    if C is None:
        return None
    j = int(np.argmin(np.abs(C[:, 1] - y_target)))
    return C[j]


def pull_to_skin_point(gd, p, depth=1.5):
    """move a single point to at least `depth` mm inside the page's skin (own pages: the one closed skin mesh,
    signed; Z pages: no-op here, Z endpoints are instead placed directly on a named skin patch by `skin_target`).
    Unlike guards.Guards.skin_pull (used on a whole tube with its end points deliberately protected), this is for
    ONE point that IS the intended end -- it must be allowed to move."""
    if "skin" not in gd.E:
        return p
    kd, nn = gd._field("skin")
    d, k = kd.query(p[None])
    s = ((p - kd.data[k[0]]) * nn[k[0]]).sum()
    dep = d[0] if s < 0 else -d[0]
    if dep < depth:
        p = p - nn[k[0]] * (depth - dep)
    return p


def skin_target(B, S, s, zan_patches, own_offset, radius=0.6):
    """Z pages: nearest surface point of the first available named skin patch (real, named regional skin), offset
    outward by the tube's own radius so its OUTER surface sits at/just outside the patch, not its centreline.
    Own pages: an offset point from a nearby real landmark, pulled to sit a little inside the page's one closed
    skin mesh (pull_to_skin_point) -- the terminal end of a cutaneous nerve really does reach the dermis, so this
    is a best-effort placement, not a precise segmentation."""
    if S.z:
        for pid in zan_patches:
            if pid in S.E:
                pt, _ = B.soft.surface_point(pid, own_offset, margin=radius + 0.3)
                if pt is not None:
                    return pt
        return own_offset
    return pull_to_skin_point(B.gd, own_offset, depth=radius + 1.0)


def build(key, root=ROOT_DEFAULT):
    S = lmk.Spine(key, root=root)
    B = Builder(S)
    E = S.E
    xm = S.xm
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        sg = SG[s]
        # ---------------------------------------------------------------- C1-C4 ventral rami
        root_pt = {}
        for lvl in ("c1", "c2", "c3", "c4"):
            p0 = S.lateral(lvl, s)
            if p0 is None:
                B.hold(f"cervical_plexus_root_{lvl}_{s}", f"Cervical plexus root, ventral ramus {lvl.upper()}", f"no {lvl} vertebra mesh on this page", side=s)
                continue
            # the target height is biased 18 mm BELOW the vertebra's own level: the ramus trends inferiorly as it
            # runs deep to sternocleidomastoid anyway, and for C1 specifically a same-height target sits right at
            # the skull base / jugular-foramen region, where the generic bone signed-distance field (surface-sample
            # based) misclassifies a point just outside the cranium as deeply inside it (checked directly: a
            # same-height C1 target gave min signed distance -38 mm after push-out, an 18-mm-lower target -2 mm,
            # i.e. just the anchor touching its own vertebra by the usual anchored-origin convention) -- caught by
            # inspecting the push-out result before shipping, not assumed to be fine.
            deep = S.scm_posterior(s, p0[1] - 18.0)
            if deep is None:
                deep = p0 + np.array([sg * 8.0, -2.0, 6.0])
            mid = 0.5 * (p0 + deep)
            e = B.mk(f"cervical_plexus_root_{lvl}_{s}", f"Cervical plexus root, ventral ramus {lvl.upper()} ({sw})",
                     f"Ramus anterior nervi spinalis {lvl.upper()} {lat}", s, [p0, mid, deep], 2.0,
                     region="neck",
                     course=(f"ventral ramus of spinal nerve {lvl.upper()} leaves the intervertebral foramen at the vertebra's own transverse-process region and runs anterolaterally, deep to sternocleidomastoid, "
                             f"to join the cervical plexus proper. Waypoints: A = lateral extent of this page's own {S.vid(lvl)} (measured), B = midway, C = the posterior border of this page's own sternocleidomastoid_{s} "
                             "at the same height (the plexus lies deep to that muscle)."),
                     calibre="no published diameter found for the isolated cervical ventral rami; 2.0 mm = ASSUMPTION (comparable small spinal-nerve calibre, cf. the sacral S3/S4 rami of this atlas' own Q249 nerves, 1.0-3.5 mm)",
                     calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(10, 70))
            root_pt[lvl] = e.get("path") if "path" in e else None
            root_pt[lvl + "_end"] = deep
            root_pt[lvl + "_start"] = p0

        def have_end(lvl):
            return lvl + "_end" in root_pt

        # ---------------------------------------------------------------- ansa cervicalis (superior root, inferior root, loop)
        if have_end("c1") and have_end("c2") and have_end("c3"):
            y_loop = 0.5 * (root_pt["c2_end"][1] + root_pt["c3_end"][1]) - 6.0
            conf = carotid_point_at_y(S, s, y_loop)
            if conf is None:
                conf = np.array([xm + sg * 18.0, y_loop, root_pt["c2_end"][2] + 6.0])
            sup0 = root_pt["c1_end"]
            B.mk(f"ansa_cervicalis_superior_root_{s}", f"Ansa cervicalis, superior root (descendens hypoglossi) ({sw})", f"Radix superior ansae cervicalis {lat}", s,
                 [sup0, 0.5 * (sup0 + conf), conf], 1.0, region="neck",
                 course=("C1 fibres run briefly with the hypoglossal nerve (not separately shipped on this page) then leave it to descend, anterior to the internal/common carotid artery, as the superior root of the ansa. "
                         "Waypoints: C1 root's own distal end, midway, a point on this page's own common-carotid-artery centreline at the loop's height."),
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine strap-muscle motor twig)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(10, 160))
            inf0 = 0.5 * (root_pt["c2_end"] + root_pt["c3_end"])
            B.mk(f"ansa_cervicalis_inferior_root_{s}", f"Ansa cervicalis, inferior root (descendens cervicalis) ({sw})", f"Radix inferior ansae cervicalis {lat}", s,
                 [inf0, 0.5 * (inf0 + conf), conf], 1.0, region="neck",
                 course=("C2-C3 ventral rami unite and descend, anterior to the carotid sheath, to meet the superior root and close the loop. Waypoints: midpoint of the C2/C3 roots' own distal ends, midway, the same "
                         "carotid-centreline confluence point as the superior root."),
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(10, 160))
            targets = S.have(f"sternothyroid_{s}", f"sternohyoid_{s}", f"omohyoid_{s}")
            if not targets:
                B.hold(f"ansa_cervicalis_loop_{s}", "Ansa cervicalis (loop)", "none of sternothyroid/sternohyoid/omohyoid exist on this page", side=s)
            else:
                tid = targets[0]
                pt, _ = B.soft.surface_point(tid, conf + np.array([0.0, -8.0, -2.0]), margin=0.5)
                miss = sorted(set(("sternothyroid", "sternohyoid", "omohyoid")) - {t.split(f"_{s}")[0] for t in targets})
                B.mk(f"ansa_cervicalis_loop_{s}", f"Ansa cervicalis (loop) ({sw})", f"Ansa cervicalis {lat}", s, [conf, 0.5 * (conf + pt), pt], 1.0, region="neck",
                     course=(f"the completed loop gives branches to the infrahyoid 'strap' muscles (sternohyoid, sternothyroid, omohyoid; thyrohyoid is supplied directly by C1 via the hypoglossal nerve, not from the loop). "
                             f"Drawn here to the nearest available target of this page ({tid})" + (f"; this page does not ship {', '.join(miss)}, so no separate branch is drawn to those" if miss else "") + "."),
                     calibre="no published diameter found; 1.0 mm = ASSUMPTION", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(5, 60),
                     softpush=((tid, 0.3),))
        else:
            for nid, nm in (("ansa_cervicalis_superior_root", "Ansa cervicalis, superior root (descendens hypoglossi)"),
                            ("ansa_cervicalis_inferior_root", "Ansa cervicalis, inferior root (descendens cervicalis)"),
                            ("ansa_cervicalis_loop", "Ansa cervicalis (loop)")):
                B.hold(f"{nid}_{s}", nm, "C1-C3 roots not all shipped on this page", side=s)

        # ---------------------------------------------------------------- phrenic nerve: origin + PROXIMAL course only
        sa = S.find(f"scalenus_anterior_{s}")
        if have_end("c4") and sa is not None:
            origin = root_pt["c4_end"] + np.array([0.0, 2.0, -2.0])  # C4 is the major root; C3/C5 join it directly on the muscle (not drawn as separate feeder tubes, see docstring)
            av = S.E[sa]["v"]
            # proximal course: down the surface of scalenus anterior toward the muscle's OWN inferior (first-rib)
            # attachment -- a real landmark of this page, not the subclavian artery's far-lateral, pose-dependent
            # extent (an earlier version used that and produced an implausibly long reach on some pages; caught by
            # inspecting shipped lengths before shipping, same discipline Q258's own neck_lm.py documents) -- NOT
            # continued into the thorax to the diaphragm (out of scope, see module docstring: phrenic_n_terminal
            # held, not guessed).
            y_end = float(np.percentile(av[:, 1], 6.0))
            band = av[np.abs(av[:, 1] - y_end) < 10.0]
            end = (band.mean(0) if len(band) else av[np.argmin(av[:, 1])]) + np.array([0.0, 0.0, 4.0])
            mid, _ = B.soft.surface_point(sa, 0.5 * (origin + end), margin=1.0)
            e = B.mk(f"phrenic_n_{s}", f"Phrenic nerve -- origin + proximal course ({sw})", f"Nervus phrenicus {lat}", s, [origin, mid if mid is not None else 0.5 * (origin + end), end], 1.8,
                     region="neck",
                     course=("C4 is the major root contributor (C3, C5 join the trunk directly from their own cervical-plexus / brachial-plexus roots, not drawn as separate feeder tubes here); the nerve runs obliquely "
                             f"downward on the surface of scalenus anterior (this page's own {sa}) toward that muscle's own inferior (first-rib) attachment -- the real nerve "
                             "continues into the thorax to the diaphragm, which this round does NOT attempt (see module docstring: phrenic_n_terminal held, out of scope, not guessed)."),
                     calibre="no published diameter found for the cervical phrenic nerve; 1.8 mm = ASSUMPTION (small named trunk, between the ansa twigs 1.0 mm and the C1-C4 roots 2.0 mm)", calibre_kind="assumption",
                     source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(20, 220), softpush=((sa, 0.3),))
        else:
            B.hold(f"phrenic_n_{s}", "Phrenic nerve -- origin + proximal course", "C4 root or scalenus anterior not available on this page", side=s)

        # ---------------------------------------------------------------- muscular branches to the scalenes (indicative: scalenus anterior)
        if have_end("c3") and sa is not None:
            c3_start = root_pt["c3_start"]
            pt, _ = B.soft.surface_point(sa, c3_start, margin=0.8)
            B.mk(f"cervical_plexus_to_scalenes_and_prevertebrals_{s}", f"Cervical plexus muscular branches (scalenes, prevertebrals) ({sw})", f"Rami musculares (scaleni, musculi praevertebrales) {lat}", s,
                 [c3_start, pt], 1.0, region="neck",
                 course=("segmental branches direct from the cervical plexus roots (C3-C8) to scalenus anterior/medius/posterior and the prevertebral muscles (longus colli, longus capitis, rectus capitis); drawn here as "
                         "one indicative branch to this page's own scalenus anterior (the owner's named interscalene region) rather than nine near-duplicate stubs to every target muscle (see module docstring)."),
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine segmental motor twig)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(5, 120), softpush=((sa, 0.3),))
        else:
            B.hold(f"cervical_plexus_to_scalenes_and_prevertebrals_{s}", "Cervical plexus muscular branches (scalenes, prevertebrals)", "C3 root or scalenus anterior not available on this page", side=s)

        # ---------------------------------------------------------------- 4 cutaneous branches (Erb's point region, posterior border of SCM)
        scm = S.find(f"sternocleidomastoid_{s}")
        if have_end("c2") and scm is not None:
            erb_y = root_pt["c2_end"][1] - 10.0
            erb = S.scm_posterior(s, erb_y)
            scv = S.E[scm]["v"]
            top_y = float(scv[:, 1].max())
            # lesser occipital: up and back, toward the occipital scalp
            occ_target = erb + np.array([0.0, (top_y - erb_y) * 0.55, -6.0])
            occ_target = skin_target(B, S, s, (f"zan_skin_occipital_region_{s}",), occ_target)
            B.mk(f"lesser_occipital_n_{s}", f"Lesser occipital nerve ({sw})", f"Nervus occipitalis minor {lat}", s, [root_pt["c2_end"], erb, occ_target], 1.0, region="neck",
                 course="C2 (mainly), ascends along the posterior border of sternocleidomastoid (Erb's point region) to the skin of the lateral scalp posterior to the ear.",
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION (fine cutaneous branch)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT,
                 min_skin=-2.0, len_range=(10, 160))
            # great auricular: up and forward, toward the ear / parotid region
            aur_target = erb + np.array([sg * 10.0, (top_y - erb_y) * 0.65, 8.0])
            aur_target = skin_target(B, S, s, (f"zan_skin_auricular_region_{s}", f"zan_skin_parotideomasseteric_region_{s}"), aur_target)
            B.mk(f"great_auricular_n_{s}", f"Great auricular nerve ({sw})", f"Nervus auricularis magnus {lat}", s, [root_pt["c2_end"], erb, aur_target], 1.2, region="neck",
                 course="C2-C3, the largest ascending branch; crosses sternocleidomastoid obliquely to the skin over the parotid gland and the ear.",
                 calibre="no published diameter found; 1.2 mm = ASSUMPTION (the largest of the four cutaneous branches, between 1.0 and the transverse-cervical/supraclavicular 1.0-1.3 mm)", calibre_kind="assumption",
                 source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, min_skin=-2.0, len_range=(10, 160))
            # transverse cervical: forward, across SCM, to the anterior neck
            tc_target = erb + np.array([sg * 20.0, -8.0, 14.0])
            tc_target = skin_target(B, S, s, (f"zan_skin_lateral_region_of_neck_{s}",), tc_target)
            B.mk(f"transverse_cervical_n_{s}", f"Transverse cervical nerve ({sw})", f"Nervus transversus colli {lat}", s, [root_pt["c2_end"], erb, tc_target], 1.0, region="neck",
                 course="C2-C3, crosses sternocleidomastoid transversely (hence the name) to the skin of the anterior neck.",
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, min_skin=-2.0,
                 len_range=(10, 160))
        else:
            for nid, nm in (("lesser_occipital_n", "Lesser occipital nerve"), ("great_auricular_n", "Great auricular nerve"), ("transverse_cervical_n", "Transverse cervical nerve")):
                B.hold(f"{nid}_{s}", nm, "C2 root or sternocleidomastoid not available on this page", side=s)

        if have_end("c3") and have_end("c4"):
            sc0 = 0.5 * (root_pt["c3_end"] + root_pt["c4_end"])
            clav = S.find(f"clavicle_{s}")
            if clav is not None:
                cv = S.E[clav]["v"]
                relx = (cv[:, 0] - xm) * sg
                band = cv[relx <= np.percentile(relx, 45)]
                sc_target = band.mean(0) + np.array([0.0, 8.0, 6.0])
            else:
                sc_target = sc0 + np.array([0.0, -40.0, 0.0])
            sc_target = skin_target(B, S, s, (f"zan_skin_greater_supraclavicular_fossa_{s}", f"zan_skin_lesser_supraclavicular_fossa_{s}"), sc_target)
            B.mk(f"supraclavicular_n_{s}", f"Supraclavicular nerves ({sw})", f"Nervi supraclaviculares {lat}", s, [sc0, 0.5 * (sc0 + sc_target), sc_target], 1.0, region="neck",
                 course="C3-C4, descend across the posterior triangle and over the clavicle to the skin of the shoulder and upper chest.",
                 calibre="no published diameter found; 1.0 mm = ASSUMPTION", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, min_skin=-2.0,
                 len_range=(10, 190))
        else:
            B.hold(f"supraclavicular_n_{s}", "Supraclavicular nerves", "C3/C4 roots not available on this page", side=s)

        # phrenic_n_terminal: intentionally not attempted this round (see module docstring)
        B.hold(f"phrenic_n_terminal_{s}", "Phrenic n. terminal branches", "out of this round's scope (phrenic nerve scoped to origin + proximal course only, per the brief); would need a thoracic course to the diaphragm this round did not verify", side=s)

    return B.out, S.notes
