"""Visible Human FEMALE body surface over BOTH CT blocks on one grid: the torso block's silhouette (HU > -300,
opened, holes filled, largest component) and the legs block's silhouette resampled into the torso grid extended
downward by EXT slices, using the legs->torso shift from vhf_lower_limb_bones (block continuity). Writes
scratchpad/vhf_ts/skin_ct.nii.gz (uint8, label 1 = body) in the torso block's RAS frame, for `ct_vhf_skin`."""
import json, numpy as np, nibabel as nib
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
def silhouette(path):
    im=nib.load(path); d=np.asarray(im.dataobj)>-300; m=np.zeros(im.shape,bool)   # whole array: slice reads from a .gz proxy are quadratic
    for k in range(im.shape[2]): m[:,:,k]=ndi.binary_fill_holes(ndi.binary_opening(d[:,:,k],iterations=2))
    del d; return im,m
imT,bt=silhouette(S+"vh_idc/nii/vhf_torso_0937.nii.gz"); imL,bl=silhouette(S+"vh_idc/nii/vhf_legs_0723.nii.gz")
t=np.array(json.load(open("/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhf_lower_limb_bones_report.json"))["registration"]["shift_ras_legs_to_torso"])
AT=imT.affine; AL=imL.affine; zl=[AL[2,3]+t[2], AL[2,3]+(imL.shape[2]-1)*AL[2,2]+t[2]]   # legs block z range in torso RAS
EXT=int(np.ceil((AT[2,3]-min(zl))/AT[2,2]))+2; A2=AT.copy(); A2[2,3]-=EXT*AT[2,2]
out=np.zeros((imT.shape[0],imT.shape[1],imT.shape[2]+EXT),bool); out[:,:,EXT:]=bt
inv=np.linalg.inv(AL); ii,jj=np.meshgrid(np.arange(imT.shape[0]),np.arange(imT.shape[1]),indexing="ij")
for k in range(0,EXT+3):
    ras=nib.affines.apply_affine(A2,np.c_[ii.ravel(),jj.ravel(),np.full(ii.size,k)])-t
    v=np.rint(nib.affines.apply_affine(inv,ras)).astype(int)
    ok=(v[:,0]>=0)&(v[:,0]<imL.shape[0])&(v[:,1]>=0)&(v[:,1]<imL.shape[1])&(v[:,2]>=0)&(v[:,2]<imL.shape[2])
    s=np.zeros(ii.size,bool); s[ok]=bl[v[ok,0],v[ok,1],v[ok,2]]; out[:,:,k]|=s.reshape(ii.shape)
out=ndi.binary_closing(out,structure=np.ones((1,1,7)))   # the few-slice junction gap
cl,n=ndi.label(out); sizes=ndi.sum(np.ones_like(cl,dtype=np.uint8),cl,np.arange(1,n+1)); body=(cl==(np.argmax(sizes)+1)).astype(np.uint8)
print("female whole-body silhouette voxels",int(body.sum()),"components",n,"grid",body.shape,"z from",A2[2,3])
nib.save(nib.Nifti1Image(body,A2),S+"vhf_ts/skin_ct.nii.gz")
