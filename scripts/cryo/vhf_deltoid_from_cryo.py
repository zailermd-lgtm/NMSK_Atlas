"""Female deltoid from her registered cryosection photographs, by the male's rule (deltoid_from_cryo.py v2):
muscle-class voxels (a) within 55 mm of the proximal humerus (her TotalSegmentator humerus label, from 20 mm
above its top to 130 mm below), (b) within 40 mm of the skin surface (the deltoid is the only muscle between skin
and proximal humerus laterally), (c) not labelled by her `abdominal_muscles` run (pectoralis major, latissimus,
serratus, trapezius) nor any other `total` label, (d) lateral to the scapula's lateral edge (+8 mm); one piece per
slice (largest). Her CT labels are shifted onto the photographs by the per-side constant found by masked
cross-correlation of the humerus label with the photograph's bone colour (the residual of the piecewise
registration at the arms). Rule-based: badge it, record the volumes. Output vhf_ts/deltoid_cryo.nii.gz (torso RAS),
a report, and crop renders."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from scipy.signal import fftconvolve
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"; R="/home/user/NMSK_Atlas/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); rgb=np.load(D+"cryo_frame_rgb.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
tot=nib.load(R+"data/ct_sources/task_outputs/vhf_total.nii.gz"); totd=np.asarray(tot.dataobj); zT0=float(tot.affine[2,3])   # whole arrays: slice reads from a .gz proxy are quadratic
abd=nib.load(R+"data/ct_sources/task_outputs/vhf_abdominal_muscles.nii.gz"); abdd=np.asarray(abd.dataobj); zA0=float(abd.affine[2,3])
labs={v:int(k) for k,v in json.load(open(R+"mappings/totalsegmentator_labels.json"))["labels"].items()}
def frame_of(dobj,zoff,shape,k,order=0):
    kk=int(round(z0+k-zoff)); full=np.zeros((H,W),np.int32)
    if 0<=kk<shape[2]: full[:,OFF:OFF+480]=ndi.zoom(np.asarray(dobj[:,:,kk]),480/512,order=order).T
    return full
out=np.zeros((n,H,W),np.uint8); rep={}
for side,(cols,lid,sgn) in {"right":(slice(0,300),1,+1),"left":(slice(400,700),2,-1)}.items():
    hum=labs[f"humerus_{side}"]; scap=labs[f"scapula_{side}"]
    ks=[k for k in range(int(-650-z0),int(-150-z0)) if (frame_of(totd,zT0,tot.shape,k)[:,cols]==hum).sum()>=40]
    if not ks: print(side,"no humerus"); continue
    ktop=max(ks); shifts=[]
    for k in ks[::10]:
        t_=frame_of(totd,zT0,tot.shape,k)[:,cols]; m=t_==hum; c=np.asarray(cls[k])[:,cols]; cr=np.isin(c,[2,4,5])&ndi.binary_dilation(m,iterations=25)
        a=m.astype(np.float32)-m.mean(); bb=cr.astype(np.float32)-cr.mean(); cc=fftconvolve(bb,a[::-1,::-1],mode="same"); iy,ix=np.unravel_index(np.argmax(cc),cc.shape); shifts.append((iy-a.shape[0]//2,ix-a.shape[1]//2))
    dy,dx=[int(np.median([s[i] for s in shifts])) for i in (0,1)]; print(side,"CT->photo shift (rows,cols) px",dy,dx,"humerus slices",len(ks),flush=True)
    for k in range(max(0,ktop-130),min(n,ktop+21)):   # 130 mm below the head top: below that the rule catches brachialis/triceps (she has no arm-compartment labels to exclude)
        t_=np.roll(np.roll(frame_of(totd,zT0,tot.shape,k),dy,0),dx,1)[:,cols]; hb_=np.roll(np.roll(frame_of(abdd,zA0,abd.shape,k),dy,0),dx,1)[:,cols]
        h=t_==hum; sc=t_==scap
        if not h.any() and not sc.any(): continue
        c=np.asarray(cls[k])[:,cols]; tissue=ndi.binary_fill_holes(ndi.binary_closing(c>0,iterations=3)); dskin=ndi.distance_transform_edt(tissue)
        dhum=ndi.distance_transform_edt(~h) if h.any() else np.full(h.shape,999.0)
        m=(c==3)&(dhum<=55)&(dskin<=40)&(hb_==0)&(t_==0)
        xs=np.where(sc)[1]
        if xs.size:
            lat_edge=xs.min() if sgn>0 else xs.max(); xx=np.arange(h.shape[1])[None,:]; m&=(xx<=lat_edge+8) if sgn>0 else (xx>=lat_edge-8)
        m=ndi.binary_opening(m,iterations=1)
        if m.any():
            cl,mm=ndi.label(m); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); m=cl==(np.argmax(sizes)+1)
        out[k][:,cols][m]=lid
    kk=np.where((out==lid).any(axis=(1,2)))[0]; rep[side]={"cm3":round(float((out==lid).sum())/1000,1),"z_range":[float(z0+kk.min()),float(z0+kk.max())] if len(kk) else None,"ct_shift_px":[dy,dx]}
print("deltoid",rep,flush=True)
nz=np.where(out.any(axis=(1,2)))[0]; k0,k1=nz.min(),nz.max()+1
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+k0],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out[k0:k1].transpose(2,1,0)),aff),S+"vhf_ts/deltoid_cryo.nii.gz")
json.dump({"_README":["Female deltoid by the male's rule on her registered cryosections (scripts/cryo/vhf_deltoid_from_cryo.py). Rule-based, derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 labels as anchors.","deltoid":rep},open(D+"deltoid_report.json","w"),indent=1)
for side,cols in (("right",slice(0,300)),("left",slice(400,700))):
    ts=[]; ks=np.where((out[:,:,cols]>0).any(axis=(1,2)))[0]
    for k in np.linspace(ks.min(),ks.max(),7).astype(int):
        im=np.asarray(rgb[k])[:,cols].copy(); m=out[k][:,cols]; ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-25,0),min(ys.max()+25,H),max(xs.min()-25,0),min(xs.max()+25,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.5*im[mm>0]+np.array([120,40,127])).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(D+f"deltoid_{side}.png")
print("DELTOID_DONE")
