"""Female rotator cuff from her registered cryosection photographs, by the male's rule (rotator_cuff_from_cryo.py v2):
muscle-class voxels within 25 mm of her TotalSegmentator scapula label and not already a trunk-muscle
(`abdominal_muscles` run), deltoid (`vhf_deltoid_cryo`) or other `total` label, assigned by the nearest scapular
surface: ventral -> subscapularis; dorsal -> supraspinatus if above the scapular spine level (top 22 % of the
scapula's height) and medial to the glenoid, else infraspinatus (teres minor merged). Voxels within 8 mm of a rib
are dropped (serratus / intercostals hug the ribs; the cuff does not). Her CT labels are shifted onto the
photographs by the per-side constants found for the deltoid (rows 0, cols +11 right / -15 left). Rule-based:
badge it, record the volumes. Output vhf_ts/rotator_cuff_cryo.nii.gz (torso RAS), a report, crop renders."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"; R="/home/user/NMSK_Atlas/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); rgb=np.load(D+"cryo_frame_rgb.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
tot=nib.load(R+"data/ct_sources/task_outputs/vhf_total.nii.gz"); totd=np.asarray(tot.dataobj); zT0=float(tot.affine[2,3])
abd=nib.load(R+"data/ct_sources/task_outputs/vhf_abdominal_muscles.nii.gz"); abdd=np.asarray(abd.dataobj); zA0=float(abd.affine[2,3])
dl=nib.load(R+"data/ct_sources/task_outputs/vhf_deltoid_cryo.nii.gz"); dld=np.asarray(dl.dataobj); zD0=float(dl.affine[2,3])   # frame voxels (col,row,k) already
labs={v:int(k) for k,v in json.load(open(R+"mappings/totalsegmentator_labels.json"))["labels"].items()}
rib_ids=[v for k,v in labs.items() if k.startswith("rib_") or k=="costal_cartilages"]
SHIFT={"right":(0,11),"left":(0,-15)}
def frame_of(arr,zoff,k):
    kk=int(round(z0+k-zoff)); full=np.zeros((H,W),np.int32)
    if 0<=kk<arr.shape[2]: full[:,OFF:OFF+480]=ndi.zoom(arr[:,:,kk],480/512,order=0).T
    return full
def delt_of(k):
    kk=int(round(z0+k-zD0)); return dld[:,:,kk].T if 0<=kk<dld.shape[2] else np.zeros((H,W),np.uint8)
out=np.zeros((n,H,W),np.uint8); rep={}
LAB={"right":(1,2,3),"left":(4,5,6)}
for side,(cols,ids) in {"right":(slice(0,360),LAB["right"]),"left":(slice(340,700),LAB["left"])}.items():
    sc=labs[f"scapula_{side}"]; dy,dx=SHIFT[side]
    kT=np.where((totd==sc).any(axis=(0,1)))[0]; ks=[int(round(zT0+k-z0)) for k in kT]; k0,k1=min(ks),max(ks); zspine=k0+0.78*(k1-k0)
    for k in range(k0,k1+1):
        t=np.roll(np.roll(frame_of(totd,zT0,k),dy,0),dx,1)[:,cols]; scap=t==sc
        if not scap.any(): continue
        c=np.asarray(cls[k])[:,cols]; hb=np.roll(np.roll(frame_of(abdd,zA0,k),dy,0),dx,1)[:,cols]; d=delt_of(k)[:,cols]
        dist,ind=ndi.distance_transform_edt(~scap,return_indices=True)
        m=(c==3)&(dist<=25)&(hb==0)&(d==0)&(t==0)
        ribs=np.isin(t,rib_ids)
        if ribs.any(): m&=ndi.distance_transform_edt(~ribs)>8
        xs_=np.where(scap)[1]; lat=xs_.min() if side=="right" else xs_.max()
        xx=np.arange(cols.stop-cols.start)[None,:]*np.ones((H,1),int); fossa=(xx>=lat+15) if side=="right" else (xx<=lat-15)
        if not m.any(): continue
        yy=np.arange(H)[:,None]*np.ones((1,cols.stop-cols.start),int); ny=ind[0]; ventral=yy<ny
        o=out[k][:,cols]; o[m&ventral]=ids[2]; dors=m&~ventral; o[dors&(k>=zspine)&fossa]=ids[0]; o[dors&((k<zspine)|~fossa)]=ids[1]
    for i,name in enumerate(("supraspinatus","infraspinatus","subscapularis")): rep[f"{name}_{side}"]=round(float((out==ids[i]).sum())/1000,1)
print("volumes cm3",rep,flush=True)
nz=np.where(out.any(axis=(1,2)))[0]; ka,kb=nz.min(),nz.max()+1
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+ka],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out[ka:kb].transpose(2,1,0)),aff),S+"vhf_ts/rotator_cuff_cryo.nii.gz")
json.dump({"_README":["Female rotator cuff by the male's scapular-surface rules on her registered cryosections (scripts/cryo/vhf_rotator_cuff_from_cryo.py). Rule-based, derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 labels as anchors.","volumes_cm3":rep},open(D+"cuff_report.json","w"),indent=1)
lut=np.zeros((7,3),np.uint8); lut[1]=lut[4]=(255,120,60); lut[2]=lut[5]=(80,200,255); lut[3]=lut[6]=(200,120,255)
for side,cols in (("right",slice(0,360)),("left",slice(340,700))):
    ks=np.where((out[:,:,cols]>0).any(axis=(1,2)))[0]; ts=[]
    for k in np.linspace(ks.min(),ks.max(),6).astype(int):
        im=np.asarray(rgb[k])[:,cols].copy(); m=out[k][:,cols]; ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-25,0),min(ys.max()+25,H),max(xs.min()-25,0),min(xs.max()+25,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.5*im[mm>0]+0.5*lut[mm[mm>0]]).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(D+f"cuff_{side}.png")
print("CUFF_DONE")
