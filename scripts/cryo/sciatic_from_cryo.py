"""Sciatic nerve tracked through the cryosections (both sides). Seed at the level of the ischial
tuberosity (lowest hip-bone voxel of the legs CT block): the nerve lies midway between the ischial
tuberosity and the greater trochanter, deep to gluteus maximus -- the pale (fat/connective-coloured) blob
of 30-250 mm2 nearest that point. Then slice by slice downward: the pale component inside the previous
cross-section dilated by 4 mm, kept within 9 mm of the previous centroid, area 25-300 mm2; stops when it
vanishes or at the femoral condyles (popliteal division). Cryo index space, legs-block registration."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_1mm_classes.npy",mmap_mode="r"); vol=np.load(S+"vh_cryo/cryo_1mm.npy",mmap_mode="r"); Z,H,W=cls.shape
seg_img=nib.load(S+"vhm_ts/legs_total.nii.gz"); A=seg_img.affine; seg=np.asarray(seg_img.dataobj)
# NOTE: A is the segmentation volume's OWN affine (LAS), not the raw legs CT's (LPS) -- TotalSegmentator's
# output is flipped along axis 1 relative to vhm_legs_0937.nii.gz despite sharing shape/spacing, so hv/fv
# (voxel indices into `seg`) must be transformed by seg_img's own affine, never the CT's, or the landmark
# lands ~470 mm off. Verified empirically: apply_affine(seg_img.affine, seg_idx) reproduces bone-HU voxels
# in the raw CT, apply_affine(legs_CT.affine, seg_idx) does not.
inv={v:k for k,v in class_map['total'].items()}; t_off=np.array([4.72,2.11,-698.0])  # Q70 re-fit legs->torso offset (was the stale 2.72,-0.89,-693.0)
def ras_to_cryo(ras):   # legs-block registration: col = (336 - x)/0.99, row = (y + 163.96)/0.99, idx = -16 - z
    return np.stack([(ras[:,1]+163.96)/0.99, (336-ras[:,0])/0.99, -16-ras[:,2]],axis=1)
out=np.zeros((Z,H,W),np.uint8); rep={}
for side,lid in (("right",1),("left",2)):
    hip=seg==inv[f"hip_{side}"]; fem=seg==inv[f"femur_{side}"]
    hv=np.argwhere(hip); hr=nib.affines.apply_affine(A,hv)+t_off; it=hr[np.argmin(hr[:,2])]           # ischial tuberosity ~ lowest hip voxel
    fv=np.argwhere(fem); fr=nib.affines.apply_affine(A,fv)+t_off; top=fr[fr[:,2]>it[2]-10]
    gt=top[np.argmax(np.abs(top[:,0]))] if len(top) else fr[np.argmax(np.abs(fr[:,0]))]              # greater trochanter ~ most lateral proximal femur
    mid=(it+gt)/2; mid[1]-=10   # a little posterior
    c0=ras_to_cryo(mid[None])[0]; r0,cc0,z0=int(round(c0[0])),int(round(c0[1])),int(round(c0[2]))
    print(side,"IT",it.round(0),"GT",gt.round(0),"seed cryo (row,col,idx)",r0,cc0,z0,flush=True)
    # seed: nearest pale blob, scanned down from the IT/GT midpoint -- at that level itself the nerve is
    # not colour-separable from the fat plane it lies in (same failure documented for the female's gluteal
    # course, Q53/Q7: "the detector locks onto gluteus maximus' fatty striations" above -70 mm), so we look
    # for the first level, up to 180 mm distal, where a plausibly-sized isolated blob actually exists near
    # the expected column, rather than assuming the anatomical midpoint is itself the first trackable slice.
    # A single matching slice is often a transient noise speck (verified: at dz=1-3 both sides briefly
    # "match" then die within 1 step), so a candidate must persist for >=3 consecutive mm before it is
    # trusted as the real seed -- the first slice of that run is used, not the run's middle.
    hits=[None]*181
    for dz in range(0,181):
        zc=z0+dz
        if zc>=Z: break
        c=np.asarray(cls[zc]); pale=np.isin(c,[2,4]); cl,m=ndi.label(pale); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1))
        best_dz=None
        for i in range(1,m+1):
            if not (30<=sizes[i-1]<=250): continue
            cy,cx=ndi.center_of_mass(cl==i); d=np.hypot(cy-r0,cx-cc0)
            if d<30 and (best_dz is None or d<best_dz[0]): best_dz=(d,i)
        hits[dz]=best_dz
    z0_found=None; best=None; run=0
    for dz in range(0,181):
        if hits[dz] is not None:
            run+=1
            if run==1: run_start=dz
            if run>=3: z0_found=z0+run_start; best=hits[run_start]; break
        else: run=0
    if best is None: print(side,"no seed blob found (persisting >=3 mm) within 180 mm distal to the IT/GT midpoint",flush=True); continue
    c=np.asarray(cls[z0_found]); pale=np.isin(c,[2,4]); cl,m=ndi.label(pale)
    print(side,"seed found",z0_found-z0,"mm distal to the IT/GT midpoint, idx",z0_found,flush=True)
    prev=cl==best[1]; py,px=ndi.center_of_mass(prev); z=z0_found; steps=0
    condyle_idx=int(-16-(fr[:,2].min()+60))   # stop 60 mm above the femur's lowest point (condyles)
    while z<condyle_idx:
        out[z][prev]=lid; z+=1; steps+=1
        c=np.asarray(cls[z]); pale=np.isin(c,[2,4]); cand=pale&ndi.binary_dilation(prev,iterations=4)
        yy,xx=np.mgrid[0:H,0:W]; cand&=((yy-py)**2+(xx-px)**2)<=9**2
        cl,m=ndi.label(cand)
        if m==0: break
        sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1)); new=cl==(np.argmax(sizes)+1)
        if new.sum()<25: break
        if new.sum()>300:   # merged into a fat sheet: keep the part nearest the previous centroid
            d=ndi.distance_transform_edt(~prev); new&=d<=4
            if new.sum()<25 or new.sum()>300: break
        prev=new; py,px=ndi.center_of_mass(prev)
    rep[side]=dict(landmark_idx=z0,seed_idx=z0_found,seed_offset_mm=z0_found-z0,slices=steps,end_idx=z,length_mm=steps,volume_cm3=round(float((out==lid).sum())/1000,2)); print(side,rep[side],flush=True)
np.save(S+"vh_cryo/sciatic_frame.npy",out); json.dump(rep,open(S+"vhm_ts/sciatic_report.json","w"),indent=1)
data=np.ascontiguousarray(out.transpose(2,1,0)); aff=np.array([[-0.99,0,0,336.0],[0,0.99,0,-163.96],[0,0,-1.0,-16.0],[0,0,0,1]])
nib.save(nib.Nifti1Image(data,aff),S+"vhm_ts/sciatic_cryo.nii.gz")
# render: coronal projection over the tissue silhouette of the legs region
zs=np.where((out>0).any(axis=(1,2)))[0]
if zs.size:
    z0_,z1_=max(0,zs.min()-30),min(Z,zs.max()+30); p=out[z0_:z1_].max(axis=1); base=np.zeros(p.shape,np.uint8)
    for i,z in enumerate(range(z0_,z1_)): base[i]=(np.asarray(cls[z])>0).sum(axis=0)
    img=np.repeat(np.clip(base,0,255)[...,None],3,2).astype(np.uint8); img[p==1]=(255,60,60); img[p==2]=(60,160,255); Image.fromarray(img).save(S+"vh_cryo/sciatic_cor.png")
    ts=[]
    for z in np.linspace(zs.min(),zs.max(),6).astype(int):
        im=np.asarray(vol[z]).copy(); mm=out[z]; ys,xs=np.where(mm>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-40,0),min(ys.max()+40,H),max(xs.min()-40,0),min(xs.max()+40,W); im=im[r0:r1,c0:c1]; m2=mm[r0:r1,c0:c1]
        e=(m2>0)&~ndi.binary_erosion(m2>0); im[e]=(0,255,0); ts.append(im)
    if ts:
        h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts); Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).resize((w*len(ts)*2,h*2)).save(S+"vh_cryo/sciatic_axial.png")
print("done")
