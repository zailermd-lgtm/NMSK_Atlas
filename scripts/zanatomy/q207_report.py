#!/usr/bin/env python3
"""Q207 report stage: before -> after numbers of the skin state of a page (zone containment on the audit and fine measures, skin quality of the moved patches, intersections, seams, urogenital refit),
written to data/derived/Q207_report_<which>.json and build/q207/<which>_report.pkl (used by q207_pack for the card badges).
    python3 scripts/zanatomy/q207_report.py male|female"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402
from scripts.zanatomy import q207_eval as EV  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy import q207_build as B  # noqa: E402
from scripts.zanatomy import q207_uro as URO  # noqa: E402
from scripts.zanatomy.q207_inflate import OwnSkin  # noqa: E402


class FieldsSigned:
    def __init__(self, f):
        self.f = f

    def signed(self, P):
        return self.f.value(P)


def run(which, log=print):
    pg, raw = B.load_ctx(which)
    V1, seam_rep = pickle.load(open(B.state_path(which, "seams"), "rb"))
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    W = pg.wrist()
    own = OwnSkin(which)
    moved = sorted(i for i in V1 if np.linalg.norm(V1[i] - V0[i], axis=1).max() > 0.05)
    log(f"[{which}] {len(moved)} skin patches changed")
    t = time.time()
    seal = EV.sealers(which, pg)
    cf0 = FieldsSigned(B.coarse_fields(which))
    cf1 = EV.coarse_field(which, pg, V1, seal)
    log(f"   coarse fields {time.time()-t:.0f}s: envelope {cf1.vol_L:.1f} L")
    rep = {"moved_patches": {}, "zone": {}, "page": which}
    for side in "lr":
        zone = pg.zone_structs(side, W[side])
        a = EV.zone_measure(pg, V0, which, side, W[side], cf0, own, zone)
        b = EV.zone_measure(pg, V1, which, side, W[side], cf1, own, zone)
        rep["zone"][side] = {"before": a, "after": b}
        for c in ("bone", "vessel", "nerve", "joint", "bursa", "muscle"):
            if c in a["classes"]:
                log(f"   {side} {c:8s} audit >5% structures {a['classes'][c]['audit_gt5pct']} -> {b['classes'][c]['audit_gt5pct']}; fine {a['classes'][c]['fine_gt5pct']} -> {b['classes'][c]['fine_gt5pct']}; fine mean >0.5 mm {a['classes'][c]['fine_mean_gt0.5_pct']} -> {b['classes'][c]['fine_mean_gt0.5_pct']} %; worst fine {a['classes'][c]['fine_worst_mm']} -> {b['classes'][c]['fine_worst_mm']} mm")
    rv = {i: raw.v(i) for i in moved if i in raw.S}
    q = EV.skin_quality(pg, V1, V0, rv, moved, own)
    for i in moved:
        d = np.linalg.norm(V1[i] - V0[i], axis=1)
        rep["moved_patches"][i] = {"max_move_mm": round(float(d.max()), 2), "mean_move_mm": round(float(d.mean()), 2), "moved_vertices_gt0.3mm": int((d > 0.3).sum()), "vertices": len(d), **q[i]}
    # intersections of the limb / hand patches and the moved ones (before / after), new pairs and their depth
    ids = sorted(set(moved) | {i for i in pg.skin_ids if C.LIMB_SKIN_RE.search(i)})
    m0 = {i: (V0[i], pg.f(i)) for i in ids}
    m1 = {i: (V1[i], pg.f(i)) for i in ids}
    Vc0, F0, ow0, nm = G.concat(m0)
    Vc1, F1, ow1, _ = G.concat(m1)
    p0 = G.intersecting_pairs(Vc0, F0, ow0)
    p1 = G.intersecting_pairs(Vc1, F1, ow1)
    newp = G.new_pairs(p0, p1)
    rep["intersections"] = {"patches_checked": len(ids), "face_pairs_before": int(len(p0)), "face_pairs_after": int(len(p1)), "new_pairs": int(len(newp)),
                            "new_pairs_depth_p50_p95_max_mm": [round(float(x), 2) for x in np.percentile(G.pair_depth(Vc1, F1, newp), [50, 95, 100])] if len(newp) else [0, 0, 0],
                            "before_depth_p50_p95_max_mm": [round(float(x), 2) for x in np.percentile(G.pair_depth(Vc0, F0, p0), [50, 95, 100])]}
    # the Z source's own count for the same patches (context)
    mr = {i: (raw.v(i), pg.f(i)) for i in ids if i in raw.S}
    Vr, Fr, owr, nmr = G.concat(mr)
    rep["intersections"]["face_pairs_z_source"] = int(len(G.intersecting_pairs(Vr, Fr, owr)))
    log(f"   intersections: {rep['intersections']}")
    # seams: border steps and contacts, before / after (q202 machinery)
    from scripts.zanatomy import q199_elbow as E
    ids_all = sorted(i for i in pg.skin_ids if i in raw.S)
    rawd = {i: raw.v(i) for i in ids_all}
    rows = {}
    for tag, Vk in (("before", V0), ("after", V1)):
        by = {i: {"v": Vk[i], "f": pg.f(i), "cat": "skin"} for i in ids_all}
        rows[tag] = E.skin_seam_rows(by, rawd, None, ids_all)
    for i in moved:
        sb = max([r["step_mm_max"] for r in rows["before"] if i in (r["a"], r["b"])] or [0])
        sa = max([r["step_mm_max"] for r in rows["after"] if i in (r["a"], r["b"])] or [0])
        rep["moved_patches"][i]["seam_step_max_mm"] = [round(sb, 2), round(sa, 2)]
    rep["seams"] = {t: {"steps_gt_2mm": int(sum(r["step_mm_max"] > 2 for r in rr)), "steps_gt_3mm": int(sum(r["step_mm_max"] > 3 for r in rr)), "max_step_mm": round(max(r["step_mm_max"] for r in rr), 2)} for t, rr in rows.items()}
    from scripts.zanatomy import q202_contact as K
    faces = {i: pg.f(i) for i in ids_all}
    rd = {i: {"v": raw.v(i), "f": faces[i]} for i in ids_all}
    cons = K.contacts(rd, ids_all)
    ct = {}
    for tag, Vk in (("before", V0), ("after", V1)):
        by = {i: {"v": Vk[i], "f": faces[i]} for i in ids_all}
        g = K.gaps(by, ids_all, cons)
        ct[tag] = {"gt_2mm": int((g > 2).sum()), "gt_3mm": int((g > 3).sum()), "gt_5mm": int((g > 5).sum()), "max_mm": round(float(g.max()), 2)}
    rep["contacts_partner_gap"] = ct
    items0, _, _ = SM_classify(ids_all, V0, faces, rawd)
    items1, _, _ = SM_classify(ids_all, V1, faces, rawd)
    rep["contacts_true_gap"] = {"before": [{"A": x["A"][9:], "B": x["B"][9:], "partner_gap": round(x["partner_gap"], 1), "true_gap": round(x["true_gap"], 1)} for x in items0 if x["true_gap"] > 1.5],
                                "after": [{"A": x["A"][9:], "B": x["B"][9:], "partner_gap": round(x["partner_gap"], 1), "true_gap": round(x["true_gap"], 1)} for x in items1 if x["true_gap"] > 1.5],
                                "sliding_contacts_still_touching_after": int(sum(1 for x in items1 if x["true_gap"] <= 1.5))}
    log(f"   contacts partner-gap {ct}; true gap > 1.5 mm: {len(rep['contacts_true_gap']['before'])} -> {len(rep['contacts_true_gap']['after'])}")
    # urogenital
    if which == "male":
        ids = list(URO.IDS)
        vol = lambda Vk, i: round(URO.volume(Vk[i], pg.f(i)))
        u = {"volume_mm3": {i[-1]: [vol(V0, i), vol(V1, i), vol({k: raw.v(k) for k in ids}, i)] for i in ids}}
        for tag, Vk in (("before", V0), ("after", V1)):
            l, r = Vk[ids[0]], Vk[ids[1]]
            u["x_range_mm_" + tag] = {"l": [round(float(l[:, 0].min()), 1), round(float(l[:, 0].max()), 1)], "r": [round(float(r[:, 0].min()), 1), round(float(r[:, 0].max()), 1)]}
        rep["urogenital"] = u
        log(f"   urogenital {u}")
    rep["envelope_L"] = {"before": round(float(cf0.f.skin_vol_L if hasattr(cf0.f, 'skin_vol_L') else 0), 1), "after": round(float(cf1.vol_L), 1)}
    rep["seam_stage"] = {k: v for k, v in seam_rep.items() if k != "items"}
    out = REPO / "data" / "derived" / f"Q207_report_{which}.json"
    out.write_text(json.dumps(rep, indent=1, default=float))
    pickle.dump(rep, open(B.state_path(which, "report"), "wb"))
    return rep


def SM_classify(ids, V, faces, rawd):
    from scripts.zanatomy import q207_seams as SM
    return SM.classify(ids, V, faces, rawd)


if __name__ == "__main__":
    run(sys.argv[1])
