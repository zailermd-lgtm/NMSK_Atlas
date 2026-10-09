"""Q62 Step 1b: Separate individual forearm muscles within compartments using marker watershed.

Given:
- vhf_left_forearm_flexors.nii.gz and extensors.nii.gz from Step 1a
- vhf_left_forearm_bones.nii.gz with segmented radius and ulna
- arm_full_left.npy: full-resolution crops for visual guidance

Process:
1. Load compartment masks and bone positions
2. Define anatomical position rules for muscle marker placement
3. Apply marker-based watershed within each compartment
4. Identify individual muscle regions
5. Output labeled volume for each compartment

Forearm muscles (20 total across flexor/extensor):
FLEXOR (8): pronator_teres, flexor_carpi_radialis, flexor_carpi_ulnaris,
            palmaris_longus, flexor_digitorum_superficialis, flexor_digitorum_profundus,
            flexor_pollicis_longus, pronator_quadratus
EXTENSOR (11): brachioradialis, anconeus, extensor_carpi_radialis_longus,
               extensor_carpi_radialis_brevis, extensor_digitorum,
               extensor_digiti_minimi, extensor_carpi_ulnaris,
               abductor_pollicis_longus, extensor_pollicis_brevis,
               extensor_pollicis_longus, extensor_indicis
SUPINATOR (1): supinator (between compartments)

Strategy: Use anatomical landmarks (radius, ulna, interosseous membrane) to define
regions where specific muscles are expected based on depth, position, and size."""
import json
import sys
from pathlib import Path
import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

# Load configuration
BUILD = Path("build")
flexor_path = BUILD / "vhf_left_forearm_flexors.nii.gz"
extensor_path = BUILD / "vhf_left_forearm_extensors.nii.gz"
bones_path = BUILD / "vhf_left_forearm_bones.nii.gz"
crops_path = Path("/tmp/claude-0/-home-user-NMSK_Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad") / "vh_cryo_f" / "arm_full_left.npy"

if not all([flexor_path.exists(), extensor_path.exists(), bones_path.exists()]):
    print(f"ERROR: Required input files not found", file=sys.stderr)
    sys.exit(1)

# Load data
print(f"Loading compartment masks and bones", flush=True)
flexor_img = nib.load(flexor_path)
flexor_mask = flexor_img.get_fdata().astype(np.uint8)
extensor_img = nib.load(extensor_path)
extensor_mask = extensor_img.get_fdata().astype(np.uint8)
bones_img = nib.load(bones_path)
bones_data = bones_img.get_fdata().astype(np.uint8)

crops = np.load(crops_path, mmap_mode='r') if crops_path.exists() else None

print(f"Flexor mask shape: {flexor_mask.shape}", flush=True)
print(f"Extensor mask shape: {extensor_mask.shape}", flush=True)
print(f"Bones shape: {bones_data.shape}", flush=True)

# Define muscle label maps
FLEXOR_MUSCLES = {
    "pronator_teres": 1,
    "flexor_carpi_radialis": 2,
    "flexor_carpi_ulnaris": 3,
    "palmaris_longus": 4,
    "flexor_digitorum_superficialis": 5,
    "flexor_digitorum_profundus": 6,
    "flexor_pollicis_longus": 7,
    "pronator_quadratus": 8
}

EXTENSOR_MUSCLES = {
    "brachioradialis": 101,
    "anconeus": 102,
    "extensor_carpi_radialis_longus": 103,
    "extensor_carpi_radialis_brevis": 104,
    "extensor_digitorum": 105,
    "extensor_digiti_minimi": 106,
    "extensor_carpi_ulnaris": 107,
    "abductor_pollicis_longus": 108,
    "extensor_pollicis_brevis": 109,
    "extensor_pollicis_longus": 110,
    "extensor_indicis": 111
}

# ========= Step 1: Locate radius and ulna per slice =========
print("\nStep 1: Locating bone positions for marker placement", flush=True)

radius_positions = {}
ulna_positions = {}
for z_idx in range(bones_data.shape[0]):
    radius_mask = (bones_data[z_idx] == 1)  # radius_l
    ulna_mask = (bones_data[z_idx] == 2)    # ulna_l

    if radius_mask.sum() > 0:
        ry, rx = np.where(radius_mask)
        radius_positions[z_idx] = (ry.mean(), rx.mean())

    if ulna_mask.sum() > 0:
        uy, ux = np.where(ulna_mask)
        ulna_positions[z_idx] = (uy.mean(), ux.mean())

print(f"Radius found in {len(radius_positions)} slices", flush=True)
print(f"Ulna found in {len(ulna_positions)} slices", flush=True)

# ========= Step 2: Separate muscles within each compartment =========
print("\nStep 2: Separating individual muscles within compartments", flush=True)

flexor_labeled = np.zeros_like(flexor_mask)
extensor_labeled = np.zeros_like(extensor_mask)

