"""Female radius and ulna by TRACKING through the full-resolution cryosection crops (0.33 mm in-plane, 1 mm
between kept slices), the approach that completed the male's arm bones. Seeds: the first slice below her CT
humerus (RAS z -568 downward) holding two compact cream discs (colour classes 2/4/5, enclosed by soft tissue: opened
4 px, not within 8 px of the outside, 800-3500 px) 40-140 px apart. Walk distally: candidate = bone-cream pixels
(cream that is pinker and less saturated than fat: smoothed b/r > 0.59, saturation < 0.41; falls back to plain
cream when empty) inside the previous section dilated by 6 px (2 mm); largest component, closed, hole-filled;
accepted when at least 35 % of its 4-px surround is muscle (colour class 3;
the track otherwise rides along the subcutaneous fat rim), its area is within [0.65, 1.4] x the previous and never above 2.5 x the seed, and its centroid moves
<= 10 px (3.3 mm). Stops after 10 consecutive failures (the last accepted section is the bone's end). Names at the
wrist: radius = lateral. Writes the two bones at 1 mm into the registered frame and as vhf_ts/forearm_cryo.nii.gz
(torso RAS), a report with lengths and volumes, and renders."""
import numpy as np, json, nibabel as nib, sys
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0,"/home/user/NMSK_Atlas/scripts/cryo"); from cryo_classes import classify
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
bb=json.load(open(D+"arm_full_bbox.json")); ZR=bb["z_ras"]; ZI=bb["cryo_idx"]; fr=json.load(open(D+"frame.json")); z0=fr["z0"]
A=json.load(open(D+"anchors.json")); A=[a for a in A if a["flip"]=="fy" and a["iou"]>=0.7]
zs_a=np.array([a["ct_z"] for a in A]); rs=ndi.median_filter(np.array([a["shift"][0] for a in A],float),size=5,mode="nearest"); cs=ndi.median_filter(np.array([a["shift"][1] for a in A],float),size=5,mode="nearest")
o=np.argsort(zs_a); zs_a,rs,cs=zs_a[o],rs[o],cs[o]; H=405; sc=0.99
def masks(im):
    c=classify(im); sm=ndi.uniform_filter(im.astype(np.float32),size=(5,5,1)); r_,b_=sm[...,0],sm[...,2]; v=sm.max(-1); sat=(v-sm.min(-1))/(v+1e-3)
    cream=np.isin(c,[2,4,5]); bonecream=cream&(sat<0.41)&(b_/(r_+1e-3)>0.59)&(v>120); body=ndi.binary_fill_holes(ndi.binary_closing(c>0,iterations=5))
    return c,cream,bonecream,body
def seeds(im,nmax=2):
    c,cream,bc,body=masks(im); core=ndi.binary_opening(cream,iterations=4); nearbg=ndi.binary_dilation(~body,iterations=8)
    l2,n2=ndi.label(core); touch=np.zeros(n2+1,bool); touch[np.unique(l2[nearbg])]=True; out=[]
    for i,ob in enumerate(ndi.find_objects(l2)):
        if ob is None or touch[i+1]: continue
        m=l2[ob]==i+1; a=int(m.sum())
        if a<300 or a>6000: continue
        mf=ndi.binary_fill_holes(m)
        if mf.sum()/float(m.shape[0]*m.shape[1])<0.4: continue
        full=np.zeros_like(core); full[ob]=mf; out.append((a,full))
    out.sort(key=lambda t:-t[0]); return [m for _,m in out[:nmax]]
def to_frame(mask,zr,w):
    RS=float(np.interp(zr,zs_a,rs)); CS=float(np.interp(zr,zs_a,cs)); ys,xs=np.where(mask)
    rf=np.rint(RS+((H-1)-(w[0]+ys)/3.0)*sc).astype(int); cf=np.rint(110+CS+(w[2]+xs)/3.0*sc).astype(int)
    ok=(rf>=0)&(rf<480)&(cf>=0)&(cf<700); m1=np.zeros((480,700),bool); m1[rf[ok],cf[ok]]=True; return ndi.binary_closing(m1,iterations=1)
