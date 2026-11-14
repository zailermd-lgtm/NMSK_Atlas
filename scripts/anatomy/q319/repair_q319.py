#!/usr/bin/env python3
"""Q319 repairs on the two BASE pages, using tooling this project already has -- never a new fitting method.

    python3 scripts/anatomy/q319/repair_q319.py \
        --page-dir base_m=build/q309/viewer_zan_atlas \
        --page-dir base_f=build/q309/viewer_base_female

Two repairs, both of them things the project has already done on another page:

  A. THE Q213 SPLIT.  Z-Anatomy's `opponens_digiti_minimi_<side>` is ONE mesh holding the hand muscle AND a
     120-vertex piece in the FOOT. `scripts/zanatomy/q213_zfit.py` already separated them on the Combined .
     Female page, where `opponens_digiti_minimi_foot_l/r` now ship as their own structures. Both BASE pages
     still carry the merged mesh (Q319 measures the two pieces 800.5 mm / 831.9 mm apart). This re-applies that
     exact split, importing `q213_zfit.components` / `q213_zfit.split` rather than re-deriving them.
     NOTHING IS DELETED AND NO VERTEX MOVES: the hand component keeps the id, the foot component becomes a new
     structure, so each page gains two meshes and loses none.

  B. THE Q213 IN-BONE CONFORM.  `scripts/transfer/q213_inbone.repair` pushes a muscle out of the bones it is
     buried in, under its own guards (bounded mean / max move, volume 0.88-1.20x, no folded or over-stretched
     triangles, no attachment end moved off its bone, muscle overlap not allowed to rise). It accepts or HOLDS
     each case itself -- which is exactly the owner's instruction: attempt the fix, and give up where the result
     is not good. Attempted only on the structures the Q319 audit puts in the decision: every muscle in the
     `not_defensible` bucket, plus every muscle with a severity-3 in-bone finding.

Measurement is NOT re-implemented here. The repaired page is handed back to
`audit_reconstructed_muscles_q319.audit_page` in memory, so the before and after numbers come from one
implementation of the metrics and one copy of the bucket rule.

WHAT THIS SCRIPT DOES NOT DO: it does not re-emit the page HTML and it publishes nothing.
`scripts/zanatomy/q205_pages.save_page` renders the page from `viewer/zan_atlas.template.html`, so re-emitting
it requires the whole round pipeline (every injected module, then `scripts/regen_template_only.py`) to equal the
page that is live. That is a page rebuild and a republish, and it is the owner's decision, not this script's.
It writes `data/derived/Q319_repair_report.json`: what was repaired, what was held and why, the before/after
numbers, and the pose-rig splice the repair would need.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

import audit_reconstructed_muscles_q319 as A            # noqa: E402  the metrics and the bucket rule
import build_zan_atlas_viewer as B                      # noqa: E402  pack_mesh: the page's own quantisation
from scripts.zanatomy import q213_zfit as Z13           # noqa: E402  components() / split(): the Q213 split
from scripts.transfer import q213_inbone as IB          # noqa: E402  the guarded in-bone repair

OUT = REPO / "data/derived/Q319_repair_report.json"
SPLIT_IDS = ("opponens_digiti_minimi_r", "opponens_digiti_minimi_l")


def repack(man, S, replace, add):
    """A new (manifest, blob) with `replace` re-quantised and `add` appended. Every untouched mesh keeps its own
    bytes, so the only geometry that changes is the geometry named here (the same contract as
    scripts/zanatomy/q202_pages.save_page, without rendering the HTML)."""
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n = dict(m)
            n.update(fields)
            if rec is not None:
                n["rec"] = rec
            meshes.append(n)
            chunks.append(packed)
            off += len(packed)
        else:
            v, f = S[m["id"]]
            fields, packed = B.pack_mesh(v, f, off)
            n = dict(m)
            n.update(fields)
            meshes.append(n)
            chunks.append(packed)
            off += len(packed)
    for entry, v, f in add:
        fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
        n = dict(entry)
        n.update(fields)
        meshes.append(n)
        chunks.append(packed)
        off += len(packed)
    man2 = dict(man)
    man2["meshes"] = meshes
    return man2, b"".join(chunks)


def do_split(man, S, log):
    """Repair A -- the Q213 split, same semantics, no vertex moved, nothing deleted."""
    by_id = {m["id"]: m for m in man["meshes"]}
    replace, add, done = {}, [], {}
    for sid in SPLIT_IDS:
        if sid not in S:
            continue
        side = sid[-1]
        if f"opponens_digiti_minimi_foot_{side}" in by_id:
            log(f"  {sid}: already split on this page, nothing to do")
            continue
        v, f = S[sid]
        k, lab = Z13.components(v, f)
        if k != 2:
            log(f"  {sid}: {k} components, not 2 -- HELD (the Q213 split only applies to the merged two-piece mesh)")
            continue
        cs = [(int((lab == c).sum()), v[lab == c].mean(0)) for c in range(k)]
        ys = [c[1][1] for c in cs]
        hand_c, foot_c = (0, 1) if ys[0] > ys[1] else (1, 0)   # the hand is the higher piece (as q213_zfit)
        hv, hf = Z13.split(v, f, lab, hand_c)
        fv, ff = Z13.split(v, f, lab, foot_c)
        apart = abs(ys[0] - ys[1])
        rec = dict(by_id[sid].get("rec") or {})
        rec_h = dict(rec)
        rec_h["procedural_badge"] = ((rec.get("procedural_badge") or "") + (
            " Q319: the Z-Anatomy source mesh of this id was ONE mesh made of the hand muscle AND a "
            f"{len(fv)}-vertex piece in the FOOT (the two parts lie {apart:.0f} mm apart); the foot piece is now "
            f"its own structure `opponens_digiti_minimi_foot_{side}`, by the same separation Q213 applied to the "
            "Combined - Female page. Hand geometry unchanged.")).strip()
        rec_f = {k2: v2 for k2, v2 in rec.items() if k2 in ("source", "folder", "region", "latin")}
        rec_f.update(name="Opponens digiti minimi (foot)",
                     origin="foot (Z-Anatomy source piece; the origin is not stated by the source)",
                     insertion="foot (Z-Anatomy source piece)",
                     procedural_badge=(
                         f"Q319: separated from the Z-Anatomy mesh `{sid}`, which merged this FOOT piece with the "
                         f"hand muscle ({apart:.0f} mm apart); geometry unchanged. Identity of this small foot "
                         "muscle follows the Z-Anatomy source; not verified on this body. Same separation as "
                         "Q213 on the Combined - Female page."))
        replace[sid] = (hv, hf, rec_h)
        add.append(({"name": "Opponens digiti minimi (foot)", "id": f"opponens_digiti_minimi_foot_{side}",
                     "side": side, "sys": "muscle", "rec": rec_f}, fv, ff))
        done[sid] = dict(hand_vertices=int(len(hv)), foot_vertices=int(len(fv)),
                         pieces_apart_mm=round(float(apart), 1),
                         new_structure=f"opponens_digiti_minimi_foot_{side}")
        log(f"  split {sid}: hand {len(hv)} v + foot {len(fv)} v, {apart:.0f} mm apart "
            f"-> new structure opponens_digiti_minimi_foot_{side}")
    return replace, add, done


def do_inbone(man, S, targets, replace, log):
    """Repair B -- the Q213 in-bone conform. The tool's own guards decide each case."""
    bones = {m["id"]: S[m["id"]] for m in man["meshes"]
             if m["sys"] == "bone" and len(S[m["id"]][1]) > 20}
    log(f"  bone field over {len(bones)} bones ...")
    field = IB.BoneField(bones)
    from scipy.spatial import cKDTree
    tree = cKDTree(np.vstack([v for v, _ in bones.values()]))
    mo = IB.MuscleOverlap({m["id"]: S[m["id"]] for m in man["meshes"] if m["sys"] == "muscle"})
    out = {"repaired": {}, "held": {}}
    for mid in targets:
        if mid not in S:
            continue
        v, f = (replace[mid][0], replace[mid][1]) if mid in replace else S[mid]
        v = np.asarray(v, float)
        ins, _, _ = field.inside(v)
        pct = 100.0 * float(ins.mean())
        nv, rep = IB.repair(v, f, field, end_tree=tree, overlap=lambda V, i=mid: mo.pct(V, (i,)))
        rep["inside_before_vertex_pct"] = round(pct, 1)
        if nv is None:
            out["held"][mid] = rep
            log(f"  {mid:46s} in bone {pct:5.1f} %  HELD: {'; '.join(rep['why_not'])}")
            continue
        rec = dict((next(m for m in man['meshes'] if m['id'] == mid).get("rec")) or {})
        if mid in replace:
            rec = dict(replace[mid][2] or rec)
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + (
            " Q319 in-bone repair (the Q213 guarded conform, scripts/transfer/q213_inbone): vertices inside this "
            f"page's bones {rep['inside_before_pct']} -> {rep['inside_after_pct']} % of the mesh, mean move "
            f"{rep['mean_move_mm']} mm, max {rep['max_move_mm']} mm, volume x{rep['volume_ratio']}; attachment "
            "ends held on their bone.")).strip()
        replace[mid] = (nv, f, rec)
        out["repaired"][mid] = rep
        log(f"  {mid:46s} in bone {pct:5.1f} %  REPAIRED -> {rep['inside_after_pct']} % "
            f"(mean move {rep['mean_move_mm']} mm, volume x{rep['volume_ratio']})")
    return out


