#!/usr/bin/env python3
"""Q246 -- aggregate the harness runs (scripts/clinical/q246_run.js, q246_us.js) into before / after tables and the small result files in data/derived/q246/.

    python3 scripts/clinical/q246_report.py RUNS_DIR OUT_DIR       RUNS_DIR holds img_{before,after}_{own_f,zan_f}.json and us_{before,after}_{own_f,zan_f}.json
Writes OUT_DIR/metrics_q246.json (the aggregated tables + the thresholds the tests read) and prints the tables (markdown)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PAGES = {"own_f": "Imaging-based Female (own engine)", "zan_f": "Combined Female (Z engine)"}


def _mean(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.mean(xs)) if xs else None


def img_table(run: dict) -> dict:
    S = run["series"]
    sel = lambda pred: [v for k, v in S.items() if pred(k)]            # noqa: E731
    single = sel(lambda k: k.endswith(".ct_single") or ".mr_" in k)     # one-sample slices (CT + MRI)
    slabs = sel(lambda k: k.endswith("ct_avg5") or k.endswith("ct_mip5"))
    everything = single + slabs
    out = {
        "ncc_adjacent_1mm": _mean([v["ncc_adjacent"] for v in everything]),
        "ncc_adjacent_1mm_ct_single": _mean([v["ncc_adjacent"] for v in sel(lambda k: k.endswith(".ct_single"))]),
        "mad_1mm": _mean([v["mad_gray"]["1"] for v in everything]),
        "mad_8mm": _mean([v["mad_gray"]["8"] for v in everything]),
        "mad_ratio_1mm_over_8mm": _mean([v["mad_gray"]["1"] / v["mad_gray"]["8"] for v in everything]),
        "value_flip_frac": _mean([v["value_flip_frac"] for v in everything]),
        "value_flip_isolated_frac": _mean([v["value_flip_isolated_frac"] for v in everything]),
        "label_change_frac": _mean([v["label_change_frac"] for v in everything]),
        "label_change_isolated_frac": _mean([v["label_change_isolated_frac"] for v in everything]),
        "islands_per_100k_body_px": _mean([v["islands_per_100k_body_px"] for v in everything]),
        "edge_jaggedness_px": _mean([v["edge_jaggedness_px"] for v in everything]),
        "odd_rows_per_subslice": _mean([v.get("odd_rows_per_subslice") for v in single]),
        "holes_filled_px_per_subslice": _mean([v.get("holes_filled_px_per_subslice") for v in single]),
    }
    for site in ("thigh", "pelvis", "knee", "shoulder"):
        out[f"jag_{site}"] = _mean([v["edge_jaggedness_px"] for k, v in S.items() if k.startswith(site + ".") and ".mr_" not in k])
        out[f"ncc_{site}"] = _mean([v["ncc_adjacent"] for k, v in S.items() if k.startswith(site + ".")])
    out["pan_lin_residual"] = _mean([v["pan_lin_residual"] for v in run["pan"].values()])
    out["z_lin_residual"] = _mean([v["z_lin_residual"] for v in run["pan"].values()])
    for mod in ("ct", "mr"):
        out[f"noise_{mod}_corr_rerender"] = _mean([v[mod]["corr_same_plane_rerender"] for v in run["noise"].values()])
        out[f"noise_{mod}_corr_pan10px_tissue_attached"] = _mean([v[mod]["corr_pan_10px_tissue_attached"] for v in run["noise"].values()])
        out[f"noise_{mod}_corr_adjacent_1mm"] = _mean([v[mod]["corr_adjacent_1mm"] for v in run["noise"].values()])
    pairs: dict[str, float] = {}
    for v in S.values():
        for name, pm in v["top_changing_pairs_permille"]:
            pairs[name] = pairs.get(name, 0.0) + pm / max(1, len(S))
    out["top_changing_pairs_permille"] = sorted(([k, round(x, 3)] for k, x in pairs.items()), key=lambda t: -t[1])[:8]
    cls = {}
    for c in ("muscle", "fat", "bone_cortical"):
        xs = [v["class_intensity"][c] for v in S.values() if v["class_intensity"].get(c)]
        cls[c] = {"std_across_slices": _mean([x["std_across_slices"] for x in xs]), "within_sd": _mean([x["mean_within_sd"] for x in xs]), "mean": _mean([x["mean"] for x in xs])}
    out["class_intensity_ct_first_series"] = cls
    out["perf_ms"] = {k: (round(v["total_ms"], 1) if isinstance(v, dict) else round(v, 1)) for k, v in run["perf"].items()}
    out["perf_ss"] = {k: v.get("ss") for k, v in run["perf"].items() if isinstance(v, dict)}
    out["bias"] = {k: v for k, v in run.get("bias", {}).items() if v}
    return out


def us_table(run: dict) -> dict:
    out = {}
    for sc, v in run["scenes"].items():
        sp = v["speckle"]
        out[sc] = {
            "star_rock_ncc_1deg": v["star_dir0"]["ncc_1deg"], "star_fan_ncc_1deg": v["star_dir90"]["ncc_1deg"],
            "star_rock_mad_1deg": v["star_dir0"]["mad_1deg"], "star_fan_mad_1deg": v["star_dir90"]["mad_1deg"],
            "signal_frac_star": _mean([v["star_dir0"].get("signal_frac"), v["star_dir90"].get("signal_frac")]), "signal_frac_star_min": min(v["star_dir0"].get("signal_frac_min", 1), v["star_dir90"].get("signal_frac_min", 1)), "star_rock_mad_4deg": v["star_dir0"]["mad_4deg"], "star_fan_mad_4deg": v["star_dir90"]["mad_4deg"],
            "star_texture_ncc_1deg": _mean([v["star_dir0"]["texture_ncc_1deg"], v["star_dir90"]["texture_ncc_1deg"]]),
            "homogeneous_speckle_ncc_1deg_fan": sp["star_fan_ncc_1deg"], "homogeneous_speckle_ncc_1deg_rock": sp["star_rock_ncc_1deg"], "homogeneous_speckle_ncc_5deg_fan": sp["star_fan_ncc_5deg"],
            "system_noise_ncc_1deg": sp.get("system_noise_ncc_1deg_fan"), "mean_db_sd_across_star": sp["mean_db_sd_across_star"],
            "sweep_ncc_homog_by_spacing_mm": sp["sweep_ncc_by_spacing_mm"],
            "sweeps": {k: {"signal_frac": s.get("signal_frac"), "ncc_adjacent": s["ncc_adjacent"], "label_change_adjacent": s["label_change_adjacent"], "plane_step_mm_sd": s["plane_step_mm_sd"], "reseat_shift_mm_range": s["reseat_shift_mm_range"], "ms_per_frame": s["ms_per_frame"]} for k, s in v["sweeps"].items()},
            "ms_per_frame_star": _mean([v["star_dir0"]["ms_per_frame"], v["star_dir90"]["ms_per_frame"]]),
        }
    return out


def fmt(x, nd=3):
    return "-" if x is None else (f"{x:.{nd}f}")


def main(runs: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    res = {"pages": PAGES, "imaging": {}, "ultrasound": {}}
    for pg in PAGES:
        res["imaging"][pg] = {}
        for v in ("before", "after"):
            run = json.loads((runs / f"img_{v}_{pg}.json").read_text())
            pf = runs / f"perf_{v}_{pg}.json"                                    # timing re-measured alone on an idle machine (q246_run.js --perfonly), the series runs are timed under load
            if pf.is_file():
                run["perf"] = json.loads(pf.read_text())["perf"]
            res["imaging"][pg][v] = img_table(run)
        try:
            res["ultrasound"][pg] = {v: us_table(json.loads((runs / f"us_{v}_{pg}.json").read_text())) for v in ("before", "after")}
        except FileNotFoundError:
            pass
    (out / "metrics_q246.json").write_text(json.dumps(res, indent=1))
    rows = [("NCC adjacent 1 mm slices (CT + MRI, higher = smoother)", "ncc_adjacent_1mm", 4), ("MAD at 1 mm (grey/255)", "mad_1mm", 4), ("MAD at 8 mm", "mad_8mm", 4), ("value flips >60/255 between slices", "value_flip_frac", 4),
            ("... of which isolated (no flipping neighbour)", "value_flip_isolated_frac", 3), ("label changes between slices", "label_change_frac", 4), ("... isolated", "label_change_isolated_frac", 3),
            ("single-pixel label islands per 100k body px", "islands_per_100k_body_px", 1), ("edge jaggedness (px, body outline)", "edge_jaggedness_px", 3), ("odd (open-seam) scan lines per sub-slice, per image row", "odd_rows_per_subslice", 2),
            ("small gaps filled, px per sub-slice", "holes_filled_px_per_subslice", 2), ("sub-pixel pan: linearity residual", "pan_lin_residual", 3), ("0.25 mm plane step: linearity residual", "z_lin_residual", 3),
            ("noise: same plane re-rendered, corr", "noise_ct_corr_rerender", 3), ("noise: panned 10 px, tissue-attached corr", "noise_ct_corr_pan10px_tissue_attached", 3), ("noise: adjacent 1 mm slice corr", "noise_ct_corr_adjacent_1mm", 3)]
    for pg, name in PAGES.items():
        b, a = res["imaging"][pg]["before"], res["imaging"][pg]["after"]
        print(f"\n### Imaging -- {name}\n| metric | before | after |\n|---|---|---|")
        for label, key, nd in rows:
            print(f"| {label} | {fmt(b.get(key), nd)} | {fmt(a.get(key), nd)} |")
        print("| ms (preview 224 / 5 sub, final 320 single, 320 slab 5 mm, 384 single, 320 slab 25 mm) | " + " / ".join(str(b["perf_ms"].get(k)) for k in ("preview224_5sub", "final320_single", "final320_slab5", "single384", "final320_slab25"))
              + " | " + " / ".join(str(a["perf_ms"].get(k)) for k in ("preview224_5sub", "final320_single", "final320_slab5", "single384", "final320_slab25")) + " |")
        print("| top label changes (permille of body px per mm): before", b["top_changing_pairs_permille"][:4], "| after", a["top_changing_pairs_permille"][:4], "|")
    for pg, name in PAGES.items():
        if pg not in res["ultrasound"]:
            continue
        b, a = res["ultrasound"][pg]["before"], res["ultrasound"][pg]["after"]
        for sc in b:
            print(f"\n### Ultrasound -- {name} -- {sc}\n| metric | before | after |\n|---|---|---|")
            for key in ("signal_frac_star", "signal_frac_star_min", "star_rock_ncc_1deg", "star_fan_ncc_1deg", "star_rock_mad_1deg", "star_fan_mad_1deg", "homogeneous_speckle_ncc_1deg_fan", "homogeneous_speckle_ncc_1deg_rock", "homogeneous_speckle_ncc_5deg_fan", "system_noise_ncc_1deg", "mean_db_sd_across_star", "ms_per_frame_star"):
                print(f"| {key} | {fmt(b[sc].get(key))} | {fmt(a[sc].get(key))} |")
            for k in b[sc]["sweeps"]:
                print(f"| sweep {k}: NCC adjacent / plane-step sd (mm) / ms per frame | {fmt(b[sc]['sweeps'][k]['ncc_adjacent'])} / {b[sc]['sweeps'][k]['plane_step_mm_sd']:.1e} / {b[sc]['sweeps'][k]['ms_per_frame']:.0f} | {fmt(a[sc]['sweeps'][k]['ncc_adjacent'])} / {a[sc]['sweeps'][k]['plane_step_mm_sd']:.1e} / {a[sc]['sweeps'][k]['ms_per_frame']:.0f} |")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
