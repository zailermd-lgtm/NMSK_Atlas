"""Q293: owner's three points -- finger re-articulation (Combined pages), the rule-based reflected head of rectus femoris (all six
pages), the Learn simulation (start position set, not animated; whole-muscle 'All together'), and the action-sign audit of every
muscle row against this project's own computed moment arms (Q284)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data/anatomy"
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
ACT = json.loads((DATA / "muscle_actions_q283.json").read_text(encoding="utf-8"))
AUD = json.loads((DATA / "muscle_audit_q293.json").read_text(encoding="utf-8"))


def run(*a):
    return subprocess.run([sys.executable, *a], cwd=REPO, capture_output=True, text=True)


def test_audit_corrections_in_place():
    r = run("scripts/anatomy/q293/audit_q293.py", "check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_heads_table_and_learn_data_up_to_date():
    for a in (["scripts/anatomy/q293/heads_q293.py", "--check"], ["scripts/anatomy/q283/build_learn.py", "--check"], ["scripts/sync_learn_q283.py", "--check"]):
        r = run(*a)
        assert r.returncode == 0, (a, r.stdout + r.stderr)


def test_every_row_sign_matches_its_moment_arm_or_is_documented():
    """for every cited action row x joint dof: on the pages where the moment arm is computed, the computed sign agrees with the row
    on at least one structure -- or the disagreement is listed, with its reason, in muscle_audit_q293.json geometry_vs_textbook"""
    doc = AUD["geometry_vs_textbook"]
    tally = {}
    for key in KEYS:
        S = json.loads((DATA / f"moment_arms_{key}.json").read_text(encoding="utf-8"))["s"]
        for x in S.values():
            for c in x.get("cv") or []:
                k = f"{x['b']}|{c[0].rsplit('_', 1)[0]}|{c[1]}|{c[2]:+d}"
                t = tally.setdefault(k, {"agrees": 0, "disagrees": 0, "agrees at some angles": 0})
                t[c[3]] += 1
    assert tally, "no cited-action checks in the moment-arm data"
    bad = [k for k, t in tally.items() if t["agrees"] + t["agrees at some angles"] == 0 and k not in doc]
    assert not bad, bad
    for k in doc:
        assert doc[k].get("reason") and doc[k].get("kept"), k


def test_two_joint_muscles_have_rows_on_both_joints():
    rows = {}
    for r in ACT["rows"]:
        for mv in r["mv"]:
            js = mv[0] if isinstance(mv[0], list) else [mv[0]]
            for j in js:
                rows.setdefault(r["m"], set()).add((j, mv[1], mv[2]))
    need = {"rectus_femoris": {("hip", "flex", 1), ("knee", "flex", -1)},
            "semitendinosus": {("hip", "flex", -1), ("knee", "flex", 1)}, "semimembranosus": {("hip", "flex", -1), ("knee", "flex", 1)},
            "biceps_femoris": {("hip", "flex", -1), ("knee", "flex", 1)}, "gastrocnemius": {("knee", "flex", 1), ("ankle", "dp", -1)},
            "sartorius": {("hip", "flex", 1), ("knee", "flex", 1)}, "gracilis": {("hip", "abd", -1), ("knee", "flex", 1)},
            "biceps_brachii": {("shoulder", "flex", 1), ("elbow", "flex", 1)}, "triceps_brachii": {("shoulder", "flex", -1), ("elbow", "flex", -1)},
            "flexor_digitorum_superficialis": {("wrist", "flex", 1), ("f2_pip", "flex", 1), ("f2_mcp", "flex", 1)},
            "flexor_digitorum_profundus": {("wrist", "flex", 1), ("f2_dip", "flex", 1)},
            "extensor_digitorum": {("wrist", "flex", -1), ("f2_mcp", "flex", -1), ("f2_pip", "flex", -1)},
            "flexor_pollicis_longus": {("thumb_ip", "flex", 1), ("thumb_mcp", "flex", 1)}, "extensor_pollicis_longus": {("thumb_ip", "flex", -1), ("thumb_mcp", "flex", -1)}}
    for m, s in need.items():
        assert s <= rows.get(m, set()), (m, s - rows.get(m, set()))
    # TFL's knee action is stated as not animated, with its reason
    assert any(x["m"] == "tensor_fasciae_latae" and "knee" in x["what"] for x in ACT["not_animated"])


def test_rf_moment_arms_flex_hip_extend_knee_on_every_page():
    for key in KEYS:
        S = json.loads((DATA / f"moment_arms_{key}.json").read_text(encoding="utf-8"))["s"]
        for s in "rl":
            x = S.get(f"rectus_femoris_{s}")
            j = x["j"]
            if not j:            # Imaging pages: the RF mesh's ends touch no bone (Q284 'not computable', unchanged) -- Z pages must have both
                assert key.startswith("own") and any("touches no bone" in f for f in x["f"]), (key, s)
                continue
            assert j[f"hip_{s}"][3]["flex"][0] > 0, (key, s, j[f"hip_{s}"])
            if f"knee_{s}" in j:
                assert j[f"knee_{s}"][3]["flex"][0] < 0, (key, s, j[f"knee_{s}"])


def test_learn_simulation_sets_the_start_position_instead_of_animating_it():
    js = (REPO / "viewer/learn/learn.js").read_text(encoding="utf-8")
    assert "tr.v0 + (tr.from - tr.v0) * ease(t / A)" not in js           # the Q283 animated pre-position (knee flexed first)
    assert "if (t < A) return tr.from;" in js and "MIN_EXC" in js
    assert "!it.c || !r.c || r.c === it.c" in js                         # whole muscle 'All together' includes its parts' rows
    for t in ("viewer/atlas_viewer.template.html", "viewer/zan_atlas.template.html"):
        s = (REPO / t).read_text(encoding="utf-8")
        assert "if (t < A) return tr.from;" in s and "rectus_femoris_reflected_head" not in s.split("LEARN js begin")[0][-10:]


def test_rf_reflected_head_report():
    R = json.loads((REPO / "data/derived/Q293_rf_reflected_head.json").read_text(encoding="utf-8"))
    for c in ("ryan2014", "atzmon2019", "gursoy2024", "hapa2013", "hasselman1995"):
        assert R["cites"][c]["doi"] and R["cites"][c]["quote"]
    for key in KEYS:
        for s in "rl":
            o = R[f"{key}_{s}"]
            assert o["watertight"] and 0.5 < o["volume_cm3"] < 8, (key, s, o["volume_cm3"])
            assert o["bone_penetration"]["verts_inside_gt_0_5mm_after_pct"] == 0, (key, s)
            assert 25 < o["footprint_len_mm"] < 60 and 40 < o["total_len_mm"] < 100, (key, s)


def test_page_report_and_rigs_carry_the_new_structures():
    P = json.loads((REPO / "data/derived/Q293_page_report.json").read_text(encoding="utf-8"))
    for key in KEYS:
        rig = json.loads((DATA / f"pose_rig_{key}.json").read_text(encoding="utf-8"))["rig"]
        assert rig["count"] == max(P[key]["new_indices"]) + 1, key
        assert P[key]["added"] == ["rectus_femoris_reflected_head_r", "rectus_femoris_reflected_head_l"]


def test_fingers_reseated_and_index_refit():
    F = json.loads((REPO / "data/derived/Q293_fingers.json").read_text(encoding="utf-8"))
    for key in ("comb_m", "comb_f"):
        assert all(v["gap_after_mm"] < 0.01 for v in F[key]["joints"].values()), key
        assert max(v["gap_before_mm"] for v in F[key]["joints"].values()) > 5, key      # the defect that was there
    f2 = F["comb_m"]["fingers"]["f2_r"]
    assert f2["refit_accepted"] and f2["ct_median_mm_after"] < 3.5 and f2["ct_median_mm_before"] > 10
    for key in ("comb_m", "comb_f"):
        rig = json.loads((DATA / f"pose_rig_{key}.json").read_text(encoding="utf-8"))["rig"]
        assert "Q293" in rig["notes"] and "finger joints" in rig["notes"]
