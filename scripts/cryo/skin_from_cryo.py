"""Body surface from the cryosections: tissue (not gelatin) per slice, holes filled, largest 3-D component.
Saved as a NIfTI on the cryo grid with the registration affine (cryo (r,c,idx) -> RAS), so the ingest
places it like every other Visible Human subject."""
import numpy as np, nibabel as nib
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_1mm_classes.npy",mmap_mode="r"); Z,H,W=cls.shape
m=np.zeros((Z,H,W),bool)
for z in range(Z):
    t=np.asarray(cls[z])>0; t=ndi.binary_opening(t,iterations=2); m[z]=ndi.binary_fill_holes(t)
cl,n=ndi.label(m); sizes=ndi.sum(np.ones_like(cl,dtype=np.uint8),cl,np.arange(1,n+1)); body=cl==(np.argmax(sizes)+1)
print("components",n,"body voxels",int(body.sum()),"dropped",int(m.sum()-body.sum()),flush=True)
# (r,c,idx) -> RAS: x = 338 - 0.99 c ; y = -159.96 + 0.99 r ; z = -16 - idx   (torso-block shift (0,-98), scale 0.99)
data=np.ascontiguousarray(body.transpose(2,1,0)).astype(np.uint8)   # (c, r, idx)
aff=np.array([[-0.99,0,0,338.0],[0,0.99,0,-159.96],[0,0,-1.0,-16.0],[0,0,0,1]])
nib.save(nib.Nifti1Image(data,aff),S+"vhm_ts/skin_cryo.nii.gz"); print("saved")
