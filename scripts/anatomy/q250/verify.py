#!/usr/bin/env python3
"""Q250: female / male skeletal and body indicators of the pages before and after, against adult-women reference ranges (own measurement on n CT women of the TotalSegmentator dataset v2.0.1, CC BY 4.0,
and PubMed-verified literature numbers), written to data/derived/Q250_sex_indicators.json + .md.
    python3 scripts/anatomy/q250/verify.py [--base-new DIR] [--comb-new DIR] [--skip-measure]
Measures = scripts/anatomy/q233/dimorphism.py rules (same code as Q233; the sciatic-notch hull angle on dense surface samples, see measure.py) + body_measures.py."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import q233_load as Q  # noqa: E402
from scripts.anatomy.q250.measure import measure  # noqa: E402
from scripts.anatomy.q250.body_measures import measure_body  # noqa: E402

D = REPO / "data" / "derived"
KEYS = [  # (key, label, kind, literature)
    ("subpubic_angle_deg", "Subpubic angle (angle between the ischiopubic rami) [deg]", "ts+lit", "CT, 50 M / 50 F: male 68.6 +- 7.6, female 87.4 +- 6.5, cut-off 78.6 deg (Mohd Ali et al. 2020, PMID 32274246, verified abstract)"),
    ("inlet_index_ap_over_transverse_pct", "Pelvic inlet index (AP conjugate / transverse diameter x 100) [%]", "ts", "direction only: male pelvic inlet shorter (PMID 21136101); no number read"),
    ("intertuberous_mm", "Pelvic outlet width (intertuberous distance) [mm]", "ts", "direction only: transverse outlet among the most dimorphic measures (PMID 24789357, 42793678)"),
    ("sciatic_notch_hull_angle_deg", "Greater sciatic notch, hull-defect angle on dense surface samples [deg]", "ts", "direction only (wider in women: PMID 39623825, 34554326); NOT diagnostic by this method (male donor 98.5, female donor 93.2, women 98 +- 6)"),
    ("sacral_index_breadth_over_length_pct", "Sacral index (breadth of upper half / straight length x 100) [%]", "ts", "direction only: higher in women (PMID 37284374; caveat PMID 35385483: weakly dimorphic)"),
    ("bi_iliac_breadth_mm", "Bi-iliac breadth of the hip bones [mm]", "ts", "women have the wider pelvis relative to the shoulders (PMID 36628541); no number read"),
    ("breadth_over_height_pct", "Pelvic breadth / height of the hip bones [%]", "ts", ""),
    ("bi_acetabular_distance_mm", "Distance between the femoral head centres [mm]", "ts", ""),
    ("shoulder_to_hip_ratio", "Biacromial / bi-iliac ratio (scapula + clavicle extent over hip-bone breadth)", "lit", "males have broader shoulders and narrower hips than females (PMID 36628541); no number read"),
    ("clavicle_length_l_mm", "Clavicle length [mm]", "lit", "male clavicles larger: dry bone, 60 M / 60 F, max length significant (PMID 41960515); no number read"),
    ("thorax_width_mm", "Rib-cage width [mm]", "lit", "thoracic bones dimorphic: rib width, sternum, clavicle (CT, 240 adults; PMID 39382593); no number read"),
    ("femoral_head_diameter_r_mm", "Femoral head diameter [mm]", "lit", "smaller in women (PMID 37803256, 40547822); population-dependent absolute values"),
    ("bicondylar_breadth_r_mm", "Femoral bicondylar breadth [mm]", "lit", "direction only"),
    ("femur_length_over_stature_pct", "Femur length / stature [%]", "unv", "UNVERIFIED: no number read"),
    ("head_height_over_stature_pct", "Head height / stature [%]", "unv", "UNVERIFIED: no number read"),
    ("stature_mm", "Stature (skin extent) [mm]", "unv", "UNVERIFIED: adult women about 1.6-1.65 m in most populations (no number read here)"),
    ("waist_to_hip_breadth_ratio", "Waist / hip skin breadth ratio", "unv", "UNVERIFIED as a body-breadth ratio; waist-hip CIRCUMFERENCE ratio thresholds women 0.85 / men 0.90 are screening cut-offs, not means (PMID 36235677)"),
    ("q_angle_r_deg", "Q angle proxy (bone landmarks, supine / standing pose dependent) [deg]", "pose", "female 13.7 +- 1.9 vs male 11.1 +- 1.9 (PMID 36713821); NOT measurable from skeleton meshes in a non-weight-bearing pose (Q233)"),
]


def ts_stats():
    d = json.loads((D / "Q250_ts_women_pelvis_measures.json").read_text())
    out = {}
    for k, *_ in KEYS:
        v = [x[k] for x in d.values() if isinstance(x, dict) and x.get(k) is not None]
        if len(v) > 5:
            out[k] = dict(n=len(v), mean=round(float(np.mean(v)), 1), sd=round(float(np.std(v)), 1), p5=round(float(np.percentile(v, 5)), 1), p95=round(float(np.percentile(v, 95)), 1))
    return out


def measure_page(key, dirpath):
    os.environ["Q233_SRC_" + key] = dirpath
    S = Q.load(key)
    r = measure(S)
    r.update(measure_body(S))
    if key.startswith("own"):          # the own pages carry one merged skin mesh and differently named skull / rib meshes: the body measures of the Z rules do not apply
        for k in ("stature_mm", "head_height_mm", "head_height_over_stature_pct", "femur_length_over_stature_pct", "stature_note", "thorax_width_mm", "thorax_depth_mm", "waist_skin_breadth_mm", "hip_skin_breadth_mm", "waist_to_hip_breadth_ratio"):
            r[k] = None
    r["page_dir"] = dirpath
    return r


def verdict(k, v, ts):
    if v is None or k not in ts:
        return None
    t = ts[k]
    if k == "subpubic_angle_deg":
        return "female (>= 78.6 cut-off)" if v >= 78.6 else "male range (< 78.6 cut-off)"
    lo, hi = t["mean"] - 2 * t["sd"], t["mean"] + 2 * t["sd"]
    return "within women mean +- 2 SD" if lo <= v <= hi else ("below women range" if v < lo else "above women range")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-new", default="build/q250/viewer_base_female"); ap.add_argument("--comb-new", default="build/q250/viewer_zan_female")
    ap.add_argument("--skip-measure", action="store_true")
    a = ap.parse_args()
    out = D / "Q250_sex_indicators.json"
    if a.skip_measure and out.exists():
        R = json.loads(out.read_text())
    else:
        before = json.loads((D / "Q250_measures_before.json").read_text())
        R = dict(pages={}, ts_women=ts_stats(), keys=[dict(key=k, label=l, kind=kd, literature=lit) for k, l, kd, lit in KEYS])
        for lab, key, d in (("Base M", "base_m", "build/q244/viewer_zan_atlas"), ("Base F (before Q250)", "base_f", "build/q244/viewer_base_female"), ("Base F (Q250)", "base_f", a.base_new),
                            ("Combined F (before Q250)", "comb_f", "build/q244/viewer_zan_female"), ("Combined F (Q250)", "comb_f", a.comb_new),
                            ("Imaging-based F (her own CT)", "own_f", "build/q244/viewer_f_hr"), ("Imaging-based M (his own CT)", "own_m", "build/q244/viewer_m_hr")):
            R["pages"][lab] = measure_page(key, d)
            print(lab, flush=True)
        out.write_text(json.dumps(R, indent=1, default=float) + "\n")
    ts = R["ts_women"]
    labs = list(R["pages"])
    md = ["# Q250 - female / male indicators, before and after", "",
          "Measures: the Q233 landmark rules (`scripts/anatomy/q233/dimorphism.py`) on the meshes of each page, body measures (`body_measures.py`). Reference: **women, n = %s CT cases of the TotalSegmentator dataset v2.0.1 (CC BY 4.0) measured with the SAME rules** (mean +- SD), plus PubMed-verified numbers where one exists. Verdict column: Q250 page vs the women range." % (ts.get("subpubic_angle_deg", {}).get("n")), ""]
    md.append("| indicator | " + " | ".join(labs) + " | women (CT, n=%s) mean +- SD | literature |" % ts.get("subpubic_angle_deg", {}).get("n"))
    md.append("|---|" + "---|" * (len(labs) + 2))
    for k, label, kind, lit in KEYS:
        row = [str(R["pages"][l].get(k)) for l in labs]
        t = ts.get(k)
        md.append(f"| {label} | " + " | ".join(row) + f" | {('%s +- %s' % (t['mean'], t['sd'])) if t else '-'} | {lit} |")
    md += ["", "## Verdicts of the Q250 pages", ""]
    for lab in ("Base F (Q250)", "Combined F (Q250)", "Base F (before Q250)", "Combined F (before Q250)"):
        md.append(f"**{lab}**")
        for k, label, kind, lit in KEYS:
            v = R["pages"][lab].get(k); vd = verdict(k, v, ts)
            if vd:
                md.append(f"- {label}: {v} -> {vd}")
        md.append("")
    (D / "Q250_sex_indicators.md").write_text("\n".join(md) + "\n")
    print("written", out)


if __name__ == "__main__":
    main()
