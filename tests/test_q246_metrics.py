"""Q246 -- continuity metrics (recorded before / after tables of the harness: scripts/clinical/q246_run.js, q246_us.js, q246_report.py -> data/derived/q246/metrics_q246.json) and a live,
small re-measurement on a synthetic body.  The recorded numbers come from the real meshes of Imaging-based Female (own engine) and Combined Female (Z engine); the thresholds below are
what the Q246 changes must keep delivering.  Browser timing (data/derived/q246/browser_*.json) is checked when the files are present."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data" / "derived" / "q246"
M = json.loads((D / "metrics_q246.json").read_text(encoding="utf-8")) if (D / "metrics_q246.json").is_file() else None
needs = pytest.mark.skipif(M is None, reason="data/derived/q246/metrics_q246.json missing (run scripts/clinical/q246_report.py)")
PAGES = ("own_f", "zan_f")


@needs
@pytest.mark.parametrize("pg", PAGES)
def test_imaging_stack_is_smoother_after(pg):
    b, a = M["imaging"][pg]["before"], M["imaging"][pg]["after"]
    assert a["ncc_adjacent_1mm"] > b["ncc_adjacent_1mm"] + 0.02                       # neighbouring 1 mm slices correlate better
    assert a["value_flip_frac"] < 0.85 * b["value_flip_frac"]                           # fewer pixels jump by > 60/255 between neighbouring slices
    assert a["islands_per_100k_body_px"] < 0.6 * b["islands_per_100k_body_px"]          # single-pixel islands / holes
    assert a["pan_lin_residual"] < 0.7 * b["pan_lin_residual"]                          # a sub-pixel pan moves the image linearly (coverage), not by flipping pixels
    assert a["z_lin_residual"] < 0.97 * b["z_lin_residual"]
    assert a["mad_ratio_1mm_over_8mm"] <= b["mad_ratio_1mm_over_8mm"] + 0.01            # change per mm does not grow relative to the change per 8 mm
    assert a["holes_filled_px_per_subslice"] > 1.0 and b["holes_filled_px_per_subslice"] == 0   # the filled gaps are counted


@needs
def test_edges_are_antialiased_on_the_own_engine_and_not_worse_on_the_z_engine():
    b, a = M["imaging"]["own_f"]["before"], M["imaging"]["own_f"]["after"]
    assert a["edge_jaggedness_px"] < 0.6 * b["edge_jaggedness_px"]
    for site in ("thigh", "knee", "pelvis", "shoulder"):
        assert a[f"jag_{site}"] < b[f"jag_{site}"] + 1e-9
    bz, az = M["imaging"]["zan_f"]["before"], M["imaging"]["zan_f"]["after"]
    assert az["edge_jaggedness_px"] < 1.1 * bz["edge_jaggedness_px"]                    # the Z skin outline is itself faceted / layered; the raster does not make it worse


@needs
@pytest.mark.parametrize("pg", PAGES)
def test_noise_belongs_to_the_body(pg):
    b, a = M["imaging"][pg]["before"], M["imaging"][pg]["after"]
    for mod in ("ct", "mr"):
        assert abs(b[f"noise_{mod}_corr_rerender"]) < 0.1 and a[f"noise_{mod}_corr_rerender"] > 0.999          # same plane re-rendered: no new noise
        assert abs(b[f"noise_{mod}_corr_pan10px_tissue_attached"]) < 0.1 and a[f"noise_{mod}_corr_pan10px_tissue_attached"] > 0.999
        assert 0.15 < a[f"noise_{mod}_corr_adjacent_1mm"] < 0.9                                               # neighbouring planes: partly the same grain
        assert abs(b[f"noise_{mod}_corr_adjacent_1mm"]) < 0.1


@needs
def test_coil_bias_is_smooth_between_slices():
    for pg in PAGES:
        for site, v in M["imaging"][pg]["after"]["bias"].items():
            assert v["max_step_between_1mm_slices"] < 0.01                                  # < 1 % per mm at +-20 % amplitude
            assert 0.6 < v["field_min"] <= v["field_max"] < 1.4


@needs
@pytest.mark.parametrize("pg", PAGES)
def test_ultrasound_speckle_follows_the_body_and_signal_is_not_lost(pg):
    b, a = M["ultrasound"][pg]["before"], M["ultrasound"][pg]["after"]
    for sc in a:
        assert a[sc]["homogeneous_speckle_ncc_1deg_fan"] > 0.8 and b[sc]["homogeneous_speckle_ncc_1deg_fan"] < 0.65
        assert a[sc]["homogeneous_speckle_ncc_1deg_rock"] > 0.75 and a[sc]["homogeneous_speckle_ncc_5deg_fan"] > b[sc]["homogeneous_speckle_ncc_5deg_fan"]
        assert a[sc]["system_noise_ncc_1deg"] > 0.05 and abs(b[sc]["system_noise_ncc_1deg"]) < 0.05
        assert a[sc]["mean_db_sd_across_star"] <= b[sc]["mean_db_sd_across_star"] + 1e-9    # the level of a homogeneous block does not wander from tilt to tilt
        assert a[sc]["star_rock_mad_1deg"] <= b[sc]["star_rock_mad_1deg"] * 1.05 + 0.002 or a[sc]["signal_frac_star"] > b[sc]["signal_frac_star"] + 0.3
        for k, s in a[sc]["sweeps"].items():
            assert s["plane_step_mm_sd"] < 1e-9                                            # the frames are evenly spaced
        assert a[sc]["signal_frac_star_min"] > 0.7                                          # no tilt frame loses its image


@needs
def test_combined_female_abdomen_is_no_longer_black():
    b, a = M["ultrasound"]["zan_f"]["before"]["abdomen"], M["ultrasound"]["zan_f"]["after"]["abdomen"]
    assert b["signal_frac_star"] < 0.3 and a["signal_frac_star"] > 0.8                      # the Z skin is open patches: the exterior flood used to fill the body with air
    assert a["star_rock_ncc_1deg"] > 0.85 and a["star_fan_ncc_1deg"] > 0.85


@needs
@pytest.mark.parametrize("pg", PAGES)
def test_recorded_performance_budget(pg):
    b, a = M["imaging"][pg]["before"]["perf_ms"], M["imaging"][pg]["after"]["perf_ms"]
    assert a["preview224_5sub"] < 2.0 * b["preview224_5sub"] + 15                          # the preview that runs while a plane is dragged is not slowed by more than 2x
    assert a["final320_single"] < 120 and a["final320_slab5"] < 300 and a["single384"] < 120 and a["final320_slab25"] < 600      # the full-quality pass (runs when the plane rests)


BROWSER = sorted(D.glob("browser_*.json"))


@pytest.mark.skipif(not BROWSER, reason="no recorded browser runs")
def test_recorded_browser_runs_zero_errors_and_drag_not_slower_than_2x():
    runs = {}
    for f in BROWSER:
        r = json.loads(f.read_text(encoding="utf-8"))
        assert r["errors"] == [], (f.name, r["errors"])
        runs[(r["tag"], r["vp"])] = r
    checked = 0
    for (tag, vp), r in runs.items():
        if not tag.endswith("_after"):
            continue
        base = runs.get((tag.replace("_after", "_before"), vp))
        if not base:
            continue
        ta, tb = r["perf"]["drag_tier0_ms"], base["perf"]["drag_tier0_ms"]
        assert ta and tb
        mean = lambda xs: sum(xs) / len(xs)                                                # noqa: E731
        assert mean(ta) < 2.0 * mean(tb) + 25, (tag, vp, mean(ta), mean(tb))
        checked += 1
    assert checked >= 1


# ---------------------------------------------------------------- live: harness on a synthetic scene (no recorded file needed)
def test_harness_library_metrics_basic():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    code = r"""
const H=require('./scripts/clinical/q246_lib.js');
const a=new Uint8Array(100), b=new Uint8Array(100); for(let i=0;i<100;i++){a[i]=i*2; b[i]=i*2+10;}
const out={ncc:H.ncc(a,b,null), mad:H.mad(a,b,null)};
const lab=new Uint8Array(25*25).fill(3); lab[12*25+12]=4;     // one island in 3
out.isl=H.islands(lab,25,25,0,9).tot;
const A=new Uint8Array(25*25).fill(3), B=A.slice(); B[5*25+5]=4; out.chg=H.labChange(A,B,0,25,25,null);
const g1=new Uint8Array(625), g2=new Uint8Array(625); g2[7*25+7]=255; out.flip=H.valueFlips(g1,g2,new Uint8Array(625).fill(1),25,25,60);
console.log(JSON.stringify(out));"""
    r = subprocess.run([node, "-e", code], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-1500:]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["ncc"] == pytest.approx(1.0) and o["mad"] == pytest.approx(10.0)
    assert o["isl"] == 1 and o["chg"]["changed"] == 1 and o["chg"]["iso"] == 1 and o["flip"]["n"] == 1 and o["flip"]["iso"] == 1
