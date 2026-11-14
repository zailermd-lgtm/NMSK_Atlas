#!/usr/bin/env python3
"""Q250: the Q233 dimorphism measures (scripts/anatomy/q233/dimorphism.py) on any set of page dirs -> JSON.
    python3 scripts/anatomy/q250/measure.py OUT.json key=pagedir [key=pagedir ...]       key in own_m own_f base_m base_f comb_m comb_f
Same code and same landmark rules as Q233, so the numbers are comparable with data/derived/Q233_measures.json."""
import json, os, sys
import numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import q233_load as Q  # noqa: E402
from scripts.anatomy.q233 import dimorphism as D  # noqa: E402


def app_tilt(S):
    """rotation about the X axis (rad) that makes the anatomical pelvic plane (both ASIS-like points + the upper symphysis) vertical (Z-normal); S = Q233 loader structures"""
    from scripts.anatomy.q250 import pelvis_reg as PR
    ring = {x["id"]: (np.asarray(x["v"]), x["f"]) for x in S if x["id"] in ("hip_bone_l", "hip_bone_r")}
    lm = PR.landmarks(ring)
    sym = 0.5 * (lm["symU_l"] + lm["symU_r"])
    a, b = lm["asis_l"], lm["asis_r"]
    n = np.cross(b - a, sym - 0.5 * (a + b)); n /= np.linalg.norm(n)
    if n[2] < 0: n = -n
    return float(np.arctan2(n[1], n[2]))            # tilt of the plane normal out of the horizontal Z axis, about X


def rotated(S, ang):
    c, s = np.cos(ang), np.sin(ang)
    R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])       # rotates (y, z): normal (0, ny, nz) -> (0, 0, 1)
    ctr = np.mean([x["v"].mean(0) for x in S if x["id"] in ("hip_bone_l", "hip_bone_r")], 0)
    return [dict(x, v=(np.asarray(x["v"]) - ctr) @ R.T + ctr) for x in S]


def measure_app(S):
    """the same measures after rotating the pelvis about X into the anatomical pelvic plane (removes the pelvic-tilt dependence of the landmark rules)"""
    ang = app_tilt(S)
    r = measure(rotated(S, -ang)); r["pelvic_tilt_removed_deg"] = round(float(np.degrees(ang)), 1)
    return r


def sciatic_notch_dense(S, n=60000):
    """the Q233 hull-defect notch angle, but on dense surface samples (the Z-Anatomy hip bones are coarse meshes of 1.9 k vertices whose jagged border makes the vertex-based value jump by +-20 deg)"""
    from scripts.anatomy.q250 import lib as L
    from scripts.anatomy.q233 import dimorphism as DD
    S2 = []
    for x in S:
        if x["id"].split("#")[0] in ("hip_bone_l", "hip_bone_r") and x["sys"] == "bone":
            p, _ = L.sample(np.asarray(x["v"]), np.asarray(x["f"]), n)
            S2.append(dict(x, v=p, f=np.zeros((0, 3), int)))
        else:
            S2.append(x)
    class _B:                                           # dimorphism.bone() needs triangle meshes: give it point clouds as degenerate meshes
        pass
    import trimesh
    orig = DD.bone
    def bone_pc(SS, base, side=None):
        for x in SS:
            if x["id"].split("#")[0] == base and x["sys"] == "bone":
                return trimesh.PointCloud(np.asarray(x["v"])) if False else type("M", (), {"vertices": np.asarray(x["v"])})()
        return None
    DD.bone = bone_pc
    try:
        return DD.sciatic_notch(S2)
    finally:
        DD.bone = orig


def measure(S):
    r = {}
    for f in (D.pelvis_size, D.outlet_and_subpubic, D.inlet, D.sacrum_metrics, D.ischiopubic, sciatic_notch_dense, D.sternum_metrics, D.shoulder_hip):
        try:
            r.update(f(S))
        except Exception as e:  # noqa: BLE001
            r[f.__name__ + "_error"] = str(e)
    try:                                                   # the Q233 vertex-based value, kept for continuity (unstable on coarse meshes: see sciatic_notch_dense)
        v = D.sciatic_notch(S)
        r["sciatic_notch_hull_angle_vertex_based_deg"] = v.get("sciatic_notch_hull_angle_deg")
    except Exception:  # noqa: BLE001
        pass
    for sd in "rl":
        fm = D.femur_metrics(S, sd)
        r[f"femoral_head_diameter_{sd}_mm"] = fm.get("femoral_head_diameter_mm"); r[f"bicondylar_breadth_{sd}_mm"] = fm.get("bicondylar_breadth_mm"); r[f"femur_length_{sd}_mm"] = fm.get("femur_length_mm")
        r[f"q_angle_{sd}_deg"] = D.q_angle(S, sd).get("q_angle_deg")
    try:
        a, b = D.femur_metrics(S, "r")["head_centre"], D.femur_metrics(S, "l")["head_centre"]
        r["bi_acetabular_distance_mm"] = round(abs(a[0] - b[0]), 1)
    except Exception:  # noqa: BLE001
        r["bi_acetabular_distance_mm"] = None
    return {a: b for a, b in r.items() if not a.startswith("tuber_")}


if __name__ == "__main__":
    out = {}
    for kv in sys.argv[2:]:
        k, d = kv.split("=", 1)
        os.environ["Q233_SRC_" + k] = d
        S = Q.load(k)
        out[k] = measure(S); out[k]["page_dir"] = d
        print(k, flush=True)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=float) + "\n")
