"""Re-check every structure both bodies carry, at matched scale.

    python3 scripts/transfer/cross_subject_scale_audit.py --male-html data/derived/viewer_bundles/vhm_v25 \
        [--female-bundle build/viewer_f] -o data/derived/cross_subject_scale_audit.json

For each atlas id present on both bodies: female/male volume ratio, the ratio expected from the
bones that drive that region (the determinant of the bone affine, i.e. how much smaller her bones
are), and the residual = measured / expected. A residual far from 1 on a structure the SAME method
produced on both bodies points at a segmentation or rule problem on one of them; a residual near 1
on a rule-based structure says the rule behaved the same on both. Muscles carry a second expected
ratio from the measured lean cross-sections (her thigh muscle is 0.34 of his at matched level), so a
lower-limb muscle residual is judged against that, not against bone alone. Nothing here is anatomy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_html, read_bundle_dir, meshes_by_id, mesh_volume_cm3, own_only  # noqa: E402
from scripts.transfer.cross_subject_transfer import build_bone_maps, REGION_BONES, side_of  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

FLAG_LOW, FLAG_HIGH = 0.6, 1.6
SRC = ("U.S. National Library of Medicine, The Visible Human Project (public domain), male and female CT and cryosections via "
       "the NCI Imaging Data Commons; lower-limb geometry Andreassen et al. 2023, Sci Data 10:34, doi:10.1038/s41597-022-01905-2 "
       "(CC BY 4.0). Derived data (scripts/transfer/cross_subject_scale_audit.py).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--male-html", required=True)
    ap.add_argument("--female-bundle", default="build/viewer_f")
    ap.add_argument("--anthro", default="data/derived/subject_anthropometrics.json")
    ap.add_argument("-o", "--out", default="data/derived/cross_subject_scale_audit.json")
    a = ap.parse_args()
    mp = Path(a.male_html); bm, blob = read_bundle_dir(mp) if mp.is_dir() else read_bundle_html(mp)
    M = own_only(meshes_by_id(bm, blob))
    bf, blobf = read_bundle_dir(a.female_bundle); F = own_only(meshes_by_id(bf, blobf))
    maps = build_bone_maps(M, F)
    anthro = json.loads(Path(a.anthro).read_text()) if Path(a.anthro).exists() else {}
    cc = anthro.get("measured", {})
    lean = {}
    for lvl in ("thigh_45pct_femur", "calf_mid_tibia", "pelvis_abdomen_y40_250", "thorax_y250_450"):
        try:
            lean[lvl] = round(cc["female"]["cryo_classes"][lvl]["muscle_area_cm2"] / cc["male"]["cryo_classes"][lvl]["muscle_area_cm2"], 3)
        except KeyError:
            pass
    rows = []
    for aid in sorted(set(M) & set(F)):
        if aid == "skin":
            continue
        m, f = M[aid], F[aid]
        vm, vf = mesh_volume_cm3(m["v"], m["f"]), mesh_volume_cm3(f["v"], f["f"])
        if vm < 0.05 or vf < 0.05:
            continue
        region = (m.get("rec") or {}).get("region"); side = side_of(aid, m)
        allowed = REGION_BONES.get(region, set(maps))
        cands = [b for b, mpv in maps.items() if b in allowed and (mpv["side"] is None or side is None or mpv["side"] == side)]
        # nearest driving bones (by the male mesh) weighted like the transfer
        c = m["v"][::max(1, len(m["v"]) // 500)]
        D = np.stack([maps[b]["tree"].query(c)[0] for b in cands], axis=1) if cands else None
        if D is None:
            continue
        w = 1.0 / (D + 8.0) ** 2; w /= w.sum(axis=1, keepdims=True)
        det = float(sum(w[:, i].mean() * maps[b]["det"] for i, b in enumerate(cands)))
        meas = vf / vm
        row = {"atlas_id": aid, "category": m["cat"], "region": region, "male_subject": m["subject"], "female_subject": f["subject"],
               "male_cm3": round(vm, 1), "female_cm3": round(vf, 1), "female_over_male": round(meas, 3),
               "expected_from_bones": round(det, 3), "residual": round(meas / det, 3)}
        if m["cat"] == "muscle":
            key = ("thigh_45pct_femur" if region in ("lower_limb", "hip") else
                   "thorax_y250_450" if region in ("trunk", "upper_limb", "pectoral_girdle", "neck") else
                   "pelvis_abdomen_y40_250" if region == "vertebral_column" else None)
            if key in lean:
                # lean cross-section ratio ~ volume ratio x (length ratio)^-1; length ratio ~ det^(1/3)
                row["expected_from_lean_sections"] = round(lean[key] * det ** (1 / 3), 3)
                row["residual_vs_lean"] = round(meas / row["expected_from_lean_sections"], 3)
        r = row.get("residual_vs_lean", row["residual"])
        row["flag"] = "LOW" if r < FLAG_LOW else "HIGH" if r > FLAG_HIGH else ""
        rows.append(row)
    same_method = [r for r in rows if r["male_subject"].replace("vhm", "X") == r["female_subject"].replace("vhf", "X")]
    out = {"source": SRC, "_README": [__doc__.strip().splitlines()[0], "Flags: residual < 0.6 LOW, > 1.6 HIGH (vs the lean-section expectation for muscles where "
                       "one exists, else vs bones). 'same_method' lists the ids the same pipeline produced on both bodies."],
           "lean_section_ratios_female_over_male": lean,
           "n": len(rows), "flagged": [r["atlas_id"] for r in rows if r["flag"]],
           "same_method_flagged": [r["atlas_id"] for r in same_method if r["flag"]],
           "rows": rows}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"{len(rows)} shared structures; flagged {len(out['flagged'])}: {out['flagged']}")
    for r in rows:
        if r["flag"]:
            print(f"  {r['flag']:4s} {r['atlas_id']:28s} {r['male_cm3']:7.1f} -> {r['female_cm3']:7.1f}  meas {r['female_over_male']:.2f} "
                  f"exp {r['expected_from_bones']:.2f}{' lean ' + str(r['expected_from_lean_sections']) if 'expected_from_lean_sections' in r else ''}  "
                  f"({r['male_subject']} / {r['female_subject']})")


if __name__ == "__main__":
    main()
