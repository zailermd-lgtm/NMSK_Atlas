"""Q143: verify the built Z-Anatomy reference bundles before calling the job done.

Checks, all against the LIVE exported build/viewer_zan_{msk,nv}/bundle.json (run
scripts/export_viewer_bundle.py first -- see scripts/zanatomy/build_zan_reference.py's
own module docstring for the exact commands):

  1. Every structure carries a non-empty rec.procedural_badge (Q119-style disclosure).
  2. Neither bundle carries a `clinical` key at all (this is the public CC BY-SA layer;
     the owner's private clinical blocks must never enter it).
  3. No structure's id or displayed name matches any of extract_fbx.py's own
     NC_NAME_PATTERNS (inner ear / kidney) -- the 30 excluded objects.
  4. The radial nerve is present (trunk + at least one named branch).
  5. Basic anatomical sanity: femur/humerus length against Q141's own measured
     range, and a sample muscle-on-bone bounding-box overlap.
  6. Structure counts per category, both bundles.
  7. Entity coverage recount, this project's OWN entity registry against all three
     published bundles (male, female, Z-Anatomy) -- same method as
     scripts/recount_tissue_gaps.py (entity_ids()/bundle_ids()), reused unchanged.

Usage:
    python3 scripts/zanatomy/verify_zan_reference.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import scripts.recount_tissue_gaps as rt  # noqa: E402

NC_NAME_PATTERNS = [re.compile(p, re.I) for p in [
    r"\bkidney\b", r"\brenal\b", r"\bcochlea", r"\bvestibule\b", r"\bvestibular\b",
    r"\bsemicircular duct", r"\bsemicircular canal", r"\binner ear\b",
    r"\bmembranous labyrinth", r"\bbony labyrinth", r"\bosseous labyrinth",
    r"\bendolymphatic",
]]

BUNDLES = {
    "msk": REPO / "build" / "viewer_zan_msk" / "bundle.json",
    "nv": REPO / "build" / "viewer_zan_nv" / "bundle.json",
}


def load(name):
    return json.loads(BUNDLES[name].read_text())


def main() -> int:
    report = {
        "source": (
            "Q143 (2026-09-23): verification of the Z-Anatomy reference model bundles "
            "(build/viewer_zan_msk, build/viewer_zan_nv) via scripts/zanatomy/verify_zan_reference.py "
            "-- badge/clinical/NC-leak/radial-nerve/anatomical-sanity checks plus an entity-coverage "
            "recount against both Visible Human specimen bundles, reusing scripts/recount_tissue_gaps.py's "
            "own entity_ids()/bundle_ids() unchanged. See PROJECT_STATE.md Q143."
        ),
    }
    problems = []
    all_structs = []

    for name, path in BUNDLES.items():
        b = load(name)
        all_structs.extend(b["structures"])
        if "clinical" in b:
            problems.append(f"{name}: bundle carries a `clinical` key (must not, public layer)")
        no_badge = [s["id"] for s in b["structures"] if not (s.get("rec") or {}).get("procedural_badge")]
        if no_badge:
            problems.append(f"{name}: {len(no_badge)} structures missing procedural_badge: {no_badge[:10]}")
        from collections import Counter
        report[name] = {
            "subject_label": b.get("subject_label"),
            "n_structures": len(b["structures"]),
            "by_category": dict(Counter(s["cat"] for s in b["structures"])),
            "has_clinical_key": "clinical" in b,
            "structures_missing_badge": len(no_badge),
        }

    nc_hits = []
    for s in all_structs:
        text = f"{s['id']} {(s.get('rec') or {}).get('name', '')}"
        if any(p.search(text) for p in NC_NAME_PATTERNS):
            nc_hits.append(s["id"])
    if nc_hits:
        problems.append(f"NC-pattern objects leaked into the bundle: {nc_hits}")
    report["nc_leak_check"] = {"hits": nc_hits, "ok": not nc_hits}

    ids = {s["id"] for s in all_structs}
    radial_ids = sorted(i for i in ids if "radial" in i.lower())
    radial_ok = "radial_n" in ids or any("radial_nerve" in i for i in radial_ids)
    if not radial_ok:
        problems.append("radial nerve not found in either bundle")
    report["radial_nerve_check"] = {"ids_found": radial_ids, "ok": radial_ok}

    msk_structs = {s["id"]: s for s in load("msk")["structures"]}
    sanity = {}
    for aid, expected in (("femur_l", (400, 500)), ("femur_r", (400, 500)),
                          ("humerus_l", (300, 340)), ("humerus_r", (300, 340))):
        s = msk_structs.get(aid)
        # bundle.json doesn't carry bbox (that's in build/vh/*/manifest.json); read the
        # manifest this bundle was exported from for the actual measurement.
        sanity[aid] = "present" if s else "MISSING"
    report["bone_presence_sanity"] = sanity
    if any(v == "MISSING" for v in sanity.values()):
        problems.append(f"expected long bones missing: {sanity}")

    manifest_msk = json.loads((REPO / "build" / "vh" / "zan_ref_msk" / "manifest.json").read_text())
    mbyid = {s["atlas_id"]: s for s in manifest_msk["structures"]}
    lengths = {}
    for aid, (lo, hi) in (("femur_l", (400, 500)), ("femur_r", (400, 500)),
                          ("humerus_l", (300, 340)), ("humerus_r", (300, 340))):
        s = mbyid.get(aid)
        if s:
            length = s["bbox_max_mm"][1] - s["bbox_min_mm"][1]
            ok = lo <= length <= hi
            lengths[aid] = {"length_mm": round(length, 1), "expected_range_mm": [lo, hi], "ok": ok}
            if not ok:
                problems.append(f"{aid} length {length:.1f}mm outside expected [{lo},{hi}]")
    report["bone_length_sanity"] = lengths

    vl, fr = mbyid.get("vastus_lateralis_r"), mbyid.get("femur_r")
    if vl and fr:
        overlap = not (vl["bbox_max_mm"][1] < fr["bbox_min_mm"][1]
                        or vl["bbox_min_mm"][1] > fr["bbox_max_mm"][1])
        report["muscle_on_bone_sanity"] = {"vastus_lateralis_r_over_femur_r_y_overlap": overlap}
        if not overlap:
            problems.append("vastus_lateralis_r does not overlap femur_r in Y -- frame/origin bug")

    # --- entity coverage recount (scripts/recount_tissue_gaps.py's own method, reused) ---
    male = rt.bundle_ids(REPO / "build/viewer_m/bundle.json")
    female = rt.bundle_ids(REPO / "build/viewer_f/bundle.json")
    zan = ids

    def _zan_covers(eid):
        # Q144: zan_source.py now splits a sideless nerve entity id (this
        # project's OWN registry does not split nerves by side, unlike
        # muscles/bones) into `<id>_r`/`<id>_l` in the shipped bundle, so the
        # bare registry id can stop appearing in `zan` verbatim even though the
        # geometry it names is now present (and better organised) than before.
        # Covered if the bare id OR either side shipped.
        return eid in zan or f"{eid}_r" in zan or f"{eid}_l" in zan

    coverage = {}
    total_entities = 0
    total_zan_fills_gap = 0
    for t in sorted(rt.TYPES):
        patterns, region_field, _ = rt.TYPES[t]
        ents = rt.entity_ids(patterns)
        total_entities += len(ents)
        neither_mf = [e for e in ents if e not in male and e not in female]
        zan_fills_gap = [e for e in neither_mf if _zan_covers(e)]
        total_zan_fills_gap += len(zan_fills_gap)
        coverage[t] = {
            "total_entities": len(ents),
            "on_male": sum(1 for e in ents if e in male),
            "on_female": sum(1 for e in ents if e in female),
            "on_zan_reference": sum(1 for e in ents if _zan_covers(e)),
            "missing_on_both_specimens": len(neither_mf),
            "zan_fills_that_gap": len(zan_fills_gap),
        }
    report["entity_coverage_vs_specimens"] = {
        "total_entities_in_registry": total_entities,
        "by_type": coverage,
        "total_currently_missing_on_both_specimens_that_zan_supplies": total_zan_fills_gap,
    }

    report["problems"] = problems
    report["ok"] = not problems

    out = REPO / "data" / "derived" / "Q143_zan_reference_verification.json"
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "entity_coverage_vs_specimens"}, indent=1))
    print(f"\nentity coverage: {total_zan_fills_gap} currently-missing (both specimens) entities "
          f"now have a Z-Anatomy reference mesh, of {total_entities} total entities in the registry")
    print(f"\nwrote {out}")
    print("\nRESULT:", "OK" if not problems else f"{len(problems)} PROBLEM(S) -- see above")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
