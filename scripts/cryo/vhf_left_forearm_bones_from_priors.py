"""Q64: Her LEFT forearm bones (radius, ulna, carpals, metacarpals, phalanges).

The female's left forearm lies outside her CT field of view, so there's no direct
bone geometry to segment. Instead, we use the male's complete left forearm/hand bones
as shape priors, transferred to her frame via her left humerus (which exists in her CT).

Process:
1. Transfer his left forearm/hand bones to her frame (driven by humerus affine)
2. Use those as +-10 mm priors for the bone discs in her full-res left forearm/hand crops
3. Trace her own bone surfaces from the photographs at full resolution (0.33 mm)

Output: vhf_left_forearm_bones.nii.gz, with per-bone labels and a volume mapping."""
import json
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer.bundle_io import read_bundle_html, meshes_by_id
from scripts.transfer.bone_frames import bone_frame, bone_affine

# The bones we're segmenting on her left side
LEFT_FOREARM_BONES = ["radius_l", "ulna_l", "carpals_l", "metacarpals_l", "phalanges_hand_l"]

def transfer_left_bones_to_female():
    """Transfer male's left forearm/hand bones to female frame, driven by humerus."""

    # Load male geometry (source)
    male_bundle, male_blob = read_bundle_html(Path("build/viewer_m/atlas_viewer_male.html"))
    male_meshes = meshes_by_id(male_bundle, male_blob)

    # Load female geometry (target)
    female_bundle, female_blob = read_bundle_html(Path("build/viewer_f/atlas_viewer_female.html"))
    female_meshes = meshes_by_id(female_bundle, female_blob)

    # Build the affine from male's left humerus to female's left humerus
    # This drives the position of all arm structures on the left side
    if "humerus_l" not in male_meshes or "humerus_l" not in female_meshes:
        print("ERROR: Left humerus not found in both bundles", file=sys.stderr)
        return False

    m_hum_v = np.vstack(male_meshes["humerus_l"]["v"])
    f_hum_v = np.vstack(female_meshes["humerus_l"]["v"])

    # Frame-based affine: fit principal axes on the humerus of each body
    m_frame = bone_frame(m_hum_v, clip_top_mm=200.0)  # truncated bones use proximal 200 mm
    f_frame = bone_frame(f_hum_v, clip_top_mm=200.0)
    A, t = bone_affine(m_frame, f_frame, uniform=True)

    print(f"Humerus affine: det(A)={np.linalg.det(A):.4f}")
    print(f"Translation: {t}", flush=True)

    # Apply this affine to his left forearm/hand bones to get priors
    priors = {}
    for bone_id in LEFT_FOREARM_BONES:
        if bone_id not in male_meshes:
            print(f"WARNING: {bone_id} not in male meshes", file=sys.stderr)
            continue

        v_src = np.vstack(male_meshes[bone_id]["v"])
        # Apply affine: v_dst = A @ v_src + t
        v_dst = v_src @ A.T + t[np.newaxis, :]
        priors[bone_id] = v_dst

        # Print info about the transfer
        src_center = v_src.mean(axis=0)
        dst_center = v_dst.mean(axis=0)
        src_extent = v_src.max(axis=0) - v_src.min(axis=0)
        dst_extent = v_dst.max(axis=0) - v_dst.min(axis=0)

        print(f"{bone_id}: {len(v_src)} vertices")
        print(f"  Source center: {src_center}, extent: {src_extent}")
        print(f"  Target center: {dst_center}, extent: {dst_extent}")
        print(f"  Scale: {dst_extent / (src_extent + 1e-6)}", flush=True)

    return priors

def main():
    priors = transfer_left_bones_to_female()
    if not priors:
        sys.exit(1)

    # Export the priors as a JSON for inspection
    prior_summary = {}
    for bone_id, vertices in priors.items():
        center = vertices.mean(axis=0)
        extent = (vertices.max(axis=0) - vertices.min(axis=0)).tolist()
        prior_summary[bone_id] = {
            "n_vertices": len(vertices),
            "center": center.tolist(),
            "extent": extent,
            "note": f"Transferred from male's {bone_id} using humerus-driven affine"
        }

    summary_path = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad") / "vhf_left_bone_priors.json"
    json.dump(prior_summary, open(summary_path, "w"), indent=2)
    print(f"Saved prior summary to {summary_path}", flush=True)

if __name__ == "__main__":
    main()