def rig_splice(key, n_before, added_ids, man2):
    """What the pose rig needs so Pose keeps working: the ADDED structures appended as RIGID entries of the foot
    segment -- exactly how the sister page (Combined . Female) carries opponens_digiti_minimi_foot_l/r. Appending
    shifts no existing index and touches no skinning weight."""
    f = REPO / f"data/anatomy/pose_rig_{key}.json"
    if not f.exists():
        return {"error": f"no committed rig at {f}"}
    R = json.loads(f.read_text(encoding="utf-8"))["rig"]
    segs = {i: s[0] for i, s in enumerate(R["segs"])}
    ids2 = [m["id"] for m in man2["meshes"]]
    plan = []
    for sid in added_ids:
        side = sid[-1]
        seg = [i for i, nm in segs.items() if nm == f"foot_{side}"]
        plan.append(dict(structure=sid, new_index=ids2.index(sid),
                         n_vertices=int(next(m for m in man2["meshes"] if m["id"] == sid)["vc"]),
                         rig_entry="rigid", segment_index=(seg[0] if seg else None),
                         segment=(f"foot_{side}" if seg else None)))
    return {"rig_file": str(f.relative_to(REPO)), "count_before": R["count"], "count_after": n_before + len(added_ids),
            "page_meshes_after": len(ids2),
            "committed_rig_matches_page_before": R["count"] == n_before,
            "skinning_weights_touched": False,
            "existing_indices_shifted": 0,
            "why": ("the new structures are APPENDED, so every existing index keeps its value and the weight blob "
                    "is untouched; each new one is a rigid entry of its foot segment, which is how "
                    "Combined . Female already carries opponens_digiti_minimi_foot_l/r (indices 2940 / 2939, "
                    "rigid in segments foot_l / foot_r, 120 vertices each)"),
            "entries": plan,
            "then": ("python3 scripts/anatomy/q241/make_pose_rig.py --inject <page dir>  -- which re-checks the "
                     "structure and per-structure vertex counts against the page before writing")}


