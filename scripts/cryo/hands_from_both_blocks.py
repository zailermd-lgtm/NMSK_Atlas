"""Whole hands: extend the torso frame 250 mm downward, add the HU>=200 hand components from the top of
the legs CT block (carried over by the block offset), then split each hand by planes along its axis from
the radius end into carpals (<45 mm) / metacarpals (45-115) / phalanges. Writes the full upper-limb label
volume (humerus, radius, ulna, hand groups) in the extended frame; labels 9-14 replace the hand masses 4/8."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
lab=np.load(S+"vh_cryo/arm_bones_completed_frame.npy"); n,H,W=lab.shape; EXT=250
ext=np.zeros((n+EXT,H,W),np.uint8); ext[EXT:]=lab
F=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863-EXT],[0,0,0,1]],float); Finv=np.linalg.inv(F)
legs=nib.load(S+"vh_idc/nii/vhm_frozen_3.nii.gz"); A=legs.affine; K0=600
L=np.asarray(legs.dataobj[:,:,K0:]).astype(np.float32); seg=np.asarray(nib.load(S+"vhm_ts/legs_total.nii.gz").dataobj[:,:,K0:])
from totalsegmentator.map_to_binary import class_map
skull=[k for k,v in class_map['total'].items() if v=='skull'][0]
known=ndi.binary_dilation((seg>0)&(seg!=skull),iterations=4)   # 'skull' in the legs block is the model mislabelling hand bones
bone=(L>=200)&~known; bone[:6]=False; bone[-6:]=False
cl,m=ndi.label(bone,structure=np.ones((3,3,3))); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1)); t=np.array([2.72,-0.89,-693.0]); added={4:0,8:0}
for i in np.argsort(-sizes):
    if sizes[i]<150: break
    vox=np.argwhere(cl==i+1); ras=nib.affines.apply_affine(A,vox+[0,0,K0])+t; cx=ras[:,0].mean()
    if ras[:,1].mean()<60 or ras[:,2].min()<-1100: continue   # hands rest on the anterior thighs
    fr=np.round(nib.affines.apply_affine(Finv,ras)).astype(int); ok=np.all((fr>=0)&(fr<np.array([W,H,n+EXT])),axis=1); fr=fr[ok]
    side=4 if cx>0 else 8; sel=ext[fr[:,2],fr[:,1],fr[:,0]]==0; ext[fr[sel,2],fr[sel,1],fr[sel,0]]=side; added[side]+=int(sel.sum())
print("legs-block hand voxels added",added,flush=True)
# close small gaps between the two blocks' hand parts (1-2 mm)
for side in (4,8):
    m_=ext==side; m2=ndi.binary_closing(m_,iterations=2)&(ext==0); ext[m2]=side
rep={}
for side,rad,base in ((4,2,9),(8,6,12)):
    # keep only the hand voxels connected (within 6 mm) to the radius' distal end: junk from the FOV edge and the pelvis is dropped
    hm=ext==side; rr_=np.argwhere(ext==rad); kmin=rr_[:,0].min(); seed=np.zeros(hm.shape,bool); seed[max(0,kmin-25):kmin+15]=ext[max(0,kmin-25):kmin+15]==rad
    grow=ndi.binary_dilation(hm|seed,iterations=10); cl_,m_=ndi.label(grow,structure=np.ones((3,3,3))); keepids=np.unique(cl_[seed]); keepids=keepids[keepids>0]
    keep=np.isin(cl_,keepids)&hm; dropped=int(hm.sum()-keep.sum()); ext[hm&~keep]=0; hm=keep; print("side",side,"dropped junk voxels",dropped,flush=True)
    idx=np.argwhere(hm).astype(float); ras=nib.affines.apply_affine(F,idx[:,[2,1,0]]); mu=ras.mean(0)
    u=np.linalg.svd(ras-mu,full_matrices=False)[2][0]
    rr=nib.affines.apply_affine(F,np.argwhere(ext==rad)[:,[2,1,0]]); rc=rr[np.argsort(np.linalg.norm(rr-mu,axis=1))[:300]].mean(0)   # radius end nearest the hand
    if np.dot(mu-rc,u)<0: u=-u
    tt=(ras-rc)@u; t0=np.percentile(tt,1); tt=tt-t0; g=np.where(tt<45,0,np.where(tt<115,1,2)).astype(np.uint8)
    ext[tuple(idx.astype(int).T)]=base+g; print("side",side,"hand length along axis mm",round(float(tt.max())),"voxels",len(idx),flush=True)
    for gi,name in enumerate(("carpals","metacarpals","phalanges")): rep[f"{name}_{'right' if side==4 else 'left'}"]=round(float((ext==base+gi).sum())/1000,1)
print("volumes cm3",rep)
np.save(S+"vh_cryo/arm_bones_ext_frame.npy",ext); json.dump(rep,open(S+"vhm_ts/hand_groups_report.json","w"))
nib.save(nib.Nifti1Image(np.ascontiguousarray(ext.transpose(2,1,0)),F),S+"vhm_ts/arm_bones_cryo_completed.nii.gz"); print("saved")
