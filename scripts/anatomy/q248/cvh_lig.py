"""Q248 (a): CVH (Wu et al. 2015, CC BY 4.0) anococcygeal and pubovesical ligaments carried onto the female pages with the Q235 bone registration (data/derived/Q235_cvh_to_vhf_transform.json: rigid + uniform scale x1.1067,
bone residual median 1.8 / p90 4.35 mm, side convention sx = -1), guarded like every other new structure.   python3 scripts/anatomy/q248/cvh_lig.py own_f|comb_f"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, trimesh
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO))
import lig_pages as PG, guards as GD  # noqa: E402
from scripts.anatomy.q235 import cvh  # noqa: E402

CVH = {15: ("anococcygeal_ligament_cvh", "Anococcygeal ligament (Chinese Visible Human)", "Ligamentum anococcygeum", "m"),
       29: ("pubovesical_ligament_cvh", "Pubovesical ligament (Chinese Visible Human)", "Ligamentum pubovesicale", "m")}


def run(key):
    d = json.loads((REPO / "data/derived/Q235_cvh_to_vhf_transform.json").read_text())
    s, R, t = d["scale"], np.array(d["rotation"]), np.array(d["translation_mm"])
    E = PG.load(key); bf = PG.BoneField(E); gd = GD.Guards(E)
    out = {}
    for i, (sid, name, latin, side) in CVH.items():
        V, F = cvh.load_raw(i); W, F2 = cvh.to_atlas(V, sx=-1, F=F)
        Y = s * W @ R.T + t
        if len(F2) > 6000:
            m = trimesh.Trimesh(Y, F2, process=False).simplify_quadric_decimation(face_count=5000); Y, F2 = np.asarray(m.vertices), np.asarray(m.faces)
        ids = bf.near(Y, [b for b, e in E.items() if e["sys"] == "bone" and "zfill" not in b], 15)
        sd, a, nr, pt = bf.signed(Y, ids)
        deep = sd < -1.0
        mv = 0.0
        if deep.any():
            mv = float((-sd[deep] + 0.2).max()); Y[deep] += nr[deep] * (-sd[deep] + 0.2)[:, None]
        ov, sk, why = gd.gate(Y, gate_soft=True)
        g = dict(vertices=len(Y), pushed_out_of_bone=int(deep.sum()), pushed_fraction=round(float(deep.mean()), 3), max_push_mm=round(mv, 2), skin_min_depth_mm=sk, soft_overlap=ov)
        if mv > 4.0 or deep.mean() > 0.15: why.append("bone penetration after registration: > 15 % of the vertices or > 4 mm")
        if sid.startswith("pubovesical"):
            hd = float(np.abs(bf.signed(Y, [b for b in ("hip_bone_l", "hip_bone_r") if b in E])[0]).min())
            g["min_distance_to_pubis_mm"] = round(hd, 1)
            if hd > 10.0: why.append(f"does not reach the pubic bone ({hd:.0f} mm away after the registration; the pubovesical ligament attaches to the pubis)")
        mm = trimesh.Trimesh(Y, F2, process=False)
        g["volume_cm3"] = round(abs(mm.volume) / 1000, 3) if mm.is_watertight else None
        g["watertight"] = bool(mm.is_watertight)
        out[sid] = dict(gates=g, held=why, status="ship" if not why else "held", name=name, latin=latin, V=Y, F=F2)
        print(key, sid, out[sid]["status"], why, g["volume_cm3"], ov["organ_fraction_deeper_3mm"], ov["top"])
    return out


if __name__ == "__main__":
    k = sys.argv[1]
    r = run(k)
    np.savez_compressed(REPO / f"data/derived/Q248_cvh_{k}.npz", **{f"{a}__v": b["V"] for a, b in r.items()}, **{f"{a}__f": b["F"] for a, b in r.items()})
    (REPO / f"data/derived/Q248_cvh_{k}.json").write_text(json.dumps({a: {x: y for x, y in b.items() if x not in ("V", "F")} for a, b in r.items()}, indent=1, default=float) + "\n")
