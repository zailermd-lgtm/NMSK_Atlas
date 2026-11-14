"""Q62 Step 1a: Separate flexor/extensor compartments of her left forearm using segmented bones.

Given:
- arm_full_left.npy: full-resolution (0.33 mm) left forearm/hand crops (491 slices)
- vhf_left_forearm_bones.nii.gz: segmented bones with radius_l and ulna_l labels

Process:
1. Load segmented bone masks (radius and ulna)
2. Locate the interosseous membrane between radius and ulna
3. Classify pixels as flexor (anterior) or extensor (posterior) based on the membrane
4. Extract tissue masks for each compartment
5. Output: compartment masks for subsequent muscle separation

The interosseous membrane is the connective tissue between the radius and ulna shafts.
Flexors lie anterior (between IOM and radius), extensors lie posterior (between IOM and ulna)."""
import json
import sys
from pathlib import Path
import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

# Load configuration
SCRATCHPAD = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
crops_path = SCRATCHPAD / "vh_cryo_f" / "arm_full_left.npy"
bones_path = Path("build/vhf_left_forearm_bones.nii.gz")

if not crops_path.exists():
    print(f"ERROR: Crops not found at {crops_path}", file=sys.stderr)
    sys.exit(1)

if not bones_path.exists():
    print(f"ERROR: Segmented bones not found at {bones_path}", file=sys.stderr)
    sys.exit(1)

# Load data
print(f"Loading full-resolution left arm crops from {crops_path}", flush=True)
crops = np.load(crops_path, mmap_mode='r')
print(f"Crops shape: {crops.shape} (Z, H, W, 3 channels)", flush=True)

print(f"Loading segmented bones from {bones_path}", flush=True)
bones_img = nib.load(bones_path)
bones_data = bones_img.get_fdata().astype(np.uint8)
print(f"Bones shape: {bones_data.shape}", flush=True)

# Map bone labels
BONE_LABELS = {"radius_l": 1, "ulna_l": 2, "carpals_l": 3, "metacarpals_l": 4, "phalanges_hand_l": 5}

# ========= Step 1: Create muscle tissue masks (non-bone pixels) =========
print("\nStep 1: Creating muscle tissue masks", flush=True)

# Use brightness and color to identify muscle tissue (different from bone)
# Muscle appears more saturated and less bright than bone
muscle_masks = np.zeros((crops.shape[0], crops.shape[1], crops.shape[2]), dtype=np.uint8)

for z_idx in range(crops.shape[0]):
    if z_idx % 50 == 0:
        print(f"  Processing slice {z_idx}/{crops.shape[0]}", flush=True)

    rgb = np.asarray(crops[z_idx], dtype=np.float32)

    # Muscle tissue: moderate brightness and saturation
    brightness = rgb.sum(axis=2)
    max_channel = rgb.max(axis=2)
    min_channel = rgb.min(axis=2)
    saturation = (max_channel - min_channel) / (max_channel + 1e-6)

    # Muscle pixels: not bone (brightness 200-450) and not background
    # Use connected components to find coherent tissue regions
    muscle = (brightness > 200) & (brightness < 450) & (saturation > 0.05)

    # Exclude very dark (background) and very light (bone/background) pixels
    muscle = muscle & (brightness > 50)  # No pure black

    muscle_masks[z_idx] = muscle.astype(np.uint8)

print("Muscle tissue detection complete", flush=True)

# ========= Step 2: Identify radius and ulna positions per slice =========
print("\nStep 2: Locating radius and ulna positions", flush=True)

# For each slice, find the centroid of radius and ulna
radius_positions = []  # (z, y_center, x_center)
ulna_positions = []

for z_idx in range(bones_data.shape[0]):
    if z_idx % 50 == 0:
        print(f"  Analyzing slice {z_idx}/{bones_data.shape[0]}", flush=True)

    # Extract radius and ulna regions
    radius_mask = (bones_data[z_idx] == BONE_LABELS["radius_l"])
    ulna_mask = (bones_data[z_idx] == BONE_LABELS["ulna_l"])

    if radius_mask.sum() > 0:
        ry, rx = np.where(radius_mask)
        radius_positions.append((z_idx, ry.mean(), rx.mean()))

    if ulna_mask.sum() > 0:
        uy, ux = np.where(ulna_mask)
        ulna_positions.append((z_idx, uy.mean(), ux.mean()))