n=1739; out=np.zeros((n,480,700),np.uint8); report={}
for side,base,sgn in (("right",0,1),("left",2,-1)):
    V=np.load(D+f"arm_full_{side}.npy",mmap_mode="r"); sd=[]
    for zr in range(-568,-640,-4):   # seed slice: the first with two compact discs (800-3500 px) 40-140 px apart
        j0=ZR.index(zr); w=bb["windows"][str(ZI[j0])][side]; im=np.asarray(V[j0]); cand=[m for m in seeds(im,nmax=6) if 800<=m.sum()<=3500]
        pairs=[(a,b) for i,a in enumerate(cand) for b in cand[i+1:] if 40<=np.hypot(*(np.array(ndi.center_of_mass(a))-np.array(ndi.center_of_mass(b))))<=140]
        if pairs: sd=list(pairs[0]); break
    print(side,"seeds at z",zr,":",[(int(m.sum()),[int(v) for v in ndi.center_of_mass(m)]) for m in sd],flush=True)
    tracks=[]
    for si,seed in enumerate(sd):
        secs={j0:seed}; prev=seed; a0=seed.sum(); cy,cx=ndi.center_of_mass(seed); fails=0; j=j0
        while fails<10 and j+1<len(ZR):
            j+=1; w=bb["windows"][str(ZI[j])][side]; im=np.asarray(V[j]); c,cream,bc,body=masks(im)
            prior=ndi.binary_dilation(prev,iterations=6); cand=bc&prior
            if cand.sum()<50: cand=cream&prior
            l,m=ndi.label(cand)
            if m==0: fails+=1; continue
            sz=ndi.sum(np.ones_like(l),l,np.arange(1,m+1)); new=ndi.binary_fill_holes(ndi.binary_closing(l==(np.argmax(sz)+1),iterations=2))&prior; a=new.sum()
            ny,nx=ndi.center_of_mass(new); ring=ndi.binary_dilation(new,iterations=4)&~new; mus=float((c[ring]==3).mean())
            if mus<0.35: fails+=1; continue   # a bone section is wrapped in muscle; a section riding along the subcutaneous fat is not
            if a<0.65*prev.sum() or a>1.4*prev.sum() or a>2.5*a0 or abs(ny-cy)>10 or abs(nx-cx)>10: fails+=1; continue
            secs[j]=new; prev=new; cy,cx=ny,nx; fails=0
        tracks.append(secs); print(side,"seed",si,"tracked",len(secs),"slices, z",ZR[j0],"->",ZR[max(secs)],flush=True)
    r={}
    if len(tracks)==2:
        def wrist_col(secs):
            jj=max(secs); ys,xs=np.where(secs[jj]); return xs.mean()
        # lateral = away from the trunk: right side smaller crop x, left side larger crop x
        lat=[(-wrist_col(t))*sgn for t in tracks]; order=np.argsort(lat)[::-1]; names=["radius","ulna"]
        for nm,ti in zip(names,order):
            t=tracks[ti]; vol=0
            for j,m in t.items(): f=to_frame(m,ZR[j],bb["windows"][str(ZI[j])][side]); k=int(round(ZR[j]-z0)); out[k][f&(out[k]==0)]=base+1+names.index(nm); vol+=int(f.sum())
            r[nm]={"z_top":ZR[min(t)],"z_bot":ZR[max(t)],"len_mm":ZR[min(t)]-ZR[max(t)],"cm3":round(vol/1000,1),"slices":len(t)}
    report[side]=r; print(side,r,flush=True)
json.dump({"_README":["Female radius/ulna tracked through the full-resolution cryosections (scripts/cryo/vhf_forearm_track.py). Derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections via the NCI Imaging Data Commons.","report":report},open(D+"forearm_track_report.json","w"),indent=1)
nz=np.where(out.any(axis=(1,2)))[0]
if len(nz):
    k0,k1=nz.min(),nz.max()+1; aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+k0],[0,0,0,1]],float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(out[k0:k1].transpose(2,1,0)),aff),S+"vhf_ts/forearm_cryo.nii.gz")
    lut=np.array([[0,0,0],[255,60,60],[60,140,255],[255,60,60],[60,140,255]],np.uint8)
    Image.fromarray(lut[out[k0:k1].max(axis=1)][::-1]).save(D+"forearm_track_front.png"); Image.fromarray(lut[out[k0:k1].max(axis=2)][::-1]).save(D+"forearm_track_side.png")
print("TRACK_DONE")
