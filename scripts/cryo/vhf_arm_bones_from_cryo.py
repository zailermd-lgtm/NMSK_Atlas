"""Female upper-limb bones from her cryosection photographs (the CT clips the arms). In the registered frame
(vhf_resample_cryo.py: rows 480, cols 700, frame col = CT col + 110) a bone cross-section is a pale/white cortical
ring (colour classes 4 and 5) with cream marrow: ring closed by 1 px around a hole under 2000 mm2 (the skin line rings the whole body and is not a bone), over the arm
levels (RAS z -180 .. -980) in the two lateral column bands. Everything within 6 mm of a CT bone label other than
the humerus (TotalSegmentator `total` on her torso block, and her lower-limb bone volume) is removed so the ribs,
scapulae, clavicles, pelvis and femora do not enter. 3-D components (26-connected) >= 3 cm3 are reported with
extent and centroid, then named per side by position: humerus = the tallest component whose top lies above the
CT humerus label's bottom; radius/ulna = the two tallest components below it (radius the more lateral at the
wrist... reported, then reviewed against the renders); hand = the rest below the forearm bones' lower ends.
Step 1 (this version) writes the candidate volume and renders; naming follows once the renders are read."""
import numpy as np, json, nibabel as nib
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); rgb=np.load(D+"cryo_frame_rgb.npy",mmap_mode="r"); fr=json.load(open(D+"frame.json")); z0=fr["z0"]
ZT,ZB=-180,-980; k0,k1=int(round(ZB-z0)),int(round(ZT-z0)); n=k1-k0
seg=nib.load("/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhf_total.nii.gz"); segd=seg.dataobj; zT0=float(seg.affine[2,3])
labs={v:int(k) for k,v in json.load(open("/home/user/NMSK_Atlas/mappings/totalsegmentator_labels.json"))["labels"].items()}
HUM=(labs["humerus_left"],labs["humerus_right"])
bone_ids=[v for k,v in labs.items() if any(t in k for t in ("vertebrae","rib","scapula","clavicula","hip","sacrum","femur","skull","sternum","costal"))]
legs=nib.load("/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz"); ld=legs.dataobj; zL0=float(legs.affine[2,3]); psL=abs(legs.affine[0,0])
ox=int(round(240-legs.affine[0,3])); oy=int(round(240-legs.affine[1,3]))
def ct_excl(zr):
    ex=np.zeros((480,480),bool); hum=np.zeros((480,480),bool); kT=int(round(zr-zT0))
    if 0<=kT<seg.shape[2]:
        l=ndi.zoom(np.asarray(segd[:,:,kT]),480/512,order=0).T; ex|=np.isin(l,bone_ids); hum|=np.isin(l,HUM)
    kL=int(round(zr-zL0))
    if 0<=kL<legs.shape[2]:
        l2=ndi.zoom(np.asarray(ld[:,:,kL]),psL,order=0).T; H2,W2=l2.shape; rr=slice(max(oy,0),min(oy+H2,480)); cc=slice(max(ox,0),min(ox+W2,480))
        ex[rr,cc]|=l2[rr.start-oy:rr.stop-oy,cc.start-ox:cc.stop-ox]>0
    return ex,hum
