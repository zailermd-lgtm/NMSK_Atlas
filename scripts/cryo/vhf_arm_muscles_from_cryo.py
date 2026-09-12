"""Female upper-arm muscles by the male's rules (arm_compartments_from_cryo.py + name_arm_muscles_from_cryo.py) on her
registered cryosection photographs, around her CT humerus label (shifted onto the photographs by the per-side
constants found for the deltoid: rows 0, cols +11 right / -15 left). Arm segment = 10 mm above the humerus label's
lower end to 70 mm below its top (the deltoid band excluded). Within the arm's cross-section (tissue component
holding the humerus, within 70 mm of it), every muscle piece within 45 mm of the humerus, not already deltoid / cuff, is split by the coronal plane
through the humerus centre: posterior -> triceps brachii; anterior: within 22 mm of the humerus in the distal 65 %
-> brachialis; proximal 40 %, medial, within 15 mm -> coracobrachialis; the rest -> biceps brachii. Boundaries are
rules, not traced fascia (the forearm is not attempted: its bones are not segmented, Q30). Badge; record volumes.
Output vhf_ts/arm_muscles_cryo.nii.gz (torso RAS), report, crop renders."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"; R="/home/user/NMSK_Atlas/"; T=R+"data/ct_sources/task_outputs/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); rgb=np.load(D+"cryo_frame_rgb.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
def load(name): im=nib.load(T+name); return np.asarray(im.dataobj),float(im.affine[2,3])
tot,zT0=load("vhf_total.nii.gz"); delt,zD0=load("vhf_deltoid_cryo.nii.gz"); cuff,zC0=load("vhf_rotator_cuff_cryo.nii.gz")
labs={v:int(k) for k,v in json.load(open(R+"mappings/totalsegmentator_labels.json"))["labels"].items()}
SHIFT={"right":(0,11),"left":(0,-15)}
def frame_ct(arr,zoff,k,dy,dx):
    kk=int(round(z0+k-zoff)); f=np.zeros((H,W),np.int32)
    if 0<=kk<arr.shape[2]: f[:,OFF:OFF+480]=ndi.zoom(arr[:,:,kk],480/512,order=0).T
    return np.roll(np.roll(f,dy,0),dx,1)
def frame_fr(arr,zoff,k):
    kk=int(round(z0+k-zoff)); return arr[:,:,kk].T.astype(np.int32) if 0<=kk<arr.shape[2] else np.zeros((H,W),np.int32)
OUT={"biceps_right":1,"brachialis_right":2,"coracobrachialis_right":3,"triceps_right":4,"biceps_left":5,"brachialis_left":6,"coracobrachialis_left":7,"triceps_left":8}
out=np.zeros((n,H,W),np.uint8); rep={}
for side,(cols,base,medial_sign) in {"right":(slice(0,300),0,+1),"left":(slice(400,700),4,-1)}.items():
    hum=labs[f"humerus_{side}"]; dy,dx=SHIFT[side]
    kT=np.where((tot==hum).any(axis=(0,1)))[0]; kbot=int(round(zT0+kT.min()-z0)); ktop=int(round(zT0+kT.max()-z0))
    k0,k1=max(kbot+10,ktop-320),ktop-70; L=k1-k0;   # a female humerus is ~300 mm: the segment never starts more than 320 mm below the head (her left label carries a stray piece lower down) print(side,"arm segment frame k",k0,"..",k1,"z",z0+k0,z0+k1,flush=True)
    for k in range(k0,k1+1):
        h=frame_ct(tot,zT0,k,dy,dx)[:,cols]==hum
        if h.sum()<30: continue
        c=np.asarray(cls[k])[:,cols]; other=(frame_fr(delt,zD0,k)[:,cols]>0)|(frame_fr(cuff,zC0,k)[:,cols]>0)
        tissue=ndi.binary_fill_holes(ndi.binary_closing(c>0,iterations=3)); tl,tn=ndi.label(tissue)
        u=np.unique(tl[h]); comp=np.isin(tl,u[u>0]); ys,xs=np.where(h); cy,cx=ys.mean(),xs.mean(); yy,xx=np.mgrid[0:H,0:cols.stop-cols.start]
        comp&=((yy-cy)**2+(xx-cx)**2)<70**2
        # her arm muscle is fattier and septated than the male's: keep every muscle piece (opened by 1 px) whose nearest point
        # lies within 45 mm of the humerus, inside the arm's own cross-section (the male's erode-3 / 12 px rule kept only slivers)
        mall=comp&(c==3)&~h&~other; op=ndi.binary_opening(mall,iterations=1); el,en=ndi.label(op)
        if en==0: continue
        dh=ndi.distance_transform_edt(~h); mind=ndi.minimum(dh,el,np.arange(1,en+1)); keep=np.arange(1,en+1)[np.asarray(mind)<=45]
        if len(keep)==0: continue
        musc=ndi.binary_dilation(np.isin(el,keep),iterations=1)&mall
        ant=yy<cy; d=ndi.distance_transform_edt(~h); frac=(k-k0)/L
        o=out[k][:,cols]; a=musc&ant; p=musc&~ant; o[p]=base+4
        brach=a&(d<=22)&(frac<0.65); o[brach]=base+2
        cor=a&(frac>=0.6)&(d<=15)&(medial_sign*(xx-cx)>0); o[cor]=base+3
        o[a&~brach&~cor]=base+1
for name,v in OUT.items(): rep[name]=round(float((out==v).sum())/1000,1)
print("volumes cm3",rep,flush=True)
nz=np.where(out.any(axis=(1,2)))[0]; ka,kb=nz.min(),nz.max()+1
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+ka],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out[ka:kb].transpose(2,1,0)),aff),S+"vhf_ts/arm_muscles_cryo.nii.gz")
json.dump({"_README":["Female upper-arm muscles by the male's compartment and naming rules on her registered cryosections (scripts/cryo/vhf_arm_muscles_from_cryo.py). Rule-based, derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 humerus label as anchor.","volumes_cm3":rep},open(D+"arm_muscles_report.json","w"),indent=1)
lut=np.array([[0,0,0],[255,90,90],[255,200,90],[200,120,255],[90,120,255],[255,90,90],[255,200,90],[200,120,255],[90,120,255]],np.uint8)
for side,cols in (("right",slice(0,300)),("left",slice(400,700))):
    ks=np.where((out[:,:,cols]>0).any(axis=(1,2)))[0]; ts=[]
    for k in np.linspace(ks.min()+3,ks.max()-3,7).astype(int):
        im=np.asarray(rgb[k])[:,cols].copy(); m=out[k][:,cols]; ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-15,0),min(ys.max()+15,H),max(xs.min()-15,0),min(xs.max()+15,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.5*im[mm>0]+0.5*lut[mm[mm>0]]).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(D+f"arm_muscles_{side}.png")
print("ARMM_DONE")
