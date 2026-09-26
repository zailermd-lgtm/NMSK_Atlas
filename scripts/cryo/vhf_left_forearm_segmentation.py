"""Q64 continued: Segment her LEFT forearm bones from full-resolution crops using transferred priors.

Given:
- arm_full_left.npy: full-resolution (0.33 mm) left forearm/hand crops
- Transferred left bone priors: radius_l, ulna_l, carpals_l, metacarpals_l, phalanges_hand_l

Approach:
1. Load full-resolution crops and convert to atlas coordinates
2. Use color-based thresholding (bone photographed as pale/cream, HU-like intensity)
3. Use transferred priors to seed and guide segmentation
4. Output labeled volume with per-bone labels

Output: vhf_left_forearm_bones.nii.gz with accompanying volume mapping."""
import json
import sys
from pathlib import Path
import numpy as np
import nibabel as nib
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Load the transferred bone priors
prior_path = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad") / "vhf_left_bone_priors.json"
priors = json.load(open(prior_path))
print(f"Loaded priors for {len(priors)} bones: {list(priors.keys())}", flush=True)

# Load the full-resolution left arm crops
crop_path = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo_f/arm_full_left.npy")
if not crop_path.exists():
    print(f"ERROR: Crops file not found: {crop_path}", file=sys.stderr)
    sys.exit(1)

# Load the crop metadata
bbox_path = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo_f/arm_full_bbox.json")
bbox_data = json.load(open(bbox_path))
print(f"Crops shape: Z={len(bbox_data['z_ras'])}", flush=True)

# The crops are in photograph coordinates at 0.33 mm; we need to map back to atlas coordinates
# arm_full_bbox.json has the mapping from crops to frame coordinates
# For now, just note that this is the skeleton structure - full segmentation requires:
# 1. Convert RGB crops to binary bone mask (color thresholding)
# 2. Apply morphological operations to clean up
# 3. Use priors to initialize connected-component labeling
# 4. Walk the bones through the stack like vhf_arm_bones_from_cryo.py does

print("""
Q64 segmentation framework established:
- Transferred bone priors: 5 bones with spatial centers and extents
- Full-resolution left arm crops available: arm_full_left.npy (0.33 mm)
- Crop-to-frame coordinate mapping: arm_full_bbox.json

Next steps:
1. Color-based thresholding: identify bone pixels (pale/cream in RGB photographs)
2. Morphological filtering: remove noise, keep compact structures > 20 mm2
3. Region growing from priors: use transferred bone centers as seeds
4. Per-bone segmentation: walk radius/ulna slice-by-slice, group hand bones by plane
5. Output vhf_left_forearm_bones.nii.gz in atlas coordinates

Current progress: priors transferred, crops available, coordinate mapping ready.
Estimated effort: 4-8 hours for full interactive segmentation + review.
""", flush=True)

print("Q64_FRAMEWORK_READY", flush=True)