bone=np.zeros((n,480,700),bool); humct=np.zeros((n,480,700),bool)
for j in range(n):
    k=k0+j; zr=z0+k; c=np.asarray(cls[k])
    # her bone cross-sections photograph as CREAM discs (marrow + cortex, colour class 2/5) enclosed by muscle: unlike the
    # subcutaneous fat they never touch the background. Keep cream components that are (a) not within 3 px of background,
    # (b) 20-2500 mm2, (c) compact (filled area / bounding-box area >= 0.45) -- the intermuscular fat septa are thin.
    cream=np.isin(c,[2,4,5]); core=ndi.binary_opening(cream,iterations=3); nearbg=ndi.binary_dilation(c==0,iterations=3)   # opening by 3 cuts the thin fat septa that tie a bone disc to the subcutaneous fat
    l2,n2=ndi.label(core); keep=np.zeros_like(cream)
    if n2:
        touch=np.zeros(n2+1,bool); touch[np.unique(l2[nearbg])]=True
        for i,o in enumerate(ndi.find_objects(l2)):
            if o is None or touch[i+1]: continue
            m=l2[o]==i+1; a=int(m.sum())
            if a<20 or a>2500: continue
            mf=ndi.binary_fill_holes(m)
            if mf.sum()/float(m.shape[0]*m.shape[1])<0.45: continue
            keep[o]|=mf
    b=ndi.binary_dilation(keep,iterations=3)&cream; b=ndi.binary_fill_holes(b)   # grow the kept cores back to the disc's true edge
    ex,hum=ct_excl(zr); full=np.zeros((480,700),bool); full[:,110:590]=ndi.binary_dilation(ex,iterations=6); b&=~full
    b[:,260:440]=False   # trunk midline band: never an arm
    bone[j]=b; humct[j][:,110:590]=hum
cl,m=ndi.label(bone,structure=np.ones((3,3,3))); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1)); objs=ndi.find_objects(cl)
rows=[]
for i in range(m):
    if sizes[i]<3000 or objs[i] is None: continue
    o=objs[i]; sub=cl[o]==i+1; idx=np.argwhere(sub)+[s.start for s in o]
    rows.append(dict(i=i+1,cm3=round(float(sizes[i])/1000,1),z_top=float(z0+k0+idx[:,0].max()),z_bot=float(z0+k0+idx[:,0].min()),ext=int(idx[:,0].max()-idx[:,0].min()),row=float(idx[:,1].mean()),col=float(idx[:,2].mean()),hum_overlap=int((sub&humct[o]).sum())))
rows.sort(key=lambda r:-r["cm3"])
for r in rows[:30]: print(r,flush=True)
json.dump(rows,open(D+"arm_bone_candidates.json","w"),indent=1); np.save(D+"arm_bone_components.npy",cl.astype(np.int32))
lut=np.random.RandomState(1).randint(60,255,(m+1,3)).astype(np.uint8); lut[0]=0
front=np.zeros((n,700,3),np.uint8); side=np.zeros((n,480,3),np.uint8)
for j in range(n):
    p=cl[j].max(axis=0); front[j]=lut[p]; q=cl[j].max(axis=1); side[j]=lut[q]
