"""Q259: the THORACIC (greater/lesser/least) and LUMBAR/SACRAL SPLANCHNIC NERVES, plus the LUMBAR and SACRAL
SYMPATHETIC CHAIN segments needed as their real anchor -- all absent on every one of the six pages today (Q247:
Autonomic group, "Greater/lesser/least splanchnic nn.; lumbar + sacral splanchnic nn." = absent everywhere).

Anchor check done BEFORE writing this module (not assumed): the four Z pages already ship a real
`zan_sympathetic_trunk_{l,r}` mesh, but its own y-extent (measured directly) runs from about the C3/C4 level down to
about T12 ONLY -- it does NOT reach the lumbar or sacral region at all, despite Q247's one-line "sympathetic trunk:
Y" summary suggesting full-length coverage. So: the THORACIC splanchnic nerves (greater/lesser/least) can anchor on
that REAL mesh on the four Z pages; the LUMBAR and SACRAL sympathetic chain (and therefore the lumbar/sacral
splanchnic nerves) have no real geometry anywhere and are built fresh, by the same rule-based method, on all SIX
pages. The own pages (no sympathetic trunk mesh at all) additionally need a short rule-based THORACIC chain segment
(T5-T12) as the thoracic splanchnics' own anchor there -- built the same way, not skipped.

Targets: the lumbar/sacral splanchnic nerves end on this atlas' own ALREADY-SHIPPED (Q249) superior_hypogastric_plexus
/ inferior_hypogastric_plexus_{l,r} -- a real, cited, previously-verified mesh on every page, giving both ends of
those two nerves a genuine anchor. The thoracic splanchnics' real target (coeliac ganglion/plexus) has no shipped
mesh anywhere; on the four Z pages the real `zan_coeliac_trunk` ARTERY is used as a documented proxy (the coeliac
ganglion/plexus surrounds the coeliac trunk's origin from the aorta -- Moore, Dalley, Agur, Clinically Oriented
Anatomy, 8th ed.); on the two own pages (no coeliac trunk mesh) the `abdominal_aorta` at the T12/L1 level (the
coeliac trunk's own origin level, same source) is used instead, with a wider, honestly-stated error bound -- the
same "wider band where the page lacks the precise anchor" pattern Q258 used for the own-page inferior brachial
trunk/medial cord.

Sources: Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.4 ('Back') and ch.5 ('Abdomen'); Moore KL,
Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998); the registry file
this module fills in, data/nerves/autonomic_nervous_system.json (the 4 lumbar/sacral splanchnic nodes were ADDED to
that file by this same round, with the same citation set already used by its other 25 nodes -- not invented)."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import lmk                     # noqa: E402
from rulenerve import Builder  # noqa: E402

ROOT_DEFAULT = "build/q258"
SG = {"l": -1.0, "r": 1.0}
SOURCE = ("Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.4/ch.5; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998); "
          "data/nerves/autonomic_nervous_system.json.")
ERR = 10.0
ERR_TEXT = "landmark-rule allowance for the sympathetic chain / splanchnic nerves (no page-specific calibre study exists for these unsegmented deep autonomic structures); +-10 mm"
ERR_PROXY = 16.0
ERR_PROXY_TEXT = ("the real target (coeliac ganglion/plexus) has no shipped mesh on this page; approximated by the abdominal aorta at the coeliac trunk's own documented origin level (T12/L1) -- wider error band than "
                  "the other splanchnics, which reach an already-shipped named target")


def trunk_point_at_y(S, s, y):
    tid = f"zan_sympathetic_trunk_{s}"
    if tid not in S.E:
        return None
    C = S.centerline(tid, n=60)
    if C is None:
        return None
    j = int(np.argmin(np.abs(C[:, 1] - y)))
    return C[j]


def aorta_proxy(S, s, y_target):
    aid = S.find("abdominal_aorta")
    if aid is None:
        return None
    v = S.E[aid]["v"]
    band = v[np.abs(v[:, 1] - y_target) < 10.0]
    if not len(band):
        band = v
    pt = band.mean(0)
    return pt + np.array([SG[s] * (v[:, 0].std() * 0.6 + 2.0), 0.0, 0.0])


def coeliac_target(S, s):
    cid = S.find("zan_coeliac_trunk")
    if cid is not None:
        v = S.E[cid]["v"]
        return v.mean(0) + np.array([SG[s] * 3.0, 0.0, -1.0]), True
    t12_y = None
    vid = S.vid("t12")
    if vid is not None:
        t12_y = float(S.E[vid]["v"][:, 1].mean())
    y_t = t12_y if t12_y is not None else S.xm
    p = aorta_proxy(S, s, y_t)
    return p, False


def renal_plexus_proxy(S, s):
    """no coeliac/aorticorenal/renal-plexus mesh anywhere on any page (checked); the lesser/least splanchnic
    nerves' real targets (aorticorenal ganglion, renal plexus) are both approximated the SAME way as the greater
    splanchnic's coeliac-trunk proxy -- the abdominal aorta a little lower (L1 level, where the renal arteries
    arise in reality), a slightly cruder stand-in than greater splanchnic's real zan_coeliac_trunk anchor on Z
    pages, stated honestly rather than invented as a separate structure."""
    vid = S.vid("l1")
    y_t = float(S.E[vid]["v"][:, 1].mean()) if vid is not None else S.xm
    return aorta_proxy(S, s, y_t), False


def build(key, root=ROOT_DEFAULT):
    S = lmk.Spine(key, root=root)
    B = Builder(S)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"

        # ---------------------------------------------------------------- thoracic chain anchor points (real trunk on Z; built fresh on own)
        def thoracic_anchor(level):
            if S.z:
                vid = S.vid(level)
                y = float(S.E[vid]["v"][:, 1].mean()) if vid is not None else None
                return None if y is None else trunk_point_at_y(S, s, y)
            return S.anterolateral(level, s)

        t5, t9, t10, t11, t12 = (thoracic_anchor(l) for l in ("t5", "t9", "t10", "t11", "t12"))
        if not S.z and all(p is not None for p in (t5, t9, t10, t11, t12)):
            B.mk(f"thoracic_sympathetic_chain_{s}", f"Thoracic sympathetic chain, T5-T12 segment ({sw})", f"Pars thoracica trunci sympathici {lat}", s,
                 [t5, thoracic_anchor("t7"), t9, t10, t11, t12], 1.6, region="thorax",
                 course=("the sympathetic trunk's thoracic segment lies against the heads of the ribs / anterolateral vertebral bodies, T5-T12; built here only as the real anchor the greater/lesser/least splanchnic "
                         "nerves below need on this page (which ships no sympathetic trunk mesh at all, unlike the four Z pages, which carry a real one for this exact span -- so this segment is NOT built on those)."),
                 calibre="no page-specific calibre; 1.6 mm = MODELLING CHOICE matched to the thin, stylised calibre the Z pages' own real zan_sympathetic_trunk ships at (~0.3-0.7 mm shipped there; this atlas' thin-trunk "
                         "convention for named autonomic trunks, Q240)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(60, 260))
        elif not S.z:
            B.hold(f"thoracic_sympathetic_chain_{s}", "Thoracic sympathetic chain, T5-T12 segment", "T5/T9/T10/T11/T12 vertebra meshes not all available on this page", side=s)

        # ---------------------------------------------------------------- greater / lesser / least thoracic splanchnic nn.
        if t5 is not None and t9 is not None:
            tgt, real = coeliac_target(S, s)
            origin = 0.5 * (t5 + t9)
            if tgt is not None:
                B.mk(f"greater_splanchnic_n_{s}", f"Greater splanchnic nerve ({sw})", f"Nervus splanchnicus major {lat}", s, [origin, (thoracic_anchor("t7") if thoracic_anchor("t7") is not None else 0.5 * (origin + tgt)), tgt], 2.0, region="thorax",
                     course=("preganglionic fibres from the T5-T9 thoracic sympathetic ganglia converge, pierce the diaphragmatic crus and descend to the coeliac ganglion/plexus. Origin: this page's own thoracic "
                             f"sympathetic chain at the T5-T9 level ({'the real zan_sympathetic_trunk mesh' if S.z else 'the T5-T12 chain segment built above'}). "
                             + ("Target: this page's own real zan_coeliac_trunk artery (the coeliac ganglion/plexus surrounds its origin from the aorta)." if real else
                                "Target: this page ships no coeliac trunk mesh; approximated by the abdominal aorta at the coeliac trunk's own documented origin level (T12/L1) -- see module docstring.")),
                     calibre="no published diameter found for the greater splanchnic nerve; 2.0 mm = ASSUMPTION (named autonomic trunk, thin stylised convention)", calibre_kind="assumption", source=SOURCE,
                     err_mm=ERR if real else ERR_PROXY, err_text=ERR_TEXT if real else ERR_PROXY_TEXT, len_range=(40, 380), side_margin=-40.0)
            else:
                B.hold(f"greater_splanchnic_n_{s}", "Greater splanchnic nerve", "no coeliac trunk or abdominal aorta mesh on this page to anchor the target", side=s)
        else:
            B.hold(f"greater_splanchnic_n_{s}", "Greater splanchnic nerve", "T5/T9 anchor not available on this page", side=s)

        if t10 is not None and t11 is not None:
            tgt, _ = renal_plexus_proxy(S, s)
            origin = 0.5 * (t10 + t11)
            if tgt is not None:
                B.mk(f"lesser_splanchnic_n_{s}", f"Lesser splanchnic nerve ({sw})", f"Nervus splanchnicus minor {lat}", s, [origin, 0.5 * (origin + tgt), tgt], 1.4, region="thorax",
                     course=(f"preganglionic fibres from the T10-T11 thoracic sympathetic ganglia descend to the aorticorenal ganglion. Origin: this page's own thoracic sympathetic chain at the T10-T11 level "
                             f"({'the real zan_sympathetic_trunk mesh' if S.z else 'the T5-T12 chain segment built above'}). Target: no aorticorenal ganglion mesh exists on this page; approximated by the abdominal "
                             "aorta near the L1 level (where the renal arteries arise in reality) -- see module docstring."),
                     calibre="no published diameter found; 1.4 mm = ASSUMPTION (smaller than the greater splanchnic)", calibre_kind="assumption", source=SOURCE, err_mm=ERR_PROXY, err_text=ERR_PROXY_TEXT,
                     len_range=(30, 320), side_margin=-40.0)
            else:
                B.hold(f"lesser_splanchnic_n_{s}", "Lesser splanchnic nerve", "no abdominal aorta mesh on this page to anchor the target", side=s)
        else:
            B.hold(f"lesser_splanchnic_n_{s}", "Lesser splanchnic nerve", "T10/T11 anchor not available on this page", side=s)

        if t12 is not None:
            tgt, _ = renal_plexus_proxy(S, s)
            if tgt is not None:
                B.mk(f"least_splanchnic_n_{s}", f"Least (lowest) splanchnic nerve ({sw})", f"Nervus splanchnicus imus {lat}", s, [t12, 0.5 * (t12 + tgt), tgt], 1.1, region="thorax",
                     course=(f"preganglionic fibres from the T12 ganglion descend to the renal plexus (present in roughly half of people; when absent its fibres travel with the lesser splanchnic nerve). Origin: this "
                             f"page's own thoracic sympathetic chain at T12 ({'the real zan_sympathetic_trunk mesh' if S.z else 'the T5-T12 chain segment built above'}). Target: approximated by the abdominal aorta "
                             "near the L1 level -- see module docstring."),
                     calibre="no published diameter found; 1.1 mm = ASSUMPTION (the smallest of the three)", calibre_kind="assumption", source=SOURCE, err_mm=ERR_PROXY, err_text=ERR_PROXY_TEXT, len_range=(20, 280), side_margin=-40.0)
            else:
                B.hold(f"least_splanchnic_n_{s}", "Least (lowest) splanchnic nerve", "no abdominal aorta mesh on this page to anchor the target", side=s)
        else:
            B.hold(f"least_splanchnic_n_{s}", "Least (lowest) splanchnic nerve", "T12 anchor not available on this page", side=s)

        # ---------------------------------------------------------------- lumbar sympathetic chain + lumbar splanchnic n.
        l_pts = [S.body_lateral(f"l{k}", s) for k in (1, 2, 3, 4)]
        if all(p is not None for p in l_pts):
            s1m = S.sacral_point(1, s, lateral_mm=8.0)
            anchors = l_pts + ([s1m] if s1m is not None else [])
            B.mk(f"lumbar_sympathetic_chain_{s}", f"Lumbar sympathetic chain, L1-L4 ({sw})", f"Pars lumbalis trunci sympathici {lat}", s, anchors, 1.4, region="abdomen",
                 course=("the sympathetic trunk's lumbar segment runs along the anterolateral margin of the lumbar vertebral bodies, medial to psoas major, continuing from the thoracic segment above and into the "
                         "sacral segment below. Waypoints: lateral-body points of this page's own L1-L4 vertebrae, continuing to the S1 landmark used by the sacral segment."),
                 calibre="no page-specific calibre; 1.4 mm = MODELLING CHOICE (thin stylised autonomic-trunk convention, see thoracic segment)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT,
                 len_range=(60, 220))
            lsp_origin = 0.5 * (l_pts[1] + l_pts[2])
            shp = S.find("superior_hypogastric_plexus")
            if shp is not None:
                tgt, _ = B.soft.surface_point(shp, lsp_origin, margin=1.5)
                B.mk(f"lumbar_splanchnic_n_{s}", f"Lumbar splanchnic nerves ({sw})", f"Nervi splanchnici lumbales {lat}", s, [lsp_origin, 0.5 * (lsp_origin + tgt), tgt], 1.3, region="abdomen",
                     course=("preganglionic and postganglionic fibres from the L1-L4 lumbar sympathetic ganglia run medially to join the intermesenteric (aortic) plexus and the superior hypogastric plexus -- the "
                             "abdominal continuation of the thoracic splanchnic pathway. Origin: this page's own lumbar sympathetic chain (L2-L3 level, built above). Target: this atlas' own already-shipped (Q249) "
                             f"superior_hypogastric_plexus."),
                     calibre="no published diameter found; 1.3 mm = ASSUMPTION", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(15, 160), softpush=((shp, 0.3),))
            else:
                B.hold(f"lumbar_splanchnic_n_{s}", "Lumbar splanchnic nerves", "superior_hypogastric_plexus not shipped on this page", side=s)
        else:
            B.hold(f"lumbar_sympathetic_chain_{s}", "Lumbar sympathetic chain, L1-L4", "not all of L1-L4 vertebra meshes available on this page", side=s)
            B.hold(f"lumbar_splanchnic_n_{s}", "Lumbar splanchnic nerves", "lumbar sympathetic chain not built on this page", side=s)

        # ---------------------------------------------------------------- sacral sympathetic chain + sacral splanchnic n.
        s_pts = [S.sacral_point(k, s, lateral_mm=8.0) for k in (1, 2, 3, 4)]
        if all(p is not None for p in s_pts):
            B.mk(f"sacral_sympathetic_chain_{s}", f"Sacral sympathetic chain, S1-S4 ({sw})", f"Pars sacralis trunci sympathici {lat}", s, s_pts, 1.2, region="pelvis",
                 course=("the sympathetic trunk's sacral segment lies on the pelvic surface of the sacrum, medial to the anterior sacral foramina, continuing the lumbar segment above and converging on the ganglion "
                         "impar at the coccyx (not drawn: this round's registry has no ganglion-impar waypoint rule). Waypoints: this page's own S1-S4 sacral-foramen landmarks (data/nerves registry: ganglion impar's "
                         "own parent chain), shifted 8 mm medial to the foramen itself (the chain, unlike the S1-S4 ventral rami, lies medial to the foramina)."),
                 calibre="no page-specific calibre; 1.2 mm = MODELLING CHOICE (thin stylised autonomic-trunk convention)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(30, 140))
            ssp_origin = 0.5 * (s_pts[1] + s_pts[2])
            ihp = S.find(f"inferior_hypogastric_plexus_{s}")
            if ihp is not None:
                tgt, _ = B.soft.surface_point(ihp, ssp_origin, margin=1.0)
                B.mk(f"sacral_splanchnic_n_{s}", f"Sacral splanchnic nerves ({sw})", f"Nervi splanchnici sacrales {lat}", s, [ssp_origin, 0.5 * (ssp_origin + tgt), tgt], 1.1, region="pelvis",
                     course=("postganglionic sympathetic fibres from the sacral sympathetic ganglia run medially to join the inferior hypogastric (pelvic) plexus -- the sympathetic counterpart of the parasympathetic "
                             "pelvic splanchnic nerves (S2-S4) this atlas already ships (Q249), joining the same plexus from the opposite side. Origin: this page's own sacral sympathetic chain (S2-S3 level, built "
                             f"above). Target: this atlas' own already-shipped inferior_hypogastric_plexus_{s}."),
                     calibre="no published diameter found; 1.1 mm = ASSUMPTION", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(10, 120), softpush=((ihp, 0.3),))
            else:
                B.hold(f"sacral_splanchnic_n_{s}", "Sacral splanchnic nerves", f"inferior_hypogastric_plexus_{s} not shipped on this page", side=s)
        else:
            B.hold(f"sacral_sympathetic_chain_{s}", "Sacral sympathetic chain, S1-S4", "sacral foramen landmarks not available on this page", side=s)
            B.hold(f"sacral_splanchnic_n_{s}", "Sacral splanchnic nerves", "sacral sympathetic chain not built on this page", side=s)

    return B.out, S.notes
