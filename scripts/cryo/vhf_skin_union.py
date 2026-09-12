"""Female body surface over the WHOLE body including the arms: the CT silhouette (vhf_whole_body_skin.py; her CT
clips the arms laterally) united with the photograph silhouette (colour classes > 0, closed, hole-filled, pieces
>= 20 cm2 per slice, the ruler rows at the top of the frame dropped) on the registered 1 mm frame (480 x 700), photographs used only
above RAS z -950 (the arm levels; lower down they would add a registration rim along the legs).
The trunk and legs therefore stay CT-exact; the arms come from the photographs (+-10 mm, the registration). Output
vhf_ts/skin_union.nii.gz (label 1 = body) in torso RAS on the frame grid, for `ct_vhf_skin` and the depth tags."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
sk=nib.load(S+"vhf_ts/skin_ct.nii.gz"); skd=np.asarray(sk.dataobj); zS0=float(sk.affine[2,3])
out=np.zeros((n,H,W),np.uint8); ncryo=0; nct=0
for k in range(n):
    c=np.asarray(cls[k])>0; c[:60]=False   # the Kodak ruler / label rows
    t=ndi.binary_fill_holes(ndi.binary_closing(c,iterations=3)); l,m=ndi.label(t)
    if m: sz=ndi.sum(np.ones_like(l),l,np.arange(1,m+1)); t=np.isin(l,np.arange(1,m+1)[sz>=2000])
    kk=int(round(z0+k-zS0)); ctm=np.zeros((H,W),bool)
    if 0<=kk<skd.shape[2]: ctm[:,OFF:OFF+480]=ndi.zoom(skd[:,:,kk],480/512,order=0).T>0
    if z0+k<-950: t=np.zeros_like(t)   # below the arms (RAS z < -950) the CT silhouette is exact; the photographs would add a registration rim along the legs
    u=t|ctm; out[k]=u; ncryo+=int((t&~ctm).sum()); nct+=int(ctm.sum())
print("CT silhouette voxels",nct,"added from the photographs",ncryo,"(%.1f %%)"%(100*ncryo/max(nct,1)),flush=True)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0],[0,0,0,1]],float)
nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhf_ts/skin_union.nii.gz"); print("SKIN_UNION_DONE")