lum=np.array([np.asarray(rgb[k0+j]).max(-1).max(axis=0)//3 for j in range(n)]); bg=np.repeat(lum[...,None],3,2)
Image.fromarray(np.where(front>0,front,bg)[::-1]).save(D+"arm_bones_front.png"); Image.fromarray(side[::-1]).save(D+"arm_bones_side.png"); print("STEP1_DONE",len(rows))

# ---------------- step 2: walk the long bones through the photographs, group the hand ----------------
# humerus: seed = her CT humerus label (TotalSegmentator, proximal part inside the CT field of view) shifted onto
# the photograph by masked cross-correlation, then walked distally slice by slice (next = largest cream component
# inside the previous section dilated by 2, closed, filled; area within [0.5, 1.3] x previous; stops when the area
# falls under 40 % of its running maximum = the trochlea has ended). Radius / ulna: seeds = the two largest step-1
# candidates with centroid z in [-720, -560] (mid-forearm, where both are clean discs), walked proximally to the
# elbow (stop on touching the humerus) and distally to the wrist; named at the wrist: radius = the lateral one.
# Hand: every step-1 candidate voxel below the forearm bones' lower ends, grouped by planes along the hand's long
# axis from the wrist (carpals < 45 mm, metacarpals 45-115, phalanges beyond) -- the male's hand rule.
from scipy.signal import fftconvolve
def cream_of(j): return ndi.binary_opening(np.isin(np.asarray(cls[k0+j]),[2,4,5]),iterations=1)
LAB={"humerus":1,"radius":2,"ulna":3,"carpals":4,"metacarpals":5,"phalanges":6}
out=np.zeros((n,480,700),np.uint8); rep2={}
def walk(prev,j,direction,cols,stop_mask=None,maxsteps=400,tight=False):
    """tight: forearm rules -- area ratio per step within [0.75, 1.25], never above 2 x the seed, centroid jump <= 6 px,
    and the section must stay enclosed by tissue (no background within 3 px)."""
    M=np.zeros((n,480,700),bool); amax=prev.sum(); a0=prev.sum(); med=a0; steps=0
    cy,cx=ndi.center_of_mass(prev)
    while steps<maxsteps:
        j+=direction
        if j<0 or j>=n: break
        c=np.asarray(cls[k0+j])[:,cols]; cr=ndi.binary_opening(np.isin(c,[2,4,5]),iterations=1); prior=ndi.binary_dilation(prev,iterations=2); cand=cr&prior
        l,m=ndi.label(cand)
        if m==0: break
        sz=ndi.sum(np.ones_like(l),l,np.arange(1,m+1)); new=ndi.binary_fill_holes(ndi.binary_closing(l==(np.argmax(sz)+1),iterations=1))&prior; a=new.sum()
        if tight:
            if a<15 or a>1.25*prev.sum() or a<0.75*prev.sum() or a>2.0*a0: break
            ny,nx=ndi.center_of_mass(new)
            if abs(ny-cy)>6 or abs(nx-cx)>6: break
            if (ndi.binary_dilation(new,iterations=3)&(c==0)).any(): break
            cy,cx=ny,nx
        else:
            hi=1.3*max(prev.sum(),med) if steps<10 else 1.3*prev.sum()
            if a<15 or a>hi or a<0.5*prev.sum(): break
        if stop_mask is not None and (stop_mask[j][:,cols]&ndi.binary_dilation(new,iterations=1)).any(): break
        amax=max(amax,a)
        if not tight and a<0.4*amax: break
        M[j][:,cols]=new; prev=new; steps+=1
    return M,steps
cands=json.load(open(D+"arm_bone_candidates.json"))
for side,cols,sgn in (("right",slice(0,260),1),("left",slice(440,700),-1)):
    base=0 if side=="right" else 6; r={}
    # --- humerus
    hk=[j for j in range(n) if humct[j][:,cols].sum()>=40]
    if not hk: print(side,"no CT humerus in band"); continue
    shifts=[]
    for j in hk[::5]:
        m=humct[j][:,cols]; cr=cream_of(j)[:,cols]&ndi.binary_dilation(m,iterations=25)
        a=m.astype(np.float32)-m.mean(); bb=cr.astype(np.float32)-cr.mean(); cc=fftconvolve(bb,a[::-1,::-1],mode="same"); iy,ix=np.unravel_index(np.argmax(cc),cc.shape)
        shifts.append((iy-a.shape[0]//2,ix-a.shape[1]//2))
    dy,dx=[int(np.median([s[i] for s in shifts])) for i in (0,1)]; r["humerus_ct_to_photo_shift_px"]=[dy,dx]; r["humerus_ct_slices"]=len(hk)
    areas={j:int(humct[j][:,cols].sum()) for j in hk}; med=np.median(list(areas.values()))
    jseed=min(j for j in hk if areas[j]>=0.6*med)   # lowest solid CT slice (index grows upward)
    hum=np.zeros((n,480,700),bool)
    for j in hk:
        if j>=jseed: hum[j][:,cols]=np.roll(np.roll(humct[j][:,cols],dy,0),dx,1)
    prev=hum[jseed][:,cols]; M,steps=walk(prev,jseed,-1,cols); hum|=M; r["humerus_walk_steps"]=steps
    hz=np.where(hum.any(axis=(1,2)))[0]; r["humerus_z"]=[float(z0+k0+hz.min()),float(z0+k0+hz.max())]; r["humerus_cm3"]=round(float(hum.sum())/1000,1)
    out[hum]=base+LAB["humerus"]; elbow_j=int(hz.min())
    # --- radius / ulna
    band=[c for c in cands if (sgn>0 and c["col"]<260) or (sgn<0 and c["col"]>=440)]
    pool=sorted([c for c in band if -740<=(c["z_top"]+c["z_bot"])/2<=-560 and c["ext"]>=8],key=lambda c:-c["cm3"]); fs=[]
    for c in pool:   # two DISTINCT bones: centroids at least 8 px apart in-plane
        if all(abs(c["row"]-f["row"])+abs(c["col"]-f["col"])>=8 for f in fs): fs.append(c)
        if len(fs)==2: break
    bones={}
    for c in fs:
        j=int(round((c["z_top"]+c["z_bot"])/2-z0-k0)); seed=(cl[j]==c["i"])[:,cols]
        up,su=walk(seed,j,+1,cols,stop_mask=hum,tight=True); dn,sd=walk(seed,j,-1,cols,tight=True)
        M=up|dn; M[j][:,cols]=seed; bones[c["i"]]=M; print(side,"forearm seed",c["i"],"steps up",su,"down",sd,flush=True)
    if len(bones)==2:
        (ia,Ma),(ib,Mb)=bones.items()
        def wrist_col(M):
            z=np.where(M.any(axis=(1,2)))[0]; jj=z.min(); ys,xs=np.where(M[jj]); return xs.mean()
        # lateral = away from the midline (col 350): right side smaller col, left side larger col
        lat_a=(350-wrist_col(Ma))*sgn; lat_b=(350-wrist_col(Mb))*sgn
        rad,uln=(Ma,Mb) if lat_a>lat_b else (Mb,Ma)
        out[rad&(out==0)]=base+LAB["radius"]; out[uln&(out==0)]=base+LAB["ulna"]
        for nm,M in (("radius",rad),("ulna",uln)):
            z=np.where(M.any(axis=(1,2)))[0]; r[nm+"_z"]=[float(z0+k0+z.min()),float(z0+k0+z.max())]; r[nm+"_cm3"]=round(float(M.sum())/1000,1)
        wrist_j=int(min(np.where(rad.any(axis=(1,2)))[0].min(),np.where(uln.any(axis=(1,2)))[0].min()))
    else:
        r["forearm"]="seeds not found: %d"%len(bones); wrist_j=None
    # --- hand
    if wrist_j is not None:
        hm=np.zeros((n,480,700),bool); hm[:wrist_j][:, :, cols]=(bone[:wrist_j][:, :, cols])&(out[:wrist_j][:, :, cols]==0)
        idx=np.argwhere(hm)
        if len(idx)>2000:
            mu=idx.mean(0).astype(float); u=np.linalg.svd(idx-mu,full_matrices=False)[2][0]
            if u[0]>0: u=-u   # fingers point downward (decreasing z index)
            t=(idx-mu)@u; t-=np.percentile(t,0.5); g=np.where(t<45,0,np.where(t<115,1,2)); out[tuple(idx.T)]=base+LAB["carpals"]+g
            r["hand_len_mm"]=round(float(t.max())); r["carpals_cm3"],r["metacarpals_cm3"],r["phalanges_cm3"]=[round(float((out==base+LAB["carpals"]+q).sum())/1000,1) for q in range(3)]
    rep2[side]=r; print(side,r,flush=True)
json.dump(rep2,open(D+"arm_walk_report.json","w"),indent=1); np.save(D+"arm_bones_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+k0],[0,0,0,1]],float)
nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhf_ts/arm_bones_cryo.nii.gz")
lut2=np.array([[0,0,0],[220,220,220],[255,60,60],[60,140,255],[255,220,60],[255,120,200],[90,230,120],[220,220,220],[255,60,60],[60,140,255],[255,220,60],[255,120,200],[90,230,120]],np.uint8)
p=out.max(axis=1); img=np.where(p[...,None]>0,lut2[p],bg).astype(np.uint8); Image.fromarray(img[::-1]).save(D+"arm_walk_front.png")
p2=out.max(axis=2); Image.fromarray(lut2[p2][::-1]).save(D+"arm_walk_side.png"); print("STEP2_DONE")