def run_page(key, page_dir, cap, before, gate, log=print):
    t0 = time.time()
    man, blob = A.read_page(Path(page_dir), None)
    S = {m["id"]: A.decode_one(m, blob) for m in man["meshes"]}
    n_before = len(man["meshes"])
    log(f"\n=== {A.LABEL.get(key, key)}: {n_before} meshes from {page_dir}")

    log(" repair A -- the Q213 split")
    replace, add, split_done = do_split(man, S, log)

    # Who gets the in-bone repair attempted: Q213's own criterion, which is the project's own gate --
    # scripts/zanatomy/q213_zfit.IN_BONE_MIN = 8 % of VERTICES inside bone, the same line as
    # scripts/anatomy/q237/fill.BELLY_IN_BONE_MAX -- plus anything in the not-defensible bucket, whatever put it
    # there. Deliberately NOT "severity 2/3 in-bone": Q198's severity ladder starts at the same 8 %, so a muscle
    # at 10-20 % is only severity 1 and would be skipped, yet it is exactly what Q213 would have repaired.
    bm = before["muscles"]
    targets = sorted({mid for mid, r in bm.items()
                      if r["bucket"] == "not_defensible"
                      or (r.get("in_bone_vertex_pct") or 0.0) >= gate})
    log(f"\n repair B -- the Q213 in-bone conform, attempted on {len(targets)} structures "
        f"(the not-defensible bucket, plus every muscle at or above {gate:g} % of its vertices inside bone)")
    inbone = do_inbone(man, S, targets, replace, log)

    man2, blob2 = repack(man, S, replace, add)
    added_ids = [e[0]["id"] for e in add]
    log(f"\n re-measuring the repaired page with the audit's own metrics ...")
    after = A.audit_page(key, None, None, f"{page_dir} + Q319 repairs (in memory, not published)", cap,
                         verbose=False, man_blob=(man2, blob2))
    return dict(page=key, label=A.LABEL.get(key, key), source=page_dir,
                meshes_before=n_before, meshes_after=len(man2["meshes"]),
                structures_added=added_ids, structures_deleted=[],
                split=split_done, in_bone=inbone, in_bone_gate_pct=gate,
                in_bone_full_pass_would_be=sorted(
                    m for m, r in before["muscles"].items() if (r.get("in_bone_vertex_pct") or 0.0) > 8.0),
                geometry_changed=sorted(replace), 
                bucket_counts_before=before["bucket_counts"], bucket_counts_after=after["bucket_counts"],
                pose_rig=rig_splice(key, n_before, added_ids, man2),
                seconds=round(time.time() - t0, 1)), after


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", action="append", default=[], metavar="KEY=PATH", required=True)
    ap.add_argument("--audit", default=str(A.OUT), help="the Q319 audit JSON holding the BEFORE state")
    ap.add_argument("--cap", type=int, default=250000)
    ap.add_argument("--gate", type=float, default=20.0,
                    help=("in-bone repair is attempted at or above this %% of VERTICES inside bone. The project's "
                          "own gate is 8 %% (q213_zfit.IN_BONE_MIN = fill.BELLY_IN_BONE_MAX), which selects 94 "
                          "muscles on Base M and 86 on Base F -- a mass geometry change on the owner's most "
                          "important models. The default 20 %% is a reviewable DEMONSTRATION of the top of the "
                          "distribution; the full 8 %% pass is a proposal, not something this script does unasked."))
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)

    audit = json.loads(Path(a.audit).read_text(encoding="utf-8"))
    rep = {"schema": "nmsk.q319.repair.v1", "round": "Q319", "generated": time.strftime("%Y-%m-%d"),
           "what": ("repairs made with tooling the project already has, measured before and after with "
                    "scripts/anatomy/q319/audit_reconstructed_muscles_q319.py; nothing deleted, nothing published"),
           "not_done": ("the page HTML was not re-emitted: scripts/zanatomy/q205_pages.save_page renders from "
                        "viewer/zan_atlas.template.html, so a republish needs the whole round pipeline and the "
                        "owner's approval"),
           "pages": {}, "per_structure": {}}
    for s in a.page_dir:
        key, _, path = s.partition("=")
        if key not in audit["pages"]:
            raise SystemExit(f"{key} is not in {a.audit} -- audit the page first")
        before = audit["pages"][key]
        page_rep, after = run_page(key, path, a.cap, before, a.gate)
        rep["pages"][key] = page_rep
        # the before/after of every structure whose geometry or bucket moved
        moved = {}
        for mid, aft in after["muscles"].items():
            bef = before["muscles"].get(mid)
            keys = ("volume_cm3", "length_mm", "n_components", "component_centroid_spread_mm",
                    "spread_over_diag", "overlap_muscle_pct", "in_bone_pct", "bone_deepest_mm",
                    "acsa_mm2", "acsa_ratio_lit", "bucket")
            if bef is None:
                moved[mid] = {"status": "NEW structure", "after": {k: aft.get(k) for k in keys}}
            elif any(bef.get(k) != aft.get(k) for k in keys):
                moved[mid] = {"status": "changed",
                              "before": {k: bef.get(k) for k in keys},
                              "after": {k: aft.get(k) for k in keys},
                              "after_severity_3": aft["bucket_because"]["severity_3"],
                              "before_severity_3": bef["bucket_because"]["severity_3"]}
        rep["per_structure"][key] = moved
        print(f"\n {A.LABEL.get(key, key)}: buckets {page_rep['bucket_counts_before']} -> "
              f"{page_rep['bucket_counts_after']}; {len(moved)} structures moved")
    Path(a.json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("\nwritten " + a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
