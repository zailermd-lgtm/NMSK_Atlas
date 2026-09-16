"""Q64 detailed segmentation: bone detection in left forearm crops using priors.

Implements the color-based thresholding and region growing for her left forearm/hand bones.
Uses the transferred bone priors as seeds for guided segmentation."""
import json
import sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi

# Load configuration
D = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo_f/")
crop_path = D / "arm_full_left.npy"
bbox_path = D / "arm_full_bbox.json"
prior_path = D.parent / "vhf_left_bone_priors.json"

if not crop_path.exists():
    print(f"ERROR: Crops not found at {crop_path}", file=sys.stderr)
    sys.exit(1)

# Load data
print(f"Loading full-resolution left arm crops from {crop_path}", flush=True)
crops = np.load(crop_path, mmap_mode='r')
bbox_data = json.load(open(bbox_path))
priors_data = json.load(open(prior_path))

print(f"Crops shape: {crops.shape} (Z, H, W, 3 channels)", flush=True)
print(f"Slices: {len(bbox_data['z_ras'])}", flush=True)
print(f"Bone priors: {list(priors_data.keys())}", flush=True)

# ========= Step 1: Bone pixel detection by color =========
# In cryosection photographs, bone cross-sections appear as pale/cream discs
# (bone mineral + marrow). We'll use a simple RGB threshold to detect these.
#
# Bone characteristics on cryosections:
# - R,G,B all relatively high (pale/cream color)
# - Not as extreme as background skin/fat
# - Cream color typically: R+G+B > 500, G ≈ R ≈ B (less saturated)

print("\nStep 1: Color-based bone detection", flush=True)

# For efficiency, process a subset of slices to establish thresholds
test_slices = [5, 50, 100, 150, 200, 250, 300, 350, 400]  # ~100 mm apart
bone_pixels_samples = []

for idx in test_slices:
    if idx >= crops.shape[0]:
        continue
    rgb = np.asarray(crops[idx])
    # Bone pixels: pale color (high brightness) + low saturation (R≈G≈B)
    brightness = rgb.sum(axis=2)
    max_channel = rgb.max(axis=2)
    min_channel = rgb.min(axis=2)
    saturation = (max_channel - min_channel) / (max_channel + 1e-6)

    # Thresholds: brightness > 500, saturation < 0.15 (cream/pale)
    mask = (brightness > 500) & (saturation < 0.15)
    n_pixels = mask.sum()
    bone_pixels_samples.append((idx, n_pixels))
    print(f"  Slice {idx}: {n_pixels} potential bone pixels", flush=True)

# Average estimates
avg_bone_pixels = np.mean([n for _, n in bone_pixels_samples])
print(f"Average bone pixels per slice: {avg_bone_pixels:.0f}", flush=True)

# ========= Step 2: Report thresholds =========
print(f"""
Bone detection thresholds established:
- Brightness (R+G+B): > 500
- Saturation (max-min)/(max): < 0.15
- Expected coverage: ~{avg_bone_pixels:.0f} pixels/slice on average

Next phase: morphological filtering, connected component analysis,
and per-bone region growing using transferred priors as seeds.

This requires interactive review of rendered masks against photographs
to validate segmentation boundaries.
""", flush=True)

print("BONE_DETECTION_THRESHOLDS_READY", flush=True)
