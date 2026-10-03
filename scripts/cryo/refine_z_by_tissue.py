"""Refine each anchor's cryo z by correlating the CT soft-tissue pattern (HU 20..150 = muscle/organs)
with the cryo muscle class, under the anchor's flip and in-plane shift, over +-25 slices."""
import numpy as np, json, nibabel as nib, sys
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_1mm_classes.npy",mmap_mode="r")
ct={"torso":nib.load(S+"vh_idc/nii/vhm_torso_0937.nii.gz").dataobj,"legs":nib.load(S+"vh_idc/nii/vhm_frozen_3.nii.gz").dataobj}
flipy={"torso":False,"legs":True}
anchors=json.load(open(S+"vh_cryo/anchors.json"))
def ct_muscle(block,k):
    s=np.asarray(ct[block][:,:,k]).astype(np.float32)
    if flipy[block]: s=s[:,::-1]
    b=ndi.zoom(s,480/512,order=1).T; return ((b>20)&(b<150)).astype(np.float32)
def cryo_muscle(z,flip,sh):
    m=(np.asarray(cls[z])==3)
    if flip=="fy": m=m[::-1,:]
    elif flip=="fx": m=m[:,::-1]
    elif flip=="fxy": m=m[::-1,::-1]
    P=np.zeros((480,700),bool); P[:m.shape[0],:m.shape[1]]=m; m=np.roll(np.roll(P,int(sh[0]),0),int(sh[1]),1); return m[:480,:480].astype(np.float32)
def ncc(a,b): a=a-a.mean(); b=b-b.mean(); return float((a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum()+1e-6))
out=[]
for a in anchors:
    A=ct_muscle(a["block"],a["ct_k"]); best=None
    for z in range(max(0,a["cryo_z"]-25),min(cls.shape[0],a["cryo_z"]+26)):
        s=ncc(A,cryo_muscle(z,a["flip"],a["shift"]))
        if best is None or s>best[0]: best=(s,z)
    a2=dict(a); a2["cryo_z_refined"]=best[1]; a2["ncc"]=round(best[0],3); out.append(a2)
    print(a["block"],a["ct_k"],"coarse",a["cryo_z"],"refined",best[1],"d=%d"%(best[1]-(-20-a["ct_z"])),"ncc %.3f"%best[0],flush=True)
json.dump(out,open(S+"vh_cryo/anchors_refined.json","w"),indent=1)