# Process each slice to separate muscles based on position
for z_idx in range(flexor_mask.shape[0]):
    if z_idx % 50 == 0:
        print(f"  Processing slice {z_idx}/{flexor_mask.shape[0]}", flush=True)

    flexor_z = flexor_mask[z_idx]
    extensor_z = extensor_mask[z_idx]

    if flexor_z.sum() < 10 and extensor_z.sum() < 10:
        continue

    # Get bone positions for anatomical reference
    has_radius = z_idx in radius_positions
    has_ulna = z_idx in ulna_positions

    if not (has_radius and has_ulna):
        continue

    r_y, r_x = radius_positions[z_idx]
    u_y, u_x = ulna_positions[z_idx]

    # ===== Flexor compartment subdivision =====
    # Flexors are organized radially (superficial to deep):
    # - Pronator teres: proximal, superficial
    # - Flexor carpi radialis: superficial lateral
    # - Flexor digitorum superficialis: middle
    # - Flexor digitorum profundus: deep/posterior
    # - Flexor pollicis longus: deep lateral
    # - Flexor carpi ulnaris: superficial medial
    # - Palmaris longus: superficial middle
    # - Pronator quadratus: deep, distal

    # Connected components in flexor compartment
    if flexor_z.sum() > 0:
        labeled_f, n_comp_f = ndi.label(flexor_z, structure=ndi.generate_binary_structure(2, 2))

        for comp_id in range(1, n_comp_f + 1):
            comp_mask = (labeled_f == comp_id)
            comp_area = comp_mask.sum()

            if comp_area < 5:
                continue

            # Get component position and size
            comp_y, comp_x = np.where(comp_mask)
            comp_center_y, comp_center_x = comp_y.mean(), comp_x.mean()
            comp_size_y = comp_y.max() - comp_y.min()
            comp_size_x = comp_x.max() - comp_x.min()

            # Assign muscle based on position relative to radius and ulna
            # Simple heuristic: distance from radius determines proximal-distal
            # Position relative to midline determines medial-lateral

            dist_from_radius = np.sqrt((comp_center_y - r_y)**2 + (comp_center_x - r_x)**2)
            dist_from_ulna = np.sqrt((comp_center_y - u_y)**2 + (comp_center_x - u_x)**2)

            # Closer to radius: pronator teres, FDS, FPL, FCR
            # Closer to ulna: FCU, flexor digitorum profundus
            # Middle/deep: palmaris longus
            # Distal: pronator quadratus

            if z_idx < 100:  # Proximal
                muscle_label = FLEXOR_MUSCLES.get("pronator_teres", 1)
            elif dist_from_radius < dist_from_ulna:
                if comp_size_y > 30:
                    muscle_label = FLEXOR_MUSCLES.get("flexor_digitorum_superficialis", 5)
                else:
                    muscle_label = FLEXOR_MUSCLES.get("flexor_carpi_radialis", 2)
            else:
                if comp_area > 50:
                    muscle_label = FLEXOR_MUSCLES.get("flexor_digitorum_profundus", 6)
                else:
                    muscle_label = FLEXOR_MUSCLES.get("flexor_carpi_ulnaris", 3)

            flexor_labeled[z_idx][comp_mask] = muscle_label

    # ===== Extensor compartment subdivision =====
    # Extensors are organized posteriorly:
    # - Brachioradialis: most lateral/anterior
    # - ECRB, ECRL: lateral
    # - Extensor digitorum: central
    # - Extensor carpi ulnaris: medial
    # - Anconeus: proximal
    # - APL, EPB, EPL: thumb group, posterior
    # - Extensor indicis: distal, deep

    if extensor_z.sum() > 0:
        labeled_e, n_comp_e = ndi.label(extensor_z, structure=ndi.generate_binary_structure(2, 2))

        for comp_id in range(1, n_comp_e + 1):
            comp_mask = (labeled_e == comp_id)
            comp_area = comp_mask.sum()

            if comp_area < 5:
                continue

            comp_y, comp_x = np.where(comp_mask)
            comp_center_y, comp_center_x = comp_y.mean(), comp_x.mean()

            # Lateral: brachioradialis
            # Central: extensor digitorum
            # Medial: extensor carpi ulnaris
            # Posterior: thumb extensors

            # Use x position to determine medial-lateral
            x_relative = comp_center_x - r_x

            if z_idx < 50 and comp_area < 30:
                muscle_label = EXTENSOR_MUSCLES.get("anconeus", 102)
            elif x_relative < -20:
                muscle_label = EXTENSOR_MUSCLES.get("extensor_carpi_ulnaris", 107)
            elif x_relative > 20:
                muscle_label = EXTENSOR_MUSCLES.get("brachioradialis", 101)
            else:
                muscle_label = EXTENSOR_MUSCLES.get("extensor_digitorum", 105)

            extensor_labeled[z_idx][comp_mask] = muscle_label

print("Muscle separation complete", flush=True)

# ========= Step 3: Output labeled volumes =========
print("\nStep 3: Saving labeled muscle volumes", flush=True)

affine = np.eye(4)
affine[0, 0] = 0.33
affine[1, 1] = 0.33
affine[2, 2] = 0.33

flexor_out = nib.Nifti1Image(flexor_labeled.astype(np.uint8), affine)
extensor_out = nib.Nifti1Image(extensor_labeled.astype(np.uint8), affine)

flexor_out_path = BUILD / "vhf_left_forearm_flexor_muscles.nii.gz"
extensor_out_path = BUILD / "vhf_left_forearm_extensor_muscles.nii.gz"

nib.save(flexor_out, flexor_out_path)
nib.save(extensor_out, extensor_out_path)

print(f"Saved flexor muscles to {flexor_out_path}", flush=True)
print(f"Saved extensor muscles to {extensor_out_path}", flush=True)

# Summary
n_flexor_labels = len(np.unique(flexor_labeled[flexor_labeled > 0]))
n_extensor_labels = len(np.unique(extensor_labeled[extensor_labeled > 0]))

print(f"""
Q62 Step 1b: Muscle separation complete (initial pass):
- Flexor compartment: {n_flexor_labels} muscle regions identified
- Extensor compartment: {n_extensor_labels} muscle regions identified

Output:
- {flexor_out_path}
- {extensor_out_path}

Note: Initial anatomical-rule-based separation. Refinement needed:
- Marker watershed with refined placement rules per muscle
- Cross-validation against anatomy references
- Volume checking against textbook ranges
- Per-muscle individual separation instead of compartment-level classification

This provides the framework for iterative refinement.
""", flush=True)

print("Q62_STEP1B_MUSCLES_INITIALIZED", flush=True)
