"""Hybrid CT: the frozen-cadaver CT with its soft-tissue contrast restored from the registered
photographs. Where the photograph says muscle and the CT is soft tissue, HU := 60; where it says
fat, HU := -100. Bone, air and everything the photograph does not classify keep the CT value.
Only the CT's soft-tissue voxels change; the geometry is the CT's."""
import numpy as np, nibabel as nib
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r")
im=nib.load(S+"vh_idc/nii/vhm_torso_0937.nii.gz"); ct=np.asarray(im.dataobj).astype(np.int16); n=ct.shape[2]
changed=0
for k in range(n):
    c=np.asarray(cls[k]); c512=ndi.zoom(c,512/480,order=0).T   # back to (i,j) voxel order
    s=ct[:,:,k]; soft=(s>-250)&(s<150)
    m=soft&(c512==3); f=soft&(c512==2); s[m]=60; s[f]=-100; changed+=int(m.sum()+f.sum()); ct[:,:,k]=s
    if k%200==0: print(k,flush=True)
nib.save(nib.Nifti1Image(ct,im.affine,im.header),S+"vh_idc/nii/vhm_torso_hybrid.nii.gz"); print("HYBRID_DONE changed voxels",changed,flush=True)
