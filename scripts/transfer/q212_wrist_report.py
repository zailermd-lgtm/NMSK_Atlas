#!/usr/bin/env python3
"""Q212: numbers of the two wrist items -> data/derived/Q212_wrist_report.json
 (a) HIS wrist re-segmentation (segmentation stats, mesh stats, photograph agreement, truncation vs Z page, bone-bone gap / penetration before -> after from the Q198 junction audits);
 (b) HER left wrist 9.0 mm gap: mesh-to-mesh vs evidence-to-evidence gap in her left-hand photographs (Q192 evidence), the reason nothing is moved."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle
from scripts.transfer.q200_geom import sample_surface
D = REPO / "data/derived"
rep = {}
his = {}
for sd in "rl":
    s = np.load(REPO / f"build/q212/wrist_seg_{sd}.npz"); m = np.load(REPO / f"build/q212/wrist_mesh_{sd}.npz")
    his[sd] = dict(segmentation=json.loads(str(s["stats"])), meshes=json.loads(str(m["info"])))
for key, f in (("before_q203", "Q203_model_own_m_after.json"), ("after_q212", "Q212_model_own_m_after212.json")):
    d = json.loads((D / f).read_text())
    for j in d["junctions"]:
        if j["name"] == "wrist":
            his.setdefault("junction_audit", {}).setdefault(key, {})[j["side"]] = dict(gap_mm=j["bones"]["surface_gap_mm"], penetration_mm3=j["bones"]["penetration_vol_mm3"],
                                                                                    pairs=[(p["a"], p["b"], p["vol_mm3"], p["max_depth_mm"]) for p in j["bones"]["penetrations"]])
his["truncation_vs_Z_page"] = json.loads((D / "Q212_wrist_truncation_vhm.json").read_text())
rep["his_wrist"] = his
# (b) her left wrist
E = np.load(D / "Q192_left_hand_evidence.npz"); u = float(E["unit_mm"])
ev = np.vstack([E["hand"], E["forearm"]]).astype(float) * u
B = Bundle(REPO / "build/viewer_f_hr_q212")
M = {it["e"]["id"]: B.mesh(it) for it in B.items if it["e"]["id"] in ("radius_l", "ulna_l", "carpals_l")}
S = {k: sample_surface(*v, 20000, 1) for k, v in M.items()}
T = {k: cKDTree(p) for k, p in S.items()}
d = {k: T[k].query(ev)[0] for k in T}
car = ev[(d["carpals_l"] < 3) & (d["radius_l"] > 4) & (d["ulna_l"] > 4)]
her = {}
for nm in ("radius", "ulna"):
    X = ev[(d[nm + "_l"] < 3) & (d["carpals_l"] > 4)]
    dd = cKDTree(car).query(X)[0]
    her[nm] = dict(evidence_gap_min_mm=round(float(dd.min()), 2), evidence_gap_p1_mm=round(float(np.percentile(dd, 1)), 2), mesh_gap_min_mm=round(float(cKDTree(S["carpals_l"]).query(S[nm + "_l"])[0].min()), 2))
her["carpal_evidence_to_carpals_mesh_median_mm"] = round(float(np.median(T["carpals_l"].query(car)[0])), 2)
her["registration_error_note"] = "Q192: photograph frame +-3 mm, bones verified at 1-4 mm; evidence precision ~50 %, thin cream edges missing"
rep["her_left_wrist"] = her
(D / "Q212_wrist_report.json").write_text(json.dumps(rep, indent=1, default=str))
print(json.dumps(her, indent=1))
print(json.dumps(his["junction_audit"], indent=0)[:800])