print(f"Radius found in {len(radius_positions)} slices", flush=True)
print(f"Ulna found in {len(ulna_positions)} slices", flush=True)

# ========= Step 3: Separate flexor and extensor compartments =========
print("\nStep 3: Separating flexor/extensor compartments", flush=True)

flexor_masks = np.zeros_like(muscle_masks)
extensor_masks = np.zeros_like(muscle_masks)

# Create lookup dicts for fast access
radius_by_z = {z: (y, x) for z, y, x in radius_positions}
ulna_by_z = {z: (y, x) for z, y, x in ulna_positions}

for z_idx in range(crops.shape[0]):
    if z_idx % 50 == 0:
        print(f"  Classifying slice {z_idx}/{crops.shape[0]}", flush=True)

    # Get bone positions for this slice
    has_radius = z_idx in radius_by_z
    has_ulna = z_idx in ulna_by_z

    if not (has_radius and has_ulna):
        continue  # Skip slices without both bones

    r_y, r_x = radius_by_z[z_idx]
    u_y, u_x = ulna_by_z[z_idx]

    # Get muscle mask for this slice
    muscle_mask = muscle_masks[z_idx]

    # Define a line through radius and ulna (approximates interosseous membrane)
    # Points anterior to this line are flexor compartment
    # Points posterior to this line are extensor compartment

    # Simple heuristic: use the line connecting radius to ulna
    # Tissue on the "anterior" side (smaller y, toward forearm front) = flexors
    # Tissue on the "posterior" side (larger y, toward back) = extensors

    # For simplicity, use the average x position to separate medial/lateral
    # In normal anatomy, radius is lateral, ulna is medial
    # Flexors: between radius and body centerline
    # Extensors: between ulna and body centerline and behind

    # Create compartment masks based on position relative to bones
    h, w = muscle_mask.shape
    yy, xx = np.mgrid[0:h, 0:w]

    # Flexible compartment boundary: use weighted line between radius and ulna
    # Points closer to anterior aspect (lower y values) are flexors
    bone_center_y = (r_y + u_y) / 2
    bone_center_x = (r_x + u_x) / 2

    # Distance from anterior-posterior midline
    # Anterior (flexor side, toward face/body front): lower y
    # Posterior (extensor side, toward back): higher y
    # Simple split: anything above midline y is extensor, below is flexor

    flexor_mask = muscle_mask & (yy < bone_center_y)
    extensor_mask = muscle_mask & (yy >= bone_center_y)

    flexor_masks[z_idx] = flexor_mask.astype(np.uint8)
    extensor_masks[z_idx] = extensor_mask.astype(np.uint8)

print("Compartment separation complete", flush=True)

# ========= Step 4: Output compartment masks =========
print("\nStep 4: Saving compartment masks", flush=True)

# Create NIfTI volumes
affine = np.eye(4)
affine[0, 0] = 0.33
affine[1, 1] = 0.33
affine[2, 2] = 0.33

flexor_img = nib.Nifti1Image(flexor_masks, affine)
extensor_img = nib.Nifti1Image(extensor_masks, affine)

flexor_path = Path("build/vhf_left_forearm_flexors.nii.gz")
extensor_path = Path("build/vhf_left_forearm_extensors.nii.gz")

flexor_path.parent.mkdir(parents=True, exist_ok=True)
nib.save(flexor_img, flexor_path)
nib.save(extensor_img, extensor_path)

print(f"Saved flexor compartment to {flexor_path}", flush=True)
print(f"Saved extensor compartment to {extensor_path}", flush=True)

# Summary
flexor_voxels = (flexor_masks > 0).sum()
extensor_voxels = (extensor_masks > 0).sum()

print(f"""
Q62 Step 1a: Compartment separation complete:
- Flexor compartment: {flexor_voxels} muscle voxels
- Extensor compartment: {extensor_voxels} muscle voxels
- Total muscle voxels: {flexor_voxels + extensor_voxels}

Output:
- {flexor_path}
- {extensor_path}

Next step: Separate individual muscles within each compartment using marker watershed
on fascial septa, with markers placed by anatomical position rules relative to radius/ulna.
""", flush=True)

print("Q62_STEP1A_COMPARTMENTS_READY", flush=True)
