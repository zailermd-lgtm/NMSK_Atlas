"""Q261: pelvic floor's LAST Q247-audited absent row -- the perineal branch of the posterior femoral cutaneous nerve
(`data/derived/Q247_nerve_coverage.md`: 'Pelvic floor | Perineal branch of posterior femoral cutaneous n. | - '),
re-verified directly this round (not trusted from the stale Q247 table): the parent trunk `posterior_femoral_cutaneous_n`
already ships on 11 of 12 page/side combinations (own_m right side absent -- checked directly, held with that
reason) and its own Q249 build (scripts/anatomy/q249/rule_nerves.py) already documents, in its own course text,
that the real nerve 'gives the inferior cluneal and the perineal branches; these are not drawn' -- this module
draws the perineal half of that acknowledged gap (the inferior cluneal branches target a different, lower-tier
skin region and are not attempted here).

New registry node added this round, `posterior_femoral_cutaneous_n_perineal_branch` (data/nerves/lumbosacral_plexus.json,
parent posterior_femoral_cutaneous_n, SAME citation already on its parent and every other node of that file -- not
a new source).

Method: the SAME generic `muscular_branch()` helper Q260's rule_limb_fill.py already built for a cutaneous branch
(skin=True path: origin = the parent nerve's own real centreline point nearest its own distal end, since this
project's own pages have no separate named perineal skin patch to query a more proximal point against; end = the
nearest real perineal-region structure's own surface) -- reused directly, not reimplemented. Real perineal-region
targets checked directly per page before building (not assumed): `zan_skin_perineal_closure` (Z female pages),
`perineal_body` (both female pages + base_f/comb_f), `deep_perineal_muscle_cvh` / `superficial_transverse_perineal_cvh`
(the CVH perineal layer Q235/Q250 already added), `transverse_perineal_ligament` (present on every male page as the
best-available perineal-region landmark there), `deep_transverse_perineal_{l,r}` (own_m only); `skin` (the one
closed envelope on own pages) as the final fallback everywhere.
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q259"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q260"))
import rulelig as RL                     # noqa: E402
import guards as GD                      # noqa: E402
import nervelib as NL                    # noqa: E402
from rulenerve import Builder as RBuilder  # noqa: E402
from rule_limb_fill import side_centerline, find  # noqa: E402

SOURCE = "Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.6; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed. -- lumbar and sacral plexus chapters; data/nerves/lumbosacral_plexus.json (posterior_femoral_cutaneous_n_perineal_branch, new this round)."
ERR = 25.0
ERR_TEXT = ("landmark-rule allowance for a cutaneous branch's origin along its parent trunk: no publication found giving this branch's own precise arborisation fraction; origin = this nerve's own real "
            "centreline's own PROXIMAL end (highest point, nearest the ischial tuberosity/gluteal fold where the real perineal branches actually arise -- Gray's ch.6 -- unlike the tibial nerve's distal medial "
            "calcaneal branches, which this project's own rule_limb_fill.py correctly queries from the DISTAL end instead), end = the nearest real perineal-region structure's own surface.")
CAL = "no published diameter found for this individual cutaneous branch; 1.0 mm = ASSUMPTION (this atlas' own convention for comparable Q260 cutaneous branches, e.g. tibial_n_medial_calcaneal_branches)"
TARGET_CANDS = ["zan_skin_perineal_closure_{s}", "zan_skin_perineal_closure", "perineal_body", "deep_perineal_muscle_cvh",
                "superficial_transverse_perineal_cvh", "transverse_perineal_ligament", "deep_transverse_perineal_{s}", "skin"]


class _S:
    pass


def S_find_hip(E, s):
    return find(E, f"hip_bone_{s}", "hip_bone")


def build(key, root="build/q260"):
    ctx = RL.Ctx(key, root=root)
    E = ctx.E
    gd = GD.Guards(E)
    soft = NL.Soft(E, gd)
    Sx = _S(); Sx.E = E; Sx.ctx = ctx; Sx.key = key; Sx.xm = ctx.F["x_mid"]
    B = RBuilder(Sx)
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        nid = f"posterior_femoral_cutaneous_n_perineal_branch_{s}"
        name = f"Posterior femoral cutaneous n., perineal branch ({sw})"
        C = side_centerline(E, Sx.xm, "posterior_femoral_cutaneous_n", s)
        if C is None:
            B.hold(nid, name, "no posterior_femoral_cutaneous_n centreline on this page (mesh absent or degenerate)", side=s)
            continue
        # proximal end = whichever of the centreline's own two endpoints is nearer the hip bone's own real surface
        # (the ischial tuberosity/gluteal-fold region this branch actually arises near, Gray's ch.6) -- a real bone
        # landmark, not a y-coordinate heuristic: checked directly this round, a plain 'higher y = proximal' guess
        # (this project's own convention for the TRUNK/vertebral column) does NOT hold for this leg nerve on the
        # four Z pages, whose own thigh pose is abducted far enough from the torso that the nerve's y-range runs
        # from well below the pelvis to well ABOVE its iliac crest -- the pose, not a real superior course.
        hb = S_find_hip(E, s)
        if hb is not None:
            hv = E[hb]["v"]
            d0 = ((hv - C[0]) ** 2).sum(1).min() ** 0.5
            d1 = ((hv - C[-1]) ** 2).sum(1).min() ** 0.5
            q = C[0] if d0 < d1 else C[-1]
        else:
            q = C[0] if C[0][1] > C[-1][1] else C[-1]
        cands = [c.format(s=s) for c in TARGET_CANDS]
        tgt_id = find(E, *cands)
        if tgt_id is None:
            B.hold(nid, name, f"no real perineal-region mesh on this page ({cands[0]} ...)", side=s)
            continue
        pt, _ = soft.surface_point(tgt_id, q, margin=0.5, maxdist=160.0)
        if pt is None:
            B.hold(nid, name, (f"{tgt_id} is farther than 160 mm from even this nerve's own hip-bone-nearest end on this page -- on this page's own leg pose, the thigh is abducted far enough from the torso that "
                                "a straight spline across that gap would not represent a real course (checked directly: the gap itself is pose-inflated, not a real anatomical distance)"), side=s)
            continue
        if ((q - pt) ** 2).sum() ** 0.5 < 2.0:
            B.hold(nid, name, f"the nerve's own proximal end and the {tgt_id} surface are within 2 mm of each other on this page (no real length for a separate branch)", side=s)
            continue
        mid_pt = 0.5 * (q + pt)
        B.mk(nid, name, f"Rami perineales nervi cutanei femoris posterioris {lat}", s, [q, mid_pt, pt], 1.0, region="perineum",
             course=("Leaves the posterior femoral cutaneous nerve near its own origin (below piriformis / at the inferior gluteal region) and curves around the ischial tuberosity's own surface to the perineum, "
                     f"supplying skin of the posterior scrotum/labium majus (Gray's ch.6) -- the nerve's own prior build (scripts/anatomy/q249/rule_nerves.py) already names this branch as real but undrawn; this "
                     f"module draws it, ending on {tgt_id}'s own real surface, the nearest available perineal-region landmark on this page."),
             calibre=CAL, calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(2, 185), softpush=((tgt_id, 0.3),))
    return B.out, {}


if __name__ == "__main__":
    for k in ("own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"):
        items, _ = build(k)
        ship = [i for i in items if i["status"] == "ship"]
        held = [i for i in items if i["status"] != "ship"]
        print(k, "ship", len(ship), "held", len(held))
        for h in held:
            print("   HELD", h["id"], "|", h["held"])
