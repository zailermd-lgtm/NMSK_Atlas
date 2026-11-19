"""Q307 Part B fix: carry the UPPER-LIMB nerves from each Combined page onto the Imaging page of the SAME body,
and repair the three lower-limb nerves Q304 left half-done.

Why this module exists, in one line each:

  * The owner reported the LATERAL ANTEBRACHIAL CUTANEOUS NERVE as "not in place". Q307's audit found it is in
    the right compartment on the four Z pages but **absent from both Imaging pages**, and not alone: each
    Imaging page lacks 96 nerves its own Combined page carries, 33 of them upper-limb.
  * Q304's selector reads `and x["id"] not in oS` -- it skipped any id the Imaging page already carried. Where
    the page happened to hold the LEFT sided id, the transfer added only the RIGHT one, and the page was left
    carrying a full-length nerve on one side and a 29-40 mm stub on the other UNDER THE SAME DISPLAY NAME:
    Imaging M's right tibial nerve is a 40 mm popliteal stub while its left is the full 524 mm nerve, and the
    right medial and lateral plantar nerves hang 436.6 mm from their own parent. Imaging F has it on the left,
    for both the tibial (37 mm vs 451 mm, plantar nerves 370.4 mm adrift) and the femoral nerve (29 mm vs 500 mm).

What may be replaced, and what may NEVER be: only a mesh whose own source is `mirror_q237` -- a MIRROR of the
other side's traced segment, so nothing measured on that side's own imaging is lost. A structure traced on this
body's own imaging (`ct_vh?_popliteal`, `ct_vhf_femoral`) is never touched; it keeps its geometry and its
"measured on this body" badge and only its CARD is corrected to say which segment it actually is.

Everything else is Q304's, deliberately: the identity + thin-plate-spline correction field of `reg304.py` (and
NOT a nearest-point ICP, which xfer304 recorded sliding a nerve 22.7 mm along a leg), Q299's validated body mask
and per-bone masks as the two guards, and Q299's mesh guard refusing any move that flips > 3 % of the triangles
or shifts the mean dihedral by more than 8 deg.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
for p in ("q241", "q237", "q299", "q304", "q307"):
    sys.path.insert(0, str(REPO / "scripts" / "anatomy" / p))
import model as MD            # noqa: E402
import reg304 as R            # noqa: E402
import contain299 as CT       # noqa: E402
import fix_contain299 as FX   # noqa: E402
import xfer304 as X4          # noqa: E402

PAIR = {"own_m": "comb_m", "own_f": "comb_f"}
OUT = Path("/dev/shm/q307/nerves")
REPORT = REPO / "data/derived/Q307_nerve_transfer.json"

# Which nerves this round carries: the upper limb and the shoulder girdle. Written as the complement of Q304's
# lower-limb set rather than as a hand-made list, so no nerve can be silently left out: a candidate qualifies if
# its own id names an upper-limb / girdle structure.
UPPER_N = re.compile(
    r"brachial|antebrachial|(?<![a-z])axillary_n|median_n|ulnar_n|radial_n|musculocutaneous|interosseous_nerve_of_forearm|"
    r"interosseous_n|thoracic_n|scapular|pectoral_n|subclavian_nerve|subscapular|palmar|dorsal_digital|"
    r"dorsal_branch_of_ulnar|supraclavicular|thoracodorsal|subclavius|lumbrical|thenar|digital_branches")
# `axillary_n` is written with a look-behind because without it the pattern matched **maxillary_nerve** -- the
# first run carried the maxillary nerve of both sides onto both Imaging pages, across a skull correspondence
# this round does not even build, and it landed 32-39 % inside bone against 2.6 % on the Combined page.

# After the bone guard has run, a structure that has GAINED this much in-bone volume over what it already had on
# the Combined page is refused outright. Q304 set the rule this enforces: a Z mesh that is inside a bone on the
# SOURCE page is the source's geometry, reported and not re-routed, but "what this round may not do is add
# penetration of its own". Q299's push-out guard reduces these (0.78 -> 0.69, 1.00 -> 0.90) and cannot clear
# them, because they are hand nerves crossing the worst-corresponded bones on the page.
GATE_BONE_GAIN = 0.25

# The Imaging pages merge the carpus, the metacarpus, the hand phalanges and the ribs into single labels and
# number the spine by STRUCTURE INDEX, not by level (Q304's own finding: a per-level alias gave 55-268 mm
# medians before it was caught). So every correspondence below is a GROUP: "merge these on the Combined page"
# against "merge these on the Imaging page", and the two Imaging pages do not even agree with each other
# (Imaging M merges the metacarpals into `metacarpals_l`, Imaging F keeps `mc_1_l`..`mc_5_l`), so both spellings
# are accepted on the destination side.
UPPER_GROUPS = {
    "humerus_l": (r"^humerus_l$", r"^humerus_l$"), "humerus_r": (r"^humerus_r$", r"^humerus_r$"),
    "radius_l": (r"^radius_l$", r"^radius_l$"), "radius_r": (r"^radius_r$", r"^radius_r$"),
    "ulna_l": (r"^ulna_l$", r"^ulna_l$"), "ulna_r": (r"^ulna_r$", r"^ulna_r$"),
    "scapula_l": (r"^scapula_l$", r"^scapula_l$"), "scapula_r": (r"^scapula_r$", r"^scapula_r$"),
    "clavicle_l": (r"^clavicle_l$", r"^clavicle_l$"), "clavicle_r": (r"^clavicle_r$", r"^clavicle_r$"),
    "sternum": (r"^sternum$", r"^sternum$"),
    "carpals_l": (r"^carpal_\w+_l$", r"^carpals_l$"), "carpals_r": (r"^carpal_\w+_r$", r"^carpals_r$"),
    "metacarpals_l": (r"^mc_\d_l$", r"^(metacarpals_l|mc_\d_l)$"),
    "metacarpals_r": (r"^mc_\d_r$", r"^(metacarpals_r|mc_\d_r)$"),
    "phalanges_hand_l": (r"^ph_hand_\d+_\w+_l$", r"^phalanges_hand_l$"),
    "phalanges_hand_r": (r"^ph_hand_\d+_\w+_r$", r"^phalanges_hand_r$"),
    "ribs_l": (r"^rib_\d+_l$", r"^(ribs_l|rib_\d+_l)$"),
    "ribs_r": (r"^rib_\d+_r$", r"^(ribs_r|rib_\d+_r)$"),
    "cervical_spine": (r"^vert_c[1-7]$", r"^cervical_vertebrae#[1-7]$"),
    "thoracic_spine": (r"^vert_t([1-9]|1[0-2])$", r"^thoracic_vertebrae#([1-9]|1[0-2])$"),
}

# The three half-done lower-limb nerves, and the ONLY source a mesh may have for this round to replace it.
REPLACEABLE_SRC = "mirror_q237"

# the per-structure registration gate (see the comment at its use site in build())
GATE_P95_MM = 20.0
GATE_MED_MM = 4.0


def axis_len(v):
    c = v.mean(0)
    u = np.linalg.svd(v - c, full_matrices=False)[2][0]
    t = (v - c) @ u
    return float(t.max() - t.min())


def fit_with(key, groups, verbose=True):
    """xfer304.fit with a chosen bone-group table in force, so the field's control points sit where the nerves
    being carried actually are. Restores the table afterwards: Q304's own build must keep working.

    One field per region, NOT one field for the page. The first version of this module fitted the UPPER-limb
    field once and used it for the lower-limb stub repair too, which is extrapolation: Imaging M's right tibial
    nerve then landed 53.5 mm from its own plantar nerves and Imaging F's left 89.8 mm, against 0.0 mm on the
    sides Q304 had already done with its own lower-limb field. Caught by val307, not by a crash."""
    old = X4.GROUPS
    try:
        X4.GROUPS = groups
        return X4.fit(key, verbose=verbose)
    finally:
        X4.GROUPS = old


def candidates(own, comb, mode):
    """-> list of Combined-page structures to carry, plus the id each one lands on."""
    oS = {x["id"]: x for x in own.S}
    cS = {x["id"]: x for x in comb.S}
    out = []
    if mode == "upper":
        for x in comb.S:
            if x["sys"] != "nerve":
                continue
            b = re.sub(r"^zan_", "", x["id"])
            if not UPPER_N.search(b) or X4.LOWER_N.search(b):
                continue
            if x["id"] in oS:
                continue
            out.append((x, x["id"], "added: the Imaging page carried no mesh under this id"))
    else:   # the half-done lower-limb sides
        for x in comb.S:
            if x["sys"] != "nerve" or x["id"] not in oS:
                continue
            tgt = oS[x["id"]]
            if (tgt.get("src") or "") != REPLACEABLE_SRC:
                continue
            if not X4.LOWER_N.search(re.sub(r"^zan_", "", x["id"])):
                continue
            lo = axis_len(np.asarray(tgt["v"], float)); hi = axis_len(np.asarray(x["v"], float))
            if lo >= 0.5 * hi:
                continue
            out.append((x, x["id"],
                        f"replaced: the page's own mesh was a {lo:.1f} mm {REPLACEABLE_SRC} stub against this "
                        f"nerve's {hi:.1f} mm on the Combined page of the same body"))
    return out


def build(keys, out_root, modes=("upper", "lower_fix")):
    out_root = Path(out_root); out_root.mkdir(parents=True, exist_ok=True)
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    for key in keys:
        own = MD.Model(key); comb = MD.Model(PAIR[key])
        FIELD, st, breport, A = {}, {}, {}, {}
        for mo in modes:
            g = UPPER_GROUPS if mo == "upper" else X4.GROUPS
            _o, _c, reg, pg, a = fit_with(key, g)
            FIELD[mo] = reg; st[mo] = reg.stats(); breport[mo] = X4.bone_report(a); A[mo] = a
            print(key, mo, "registration", st[mo], flush=True)
            del _o, _c
        own_canon = {}
        for x in own.S:
            own_canon.setdefault(X4.canon(x["id"]), []).append(x["id"])
        cands = []
        for mo in modes:
            cands += [(x, t, w, mo) for x, t, w in candidates(own, comb, mo)]
        print(key, "candidates:", len(cands), flush=True)
        rng = np.random.default_rng(11)
        print(key, "building the Q299 body mask of the Combined page ...", flush=True)
        BC = CT.build(PAIR[key], 2.0)
        comb_bone_frac = {x["id"]: round(X4.in_bone_frac(np.asarray(x["v"], float), np.asarray(x["f"], np.int64), BC["bones"], np.random.default_rng(11)), 4)
                          for x, _, _, _ in cands}
        del BC
        print(key, "building the Q299 body mask of the Imaging page ...", flush=True)
        BM = CT.build(key, 2.0)
        mval = CT.validate(BM)
        assert mval["ok"], f"{key}: the Q299 body mask does not validate: {mval['reasons']}"
        own_nerve_pts = np.vstack([x["v"] for x in own.S if x["sys"] == "nerve"])
        own_tree = cKDTree(own_nerve_pts)
        items, arrays, refused = {}, {}, {}
        for x, tgt_id, why, mo in sorted(cands, key=lambda t: t[1]):
            reg = FIELD[mo]
            V0 = np.asarray(x["v"], float); F = np.asarray(x["f"], np.int64)
            V = reg(V0)
            loc = reg.local(V0, 40.0)
            # The gate, and the reason it exists. The upper limb does NOT correspond as well as the lower limb
            # did: `xfer307.py probe` measures per-group medians of 0.14-10.29 mm against Q304's lower-limb
            # 0.79-2.79, with Imaging M's right metacarpals at median 10.29 / p95 54.87 / max 63.86 mm and its
            # hand phalanges at p95 46-58 mm (Q293's own finding -- his hand bones were seated apart -- and
            # Q304's, that his legs were scanned in different positions). Carrying a hand nerve across that
            # correspondence would land it centimetres away, so every candidate is gated on the residual of the
            # bone correspondences within 40 mm of its OWN vertices, and every refusal is named with its numbers
            # instead of being averaged away.
            if loc["p95_mm"] > GATE_P95_MM or loc["median_mm"] > GATE_MED_MM:
                refused[tgt_id] = dict(id=tgt_id, name=(x.get("rec") or {}).get("name") or x["id"],
                                       side=x["side"], why=why, region=mo, local_resid=loc,
                                       refused_because=f"local bone residual median {loc['median_mm']:.2f} / "
                                                       f"p95 {loc['p95_mm']:.2f} mm exceeds the gate "
                                                       f"(median <= {GATE_MED_MM}, p95 <= {GATE_P95_MM})")
                continue
            guards = {}
            if not BM["g"].inside(BM["body"], V).all():
                V1, gs = FX.pull_inside(V, F, BM["g"], BM["body"], BM["skin_tree"], BM["bones"], BM["bone_tree"])
                ok, mg = X4.mesh_guard(V, V1, F)
                guards["skin_pull"] = dict(applied=bool(ok), **gs, **mg)
                if ok:
                    V = V1
            fb_now = X4.in_bone_frac(V, F, BM["bones"], rng)
            fb_comb = comb_bone_frac.get(x["id"])
            if fb_comb is not None and fb_now > fb_comb + 0.10 and fb_now > 0.05:
                V1 = X4.push_out_of_bone(V, F, BM["bones"], BM["bone_tree"])
                ok, mg = X4.mesh_guard(V, V1, F)
                after = X4.in_bone_frac(V1, F, BM["bones"], rng) if ok else fb_now
                guards["bone_push"] = dict(applied=bool(ok), in_bone_frac_combined=round(fb_comb, 4),
                                           in_bone_frac_before=round(fb_now, 4),
                                           in_bone_frac_after=round(after, 4), **mg)
                if ok:
                    V = V1; fb_now = after
            if fb_comb is not None and fb_now > fb_comb + GATE_BONE_GAIN:
                refused[tgt_id] = dict(id=tgt_id, name=(x.get("rec") or {}).get("name") or x["id"],
                                       side=x["side"], why=why, region=mo, local_resid=loc,
                                       refused_because=f"after Q299's bone guard it is still {fb_now:.1%} inside "
                                                       f"bone against {fb_comb:.1%} on the Combined page, a gain "
                                                       f"of more than {GATE_BONE_GAIN:.0%}: this round may not add "
                                                       f"bone penetration of its own")
                continue
            try:
                vol = float(trimesh.Trimesh(V, F, process=False).volume) / 1000.0
                vol0 = float(trimesh.Trimesh(V0, F, process=False).volume) / 1000.0
            except Exception:
                vol = vol0 = float("nan")
            items[tgt_id] = dict(
                id=tgt_id, src_id=x["id"], why=why, region=mo,
                name=(x.get("rec") or {}).get("name") or x.get("name") or x["id"],
                side=x["side"], canon=X4.canon(x["id"]), nv=int(len(V)), tris=int(len(F)),
                cm3=round(vol, 4), cm3_combined=round(vol0, 4),
                dihedral_mean_deg=round(X4.dihedral_mean(V, F), 1),
                moved_median_mm=round(float(np.median(np.linalg.norm(V - V0, axis=1))), 2),
                moved_max_mm=round(float(np.linalg.norm(V - V0, axis=1).max()), 2),
                axis_len_mm=round(axis_len(V), 1),
                local_resid=loc, bbox_mm=np.round(V.max(0) - V.min(0), 1).tolist(),
                y_range=[round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)],
                already_on_page_same_nerve=own_canon.get(X4.canon(x["id"]), []),
                nearest_own_nerve_mm=round(float(own_tree.query(V, workers=-1)[0].min()), 2),
                in_bone_frac=round(fb_now, 4),
                in_bone_frac_combined=(round(fb_comb, 4) if fb_comb is not None else None),
                guards=guards, rec_combined=x.get("rec") or {})
            arrays[tgt_id + "__v"] = V.astype(np.float32)
            arrays[tgt_id + "__f"] = F.astype(np.int32)
        # BOTH SIDES OR NEITHER. A round called in to fix a nerve that exists on one side only must not create
        # another one: if the gate passes one side of a nerve and refuses the other, both are refused and the
        # pair is named. (Without this rule the gate dropped exactly the owner's own nerve on one side of each
        # page -- own_m's left LACN at p95 10.82 mm and own_f's right at 16.73 -- and would have shipped a
        # one-sided lateral antebrachial cutaneous nerve on both Imaging pages.)
        for i in sorted(items):
            other = (i[:-2] + "_r") if i.endswith("_l") else ((i[:-2] + "_l") if i.endswith("_r") else None)
            if other is None or other in items:
                continue
            if other in refused:
                refused[i] = dict(items[i], refused_because=
                                  f"its opposite side {other} was refused ({refused[other]['refused_because']}), "
                                  f"and this round carries a nerve only if BOTH sides pass")
                items.pop(i); arrays.pop(i + "__v", None); arrays.pop(i + "__f", None)
        inverted = sum(1 for v in items.values() if v["cm3"] < 0)
        for v in items.values():
            v["cm3_signed"] = v["cm3"]; v["cm3"] = round(abs(v["cm3"]), 4)
            v["cm3_combined"] = round(abs(v["cm3_combined"]), 4)
        np.savez_compressed(out_root / f"{key}_nerves.npz", **arrays)
        (out_root / f"{key}_nerves.json").write_text(json.dumps(items, indent=1, default=float), encoding="utf-8")
        (out_root / f"{key}_refused.json").write_text(json.dumps(refused, indent=1, default=float), encoding="utf-8")
        rep[key] = dict(pair=PAIR[key], registration=st, bones=breport,
                        bone_groups={k2: len(v2) for k2, v2 in A.items()},
                        gate=dict(p95_mm=GATE_P95_MM, median_mm=GATE_MED_MM),
                        n_candidates=len(cands), n_refused=len(refused),
                        refused={k: v["refused_because"] for k, v in sorted(refused.items())},
                        n_transferred=len(items),
                        n_added=sum(1 for v in items.values() if v["why"].startswith("added")),
                        n_replaced=sum(1 for v in items.values() if v["why"].startswith("replaced")),
                        triangles=int(sum(v["tris"] for v in items.values())),
                        cm3_absolute=round(sum(v["cm3"] for v in items.values()), 2),
                        # the source tubes' winding is not consistent, so only the ABSOLUTE enclosed volume
                        # means anything; Q304 reported its own total the same way, and the count is on record.
                        n_inverted_winding=inverted, ids=sorted(items))
        print(key, "->", len(items), "nerves,", rep[key]["triangles"], "triangles,",
              rep[key]["cm3_absolute"], "cm3 absolute,", len(refused), "refused", flush=True)
        del BM
    rep["_README"] = [
        "Q307: the UPPER-LIMB nerve meshes carried from the Combined page of the same body onto the Imaging page "
        "by Q304's bone-point registration (identity + a thin-plate-spline correction field), plus the three "
        "lower-limb nerves Q304 left as a mirror_q237 stub on one side while the other side carried the full "
        "transferred nerve. scripts/anatomy/q307/xfer307.py. Nothing traced on the body's own imaging is replaced."]
    REPORT.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "build"])
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--modes", default="upper,lower_fix")
    a = ap.parse_args()
    keys = a.keys or ["own_m", "own_f"]
    if a.cmd == "probe":
        old = X4.GROUPS
        try:
            X4.GROUPS = UPPER_GROUPS
            r = X4.probe(keys)
        finally:
            X4.GROUPS = old
        p = REPO / "data/derived/Q307_frame_probe.json"
        p.write_text(json.dumps(r, indent=1), encoding="utf-8"); print("->", p)
    else:
        build(keys, a.out, tuple(a.modes.split(",")))


if __name__ == "__main__":
    main()
