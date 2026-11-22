"""Q258: the two missing brachial-plexus cords (lateral, medial) on the four Z-family pages, which already carry the
roots (merged), trunks, all six divisions and the posterior cord under their own names (Q247 audit) but not these two.

Method: GEOMETRIC CONTINUATION of the page's own already-shipped anterior-division meshes -- a cord is literally the
continuation of the relevant division(s) past the clavicle (Moore & Dalley; Drake, Vogl, Mitchell ch.7): the lateral
cord is the union of the superior and middle trunks' anterior divisions, the medial cord is the anterior division of
the inferior trunk alone. No new course is invented: each division's own centreline (scripts/anatomy/q249/lm.py's
generic `centerline()`, geodesic end-to-end) is extracted from its REAL shipped geometry, and the cord tube continues
smoothly from its distal end through the lateral border of pectoralis minor (the textbook landmark the cords are named
relative to the axillary artery at) to a soft blend with the proximal end of the already-shipped terminal nerve it
becomes (median nerve's lateral root for the lateral cord, ulnar nerve for the medial cord) -- same continuity blend
as rule_brachial_own.py uses for the own pages, same honesty: reported per cord, not a hard snap.
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
import rulelig as RL      # noqa: E402
import lm as LMK          # noqa: E402
import nervelib as NL     # noqa: E402
import guards as GD       # noqa: E402

ROOT = "build/q256"
SG = {"l": -1.0, "r": 1.0}
SOURCE = ("Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.7; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, "
          "8th ed. -- brachial plexus chapter; Terminologia Anatomica (FICAT 1998).")
NAME = {"brachial_cord_lateral": "Lateral cord", "brachial_cord_medial": "Medial cord"}


def _distal_end(ctx, xm, s, nid):
    v, f = ctx.E[nid]["v"], ctx.E[nid]["f"]
    C = LMK.centerline(v, f, 24)
    if C is None:
        C = np.array([v.mean(0), v.mean(0)])
    # the distal (axilla-ward) end is the one with the LOWER y (further from the vertebral origin, closer to the axilla)
    return C[0] if C[0, 1] < C[-1, 1] else C[-1]


def pecminor_point(E, xm, s, medial):
    pm = E[f"pectoralis_minor_{s}"]["v"]
    relx = (pm[:, 0] - xm) * SG[s]
    thr = np.percentile(relx, 25 if medial else 85)
    sel = pm[relx <= thr] if medial else pm[relx >= thr]
    return sel.mean(0)


def nerve_anchor(E, nid, s):
    full = f"{nid}_{s}"
    if full not in E:
        return None, full
    v = E[full]["v"]
    return v[np.argmax(v[:, 1])], full


def build(key):
    ctx = RL.Ctx(key, root=ROOT)
    E = ctx.E; xm = ctx.F["x_mid"]
    gd = GD.Guards(E)
    out = []
    for s in ("l", "r"):
        sup = _distal_end(ctx, xm, s, f"brachial_div_superior_ant_{s}")
        mid = _distal_end(ctx, xm, s, f"brachial_div_middle_ant_{s}")
        inf = _distal_end(ctx, xm, s, f"brachial_div_inferior_ant_{s}")

        def cord(nid, origin, target, anchor_id, d0, d1, blend=0.4):
            anchor, full = nerve_anchor(E, anchor_id, s)
            end = target if anchor is None else (1 - blend) * target + blend * anchor
            path = NL.spline([origin, (origin + end) / 2.0, end], n=30)
            path = NL.push_out_bones(ctx, path, max(d0, d1) / 2.0, loops=10)
            V, F, c0, c1, d = NL.tube_round(path, d0, d1)
            V, pb = NL.finish_bones(ctx, V, F, c0, c1, iters=12, tol=0.3)
            rep = NL.measure_tube(ctx, gd, V, F, c0, c1, path, d, gate_soft=False, min_skin=0.0)
            rep["pushed_out_of_bone"] = pb; rep["length_mm"] = round(NL.path_len(path), 1)
            rep["continuity_target"] = dict(nerve=full, used=anchor is not None, blend_fraction=blend if anchor is not None else None)
            rec = dict(method="rule-based (continuation of this page's own shipped division meshes)",
                       course="see rule_cords_z.py docstring", error_band_mm=10.0, source=SOURCE)
            out.append(dict(id=f"{nid}_{s}", name=NAME[nid], latin=NAME[nid], side=s, V=V, F=F, d=d, status="ship", report=rep, rec=rec, cat="nerve"))

        # diameters matched to the thin, stylised mesh convention this page's own pre-existing brachial_trunk_*/
        # brachial_cord_posterior_* already use (~2-3 mm shipped vs. larger real calibre; named cords are promoted
        # to calibre level 1 regardless of mesh diameter, Q240's own convention) -- not a cited caliper figure.
        cord("brachial_cord_lateral", (sup + mid) / 2.0, pecminor_point(E, xm, s, medial=False), "median_n_lateral_root", 2.8, 2.4)
        cord("brachial_cord_medial", inf, pecminor_point(E, xm, s, medial=True), "ulnar_n", 2.6, 2.2)
    return out
