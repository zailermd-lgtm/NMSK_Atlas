"""Build the lower-limb lean envelopes of both bodies (see lean_envelope.py).

    python3 scripts/transfer/build_envelopes.py --male-html MALE.html --female-bundle build/viewer_f \
        --female-cryo-cls .../cryo_frame_cls.npy --origin-female 'x,y,z' \
        --out-male data/derived/lean_envelope_vhm.json --out-female data/derived/lean_envelope_vhf.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_html, read_bundle_dir, meshes_by_id  # noqa: E402
from scripts.transfer import lean_envelope as le  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--male-html", required=True)
    ap.add_argument("--female-bundle", default="build/viewer_f")
    ap.add_argument("--female-cryo-cls", required=True)
    ap.add_argument("--origin-female", default="7.769,-885.229,14.137")
    ap.add_argument("--out-male", default="data/derived/lean_envelope_vhm.json")
    ap.add_argument("--out-female", default="data/derived/lean_envelope_vhf.json")
    ap.add_argument("--frame-correction", default="data/derived/vhf_cryo_frame_y_correction.json")
    a = ap.parse_args()
    mp = Path(a.male_html); bm, blob = read_bundle_dir(mp) if mp.is_dir() else read_bundle_html(mp); M = meshes_by_id(bm, blob)
    bf, blobf = read_bundle_dir(a.female_bundle); F = meshes_by_id(bf, blobf)

    bones_m = {k: M[k]["v"] for k in ("femur_r", "femur_l", "tibia_r", "tibia_l")}
    bones_f = {k: F[k]["v"] for k in ("femur_r", "femur_l", "tibia_r", "tibia_l")}
    mus = {"right": [], "left": []}
    for k, m in M.items():
        if m["cat"] == "muscle" and m["subject"] == "vhm_both" and (m.get("rec") or {}).get("region") == "lower_limb":
            side = "right" if k.endswith("_r") else "left"
            mus[side].append(m["v"])
    mus = {s: np.concatenate(v) for s, v in mus.items()}
    tab_m = {s: le.source_envelopes({s[0]: mus[s]}, bones_m, s[0]) for s in ("right", "left")}
    le.save(tab_m, a.out_male, "Visible Human male: outer boundary of his segmented lower-limb muscles (DU release) per "
            "10 mm level and 36 directions about the femur (above the knee) / tibia centre; atlas mm. Source side of the "
            "cross-subject transfer (scripts/transfer/lean_envelope.py).")

    cls = np.load(a.female_cryo_cls, mmap_mode="r")
    frame = json.load(open(Path(a.female_cryo_cls).parent / "frame.json"))
    origin = [float(t) for t in a.origin_female.split(",")]
    corr = json.load(open(a.frame_correction)) if a.frame_correction and Path(a.frame_correction).exists() else None
    tab_f = {s: le.target_envelopes_from_cryo(cls, frame, origin, F["skin"]["v"], bones_f, s[0], corr=corr) for s in ("right", "left")}
    le.save(tab_f, a.out_female, "Visible Human female: muscle-compartment radius per 10 mm level and 36 directions = "
            "(outermost muscle-class pixel / outermost tissue pixel along the ray in her registered cryosections, q) x her "
            "skin-mesh radius; about the femur / tibia centre; atlas mm. Target side of the cross-subject transfer.")
    for s in ("right", "left"):
        print(s)
        for y in sorted(tab_m[s], reverse=True)[::4]:
            rm = np.array(tab_m[s][y]["r"]); e = tab_f[s].get(y)
            if e is None:
                print(f"  y {y:6.0f} male R mean {np.nanmean(rm):5.1f}   (female: no level)"); continue
            rf, q, sk = np.array(e["r"]), np.array(e["q"]), np.array(e["skin_r"])
            print(f"  y {y:6.0f} male R mean {np.nanmean(rm):5.1f}  female R mean {np.nanmean(rf):5.1f}  q {np.nanmean(q):.2f}  skin {np.nanmean(sk):5.1f}  "
                  f"ant/post/lat/med male {rm[27]:.0f}/{rm[9]:.0f}/{rm[18 if s=='right' else 0]:.0f}/{rm[0 if s=='right' else 18]:.0f} "
                  f"female {rf[27]:.0f}/{rf[9]:.0f}/{rf[18 if s=='right' else 0]:.0f}/{rf[0 if s=='right' else 18]:.0f}")


if __name__ == "__main__":
    main()
