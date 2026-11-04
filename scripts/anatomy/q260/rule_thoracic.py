"""Q260: THORACIC DORSAL RAMI (medial branches), the one tractable item of the thoracic-segmental-nerve row Q247/
Q259 queued (the other two -- subcostal n.'s own long course around the abdominal wall to pyramidalis, and the
lateral/anterior cutaneous branches of each intercostal nerve -- need more landmark work than this round had left
and are queued precisely instead, see docs/OPEN_ITEMS_FOR_OWNER.md).

Method: Q249's own `rule_nerves.medial_branches()` (lumbar L1-L4 + the L5 dorsal ramus, already shipped and
Q240-calibre-clean) extended upward through the thoracic column, T1-T11 (each exits at the vertebra immediately
below, the SAME 'junction of the superior articular process and the transverse-process root' textbook landmark,
Gray's Anatomy for Students 4th ed. ch.4, 'Back') -- T12's own medial branch is already covered by the EXISTING
`lumbar_medial_branch_l1` build (L1's own medial branch exits at the L1/L2 junction, one level below; T12's own
would exit at the T12/L1 junction, which Q249's own L1 build already approximates from the L1 vertebra side, so a
separate T12 item here would double the same real location under two different registry rows -- not built, stated
plainly). Registry: `data/nerves/dorsal_rami.json`'s existing generic `dorsal_ramus_medial_branches` node (C2-L5),
the SAME citation Q249's own lumbar medial branches already use for this exact structure family -- no new registry
node needed.

Uses `lmk.py`'s generic vertebra-id resolver (q259, reused) so this works on both own pages (reversed numbering,
already documented there) and the four Z pages (natural ids) without re-deriving the mapping."""
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
from rulenerve import Builder as RBuilder  # noqa: E402
import lmk                        # noqa: E402

SG = {"l": -1.0, "r": 1.0}
SOURCE = "Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.4 'Back'; Shuang F et al. 2015 (lumbar level bifurcation distance); Terminologia Anatomica (FICAT 1998); data/nerves/dorsal_rami.json 'dorsal_ramus_medial_branches'."
ERR = 5.0
ERR_TEXT = "bifurcation distance above the transverse-process root measured 3.5 +- 1.2 mm at lumbar levels (Shuang 2015, 12 cadavers); no thoracic-specific cadaver distance found, so the same figure is carried up with a wider (5 mm) allowance; vertebral landmarks are this page's own meshes."
CAL = "no published diameter of the thoracic medial branch found; 1.0 mm = ASSUMPTION, matching Q249's own lumbar medial branches (same structure family, same atlas convention)"


class _S:
    pass


def build(key, root="build/q259"):
    S = lmk.Spine(key, root=root)
    E = S.E
    Sx = _S(); Sx.E = E; Sx.ctx = S.ctx; Sx.key = key; Sx.xm = S.xm
    B = RBuilder(Sx)
    xm = S.xm
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        for n in range(1, 12):  # T1..T11 (T12's own would duplicate the existing L1 build, see docstring)
            nid = f"thoracic_medial_branch_t{n}_{s}"
            name = f"Medial branch of the T{n} dorsal ramus ({sw})"
            below = f"t{n + 1}"
            vid = S.vid(below)
            if vid is None:
                B.hold(nid, name, f"vertebra T{n + 1} (the junction level for T{n}'s own medial branch) not found on this page", side=s)
                continue
            v = E[vid]["v"]
            side_v = v[SG[s] * (v[:, 0] - xm) > 0]
            if len(side_v) < 10:
                B.hold(nid, name, f"too few vertices on this side of {vid}", side=s)
                continue
            ytop = float(np.percentile(side_v[:, 1], 98)); hgt = float(np.percentile(side_v[:, 1], 98) - np.percentile(side_v[:, 1], 2))
            win = (np.abs(side_v[:, 0] - xm) > 10) & (np.abs(side_v[:, 0] - xm) < 26) & (side_v[:, 1] > ytop - 0.42 * hgt) & (side_v[:, 1] < ytop - 0.08 * hgt)
            if win.sum() < 5:
                B.hold(nid, name, f"no vertebral vertices in the junction window of {vid}", side=s)
                continue
            Jv = side_v[win][np.argmin(side_v[win][:, 2])]
            J = Jv + np.array([0, 0, -1.2])
            sg = SG[s]
            S0 = J + np.array([sg * 5.0, 3.5, 7.0])
            E1 = J + np.array([-sg * 7.0, -8.0, -4.0])
            e = B.mk(nid, name, f"Ramus medialis rami dorsalis nervi spinalis T{n} {lat}", s, [S0, J, E1], 1.0, region="back",
                     course=(f"the dorsal ramus of T{n} leaves the T{n}-T{n + 1} intervertebral foramen and divides about 3.5 mm above the superior border of the transverse-process root; its medial branch runs backward and "
                             f"caudally across the junction of the superior articular process and the transverse-process root of T{n + 1} ({vid}) and supplies multifidus and the facet joints above and below. Same method as "
                             "this atlas' own existing lumbar medial branches (Q249), extended up the thoracic column."),
                     calibre=CAL, calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(8, 45), min_skin=3.0,
                     extra_rep=dict(junction_vertex_on=vid))
    return B.out, {}
