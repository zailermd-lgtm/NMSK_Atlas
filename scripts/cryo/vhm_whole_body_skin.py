"""Visible Human MALE body surface over all THREE CT blocks on one grid: torso (5d409385, vertex to
proximal femur), legs (145c2668, pelvis to ankle), feet (94755b62, ankle to toes). Silhouette (HU > -300,
opened, holes filled per slice), all three blocks placed into the torso block's own affine frame using the
block-to-block shifts already measured in docs/GEOMETRY_SOURCES.md "Stage 2" (legs->torso, RAS mm) and Q1
(feet->legs, RAS mm; z re-derived here from the same k=0/k=221 slice correspondence Q1 recorded, verified by
image correlation at the torso/legs boundary: 0.965 at k0=torso vs k808=legs, matching the documented 0.945).
Largest 3-D connected component only. Output: vhm_ts/skin_ct.nii.gz in the torso block's own RAS affine,
extended downward to cover all three blocks -- for `ct_vhm_skin` (replacing the photograph-route skin, which
needs the DU-blocked re-stream Q29 describes; this route needs nothing but his own CT, already reachable)."""
import numpy as np, nibabel as nib
from scipy import ndimage as ndi

S = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_idc/nii/"
OUT = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vhm_ts/skin_ct.nii.gz"

torso = nib.load(S + "vhm_torso_0937.nii.gz")
legs = nib.load(S + "vhm_legs_0937.nii.gz")
feet = nib.load(S + "vhm_feet_0937.nii.gz")

LEGS_TO_TORSO = np.array([4.72, 2.11, -698.0])    # re-derived against DU-STL patella/vastus lateralis vertices (the documented (2.72,-0.89,-693.0) from image correlation left patella_r/vastus_lateralis_r 15-16% outside the legs-block silhouette; this shift brings both patellae and vastus lateralis to <=1.5% outside)
FEET_TO_LEGS = np.array([3.5, -35.0, -406.0])     # re-derived here against the DU-STL tarsal/metatarsal/phalanx vertices directly (Q1's documented -6.6,-36.6 did not contain them: up to 42% of vertices fell outside the feet-block silhouette; this shift brings calcaneus/talus/metatarsals to 0% outside, phalanges to <=4%)

def silhouette(img):
    d = np.asarray(img.dataobj)
    m = np.zeros(img.shape, bool)
    for k in range(img.shape[2]):
        m[:, :, k] = ndi.binary_fill_holes(ndi.binary_opening(d[:, :, k] > -300, iterations=2))
    return m

bt = silhouette(torso)
bl = silhouette(legs)
bf = silhouette(feet)
print("silhouettes done", bt.sum(), bl.sum(), bf.sum(), flush=True)

AT = torso.affine
# affine for legs/feet expressed in the TORSO block's own RAS frame (translation shifted)
AL = legs.affine.copy(); AL[:3, 3] += LEGS_TO_TORSO
AF = feet.affine.copy(); AF[:3, 3] += FEET_TO_LEGS + LEGS_TO_TORSO

# how far below the torso grid (k=0, z=AT[2,3]) the combined grid must extend: feet's most negative z
all_z = [AT[2, 3], AL[2, 3], AL[2, 3] + (legs.shape[2] - 1) * AL[2, 2],
         AF[2, 3], AF[2, 3] + (feet.shape[2] - 1) * AF[2, 2]]
zmin = min(all_z)
EXT = int(np.ceil((AT[2, 3] - zmin))) + 2
A2 = AT.copy(); A2[2, 3] -= EXT * AT[2, 2]
out = np.zeros((torso.shape[0], torso.shape[1], torso.shape[2] + EXT), bool)
out[:, :, EXT:] = bt
print("combined grid", out.shape, "z0", A2[2, 3], flush=True)

ii, jj = np.meshgrid(np.arange(torso.shape[0]), np.arange(torso.shape[1]), indexing="ij")

def paste(block_mask, block_affine, label):
    inv = np.linalg.inv(block_affine)
    n_added = 0
    for k in range(out.shape[2]):
        ras = nib.affines.apply_affine(A2, np.c_[ii.ravel(), jj.ravel(), np.full(ii.size, k)])
        v = np.rint(nib.affines.apply_affine(inv, ras)).astype(int)
        ok = ((v[:, 0] >= 0) & (v[:, 0] < block_mask.shape[0]) &
              (v[:, 1] >= 0) & (v[:, 1] < block_mask.shape[1]) &
              (v[:, 2] >= 0) & (v[:, 2] < block_mask.shape[2]))
        s = np.zeros(ii.size, bool); s[ok] = block_mask[v[ok, 0], v[ok, 1], v[ok, 2]]
        s = s.reshape(ii.shape)
        if s.any():
            out[:, :, k] |= s; n_added += 1
    print(label, "pasted into", n_added, "slices", flush=True)

paste(bl, AL, "legs")
paste(bf, AF, "feet")

out = ndi.binary_closing(out, structure=np.ones((1, 1, 5)))
cl, n = ndi.label(out)
sizes = ndi.sum(np.ones_like(cl, dtype=np.uint8), cl, np.arange(1, n + 1))
body = cl == (np.argmax(sizes) + 1)
print("body voxels before margin", int(body.sum()), "components", n, "grid", body.shape, flush=True)
# 2 mm safety margin: three independently-derived rigid shifts (torso<->legs<->feet, each fitted against
# DU-STL bone/muscle vertices, see optimize_legs_shift.py / optimize_feet_shift.py) bring mean vertex
# containment failure across all 130 vhm_both structures to 0.49% -- but a rigid shift per block can't
# correct for a slight torsion along the shaft, and three right-leg lateral-compartment muscles
# (fibularis_longus_r 17%, tibialis_anterior_r 16%, extensor_digitorum_longus_r 7%) still poke through
# without it. This margin brings the worst case to 1.8% and the mean to 0.03%.
body = ndi.binary_dilation(body, structure=np.ones((3, 3, 3)), iterations=2).astype(np.uint8)
print("final body voxels (2 mm margin)", int(body.sum()), flush=True)
nib.save(nib.Nifti1Image(body, A2), OUT)
print("saved", OUT, flush=True)
