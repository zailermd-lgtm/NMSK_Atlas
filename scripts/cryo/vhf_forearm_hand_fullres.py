"""Female forearm and hand bones from the FULL-RESOLUTION (0.33 mm) cryosection crops (vhf_stream_arm_crops.py).
Per slice and side: colour classes; a bone is a cream marrow disc (class 2) bounded by its pale/white cortex line (classes 4/5, used as a wall so
the distal radius/ulna do not merge with the subcutaneous fat they lie on) -- opened by 4 px to cut the fat septa, never within 3 px (1 mm) of the outside of the body silhouette (the distal radius and ulna are subcutaneous), 300-6000 px
(3-650 mm2), compact (filled area / box >= 0.4) -- grown back to its edge. Anything within 4 mm of a CT bone label
(torso TotalSegmentator bones, lower-limb volume, mapped through the frame) is removed: the hip and thigh share the crop with the hand.
Slices above the CT humerus's lower end + 3 mm are ignored (the trochlea would join the ulna through the joint
cartilage, which is pale; the olecranon tip is therefore short). 3-D components at 1 mm slice spacing after bridging gaps of up to 8 slices where a disc overlaps itself (closing along z); per side
the two tallest (>= 120 mm) are the forearm bones, named at the wrist (radius = lateral); everything below the
lower of their distal ends is the hand, grouped by planes along the hand axis from the wrist (carpals < 45 mm,
metacarpals 45-115, phalanges beyond). Labels are written at 1 mm into the registered frame (n x 480 x 700) and
as vhf_ts/forearm_hand_cryo.nii.gz in torso RAS. Renders + a volume report (arm_fullres_report.json)."""
import numpy as np, json, nibabel as nib, sys
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0,"/home/user/NMSK_Atlas/scripts/cryo"); from cryo_classes import classify
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
bb=json.load(open(D+"arm_full_bbox.json")); ZR=bb["z_ras"]; ZI=bb["cryo_idx"]; fr=json.load(open(D+"frame.json")); z0=fr["z0"]
A=json.load(open(D+"anchors.json")); A=[a for a in A if a["flip"]=="fy" and a["iou"]>=0.7]
zs_a=np.array([a["ct_z"] for a in A]); rs=ndi.median_filter(np.array([a["shift"][0] for a in A],float),size=5,mode="nearest"); cs=ndi.median_filter(np.array([a["shift"][1] for a in A],float),size=5,mode="nearest")
o=np.argsort(zs_a); zs_a,rs,cs=zs_a[o],rs[o],cs[o]; H=405; sc=0.99
walk=json.load(open(D+"arm_walk_report.json")); HUM_BOT={"right":walk["right"]["humerus_z"][0],"left":walk["left"]["humerus_z"][0]}
legs=nib.load("/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz"); ld=legs.dataobj; zL0=float(legs.affine[2,3]); psL=abs(legs.affine[0,0])
ox=int(round(240-legs.affine[0,3])); oy=int(round(240-legs.affine[1,3]))
seg=nib.load("/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhf_total.nii.gz"); segd=seg.dataobj; zT0=float(seg.affine[2,3])
labs={v:int(k) for k,v in json.load(open("/home/user/NMSK_Atlas/mappings/totalsegmentator_labels.json"))["labels"].items()}
bone_ids=[v for k,v in labs.items() if any(t in k for t in ("vertebrae","rib","scapula","clavicula","hip","sacrum","femur","skull","sternum","costal"))]
def ct_bone_frame(zr):
    """Every CT bone (torso TotalSegmentator bones, lower-limb volume) at RAS z, in frame coords, dilated 4 mm: the thigh and hip share the crop with the hand."""
    f=np.zeros((480,700),bool); kT=int(round(zr-zT0))
    if 0<=kT<seg.shape[2]: f[:,110:590]|=np.isin(ndi.zoom(np.asarray(segd[:,:,kT]),480/512,order=0).T,bone_ids)
    kL=int(round(zr-zL0))
    if 0<=kL<legs.shape[2]:
        l2=ndi.zoom(np.asarray(ld[:,:,kL]),psL,order=0).T>0; H2,W2=l2.shape; rr=slice(max(oy,0),min(oy+H2,480)); cc=slice(max(ox,0),min(ox+W2,480))
        f[:,110:590][rr,cc]|=l2[rr.start-oy:rr.stop-oy,cc.start-ox:cc.stop-ox]
    return ndi.binary_dilation(f,iterations=4)
LAB={"radius":1,"ulna":2,"carpals":3,"metacarpals":4,"phalanges":5}
n=1739; out=np.zeros((n,480,700),np.uint8); report={}
for side,base in (("right",0),("left",5)):
    V=np.load(D+f"arm_full_{side}.npy",mmap_mode="r"); det=np.zeros((len(ZR),480,700),bool)
    for j,(zr,zi) in enumerate(zip(ZR,ZI)):
        if zr>HUM_BOT[side]+3: continue
        w=bb["windows"][str(zi)][side]; im=np.asarray(V[j][:w[1]-w[0],:w[3]-w[2]]); c=classify(im)
        cream=np.isin(c,[2,4,5]); wall=ndi.binary_dilation(np.isin(c,[4,5]),iterations=1)   # the pale/white cortex line is a WALL: distally the bones lie on the subcutaneous fat with no muscle between
        core=ndi.binary_opening((c==2)&~wall,iterations=4)
        body=ndi.binary_fill_holes(ndi.binary_closing(c>0,iterations=5)); nearbg=ndi.binary_dilation(~body,iterations=3)   # background = outside the body silhouette (dark marrow and blood are class 0 too, but inside)
        l2,n2=ndi.label(core); keep=np.zeros_like(cream)
        if n2:
            touch=np.zeros(n2+1,bool); touch[np.unique(l2[nearbg])]=True
            for i,ob in enumerate(ndi.find_objects(l2)):
                if ob is None or touch[i+1]: continue
                m=l2[ob]==i+1; a=int(m.sum())
                if a<300 or a>6000: continue
                mf=ndi.binary_fill_holes(m)
                if mf.sum()/float(m.shape[0]*m.shape[1])<0.4: continue
                keep[ob]|=mf
        b=ndi.binary_fill_holes(ndi.binary_dilation(keep,iterations=4)&cream)
        if not b.any(): continue
        # crop px -> frame (1 mm): r=(w0+y)/3, c=(w2+x)/3 ; row_f=RS+((H-1)-r)*sc ; col_f=110+CS+c*sc
        RS=float(np.interp(zr,zs_a,rs)); CS=float(np.interp(zr,zs_a,cs)); ys,xs=np.where(b)
        rf=np.rint(RS+((H-1)-(w[0]+ys)/3.0)*sc).astype(int); cf=np.rint(110+CS+(w[2]+xs)/3.0*sc).astype(int)
        ok=(rf>=0)&(rf<480)&(cf>=0)&(cf<700); m1=np.zeros((480,700),bool); m1[rf[ok],cf[ok]]=True; m1=ndi.binary_closing(m1,iterations=1)
        m1&=~ct_bone_frame(zr); det[j]=m1
    det=ndi.binary_closing(det,structure=np.ones((9,3,3)))|det   # a disc missed on a few slices (a septum touching it, a cut artefact) must not break the bone: bridge gaps of up to 8 slices where the disc overlaps itself
    cl,m=ndi.label(det,structure=np.ones((3,3,3))); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1)); objs=ndi.find_objects(cl)
    comps=[]
    for i in range(m):
        if objs[i] is None or sizes[i]<200: continue
        ob=objs[i]; sub=cl[ob]==i+1; idx=np.argwhere(sub)+[s.start for s in ob]
        comps.append(dict(i=i+1,cm3=round(float(sizes[i])/1000,1),ext=int(idx[:,0].max()-idx[:,0].min()),z_top=ZR[idx[:,0].min()],z_bot=ZR[idx[:,0].max()],col=float(idx[:,2].mean()),row=float(idx[:,1].mean())))
    comps.sort(key=lambda c:-c["ext"]); print(side,"components",[(c["cm3"],c["ext"],c["z_top"],c["z_bot"],round(c["col"])) for c in comps[:8]],flush=True)
    r={}; longs=[]
    for c in [c for c in comps if c["ext"]>=100]:   # the two forearm bones: tallest pair with overlapping z ranges, centroids < 45 mm apart
        if not longs: longs=[c]; continue
        a=longs[0]; ov=min(a["z_top"],c["z_top"])-max(a["z_bot"],c["z_bot"])
        if ov>=0.5*min(a["ext"],c["ext"]) and abs(a["col"]-c["col"])+abs(a["row"]-c["row"])<45: longs.append(c); break
    kmap={zr:int(round(zr-z0)) for zr in ZR}   # frame slice index of each crop slice
    def to_frame(mask3):
        for j in range(len(ZR)): out[kmap[ZR[j]]][mask3[j]]=0
    if len(longs)==2:
        Ma,Mb=(cl==longs[0]["i"]),(cl==longs[1]["i"]); sgn=1 if side=="right" else -1
        def wrist_col(M):
            jj=np.where(M.any(axis=(1,2)))[0].max(); ys,xs=np.where(M[jj]); return xs.mean()
        rad,uln=(Ma,Mb) if (350-wrist_col(Ma))*sgn>(350-wrist_col(Mb))*sgn else (Mb,Ma)
        for nm,M in (("radius",rad),("ulna",uln)):
            jj=np.where(M.any(axis=(1,2)))[0]; r[nm+"_z"]=[ZR[jj.max()],ZR[jj.min()]]; r[nm+"_cm3"]=round(float(M.sum())/1000,1)
            for j in jj: out[kmap[ZR[j]]][M[j]]=base+LAB[nm]
        wrist=min(np.where(rad.any(axis=(1,2)))[0].max(),np.where(uln.any(axis=(1,2)))[0].max())
        hm=det&~rad&~uln; hm[:wrist+1]=False; idx=np.argwhere(hm)
        if len(idx)>2000:
            mu=idx.mean(0); u=np.linalg.svd(idx-mu,full_matrices=False)[2][0]
            if u[0]<0: u=-u   # fingers point toward larger j (lower z)
            t=(idx-mu)@u; t-=np.percentile(t,0.5); g=np.where(t<45,0,np.where(t<115,1,2))
            for (j,y,x),gg in zip(idx,g): out[kmap[ZR[j]],y,x]=base+LAB["carpals"]+gg
            r["hand_len_mm"]=round(float(t.max())); r["carpals_cm3"],r["metacarpals_cm3"],r["phalanges_cm3"]=[round(float((out==base+LAB["carpals"]+q).sum())/1000,1) for q in range(3)]
    else: r["forearm"]="fewer than two long components"
    report[side]=r; print(side,r,flush=True)
json.dump({"_README":["Female forearm and hand bone volumes from the full-resolution cryosection crops (scripts/cryo/vhf_forearm_hand_fullres.py). Derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections via the NCI Imaging Data Commons.","report":report},open(D+"arm_fullres_report.json","w"),indent=1)
np.save(D+"forearm_hand_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0],[0,0,0,1]],float)
nz=np.where(out.any(axis=(1,2)))[0]
if len(nz):
    k0,k1=nz.min(),nz.max()+1; aff2=aff.copy(); aff2[2,3]=z0+k0
    nib.save(nib.Nifti1Image(np.ascontiguousarray(out[k0:k1].transpose(2,1,0)),aff2),S+"vhf_ts/forearm_hand_cryo.nii.gz")
    lut=np.array([[0,0,0],[255,60,60],[60,140,255],[255,220,60],[255,120,200],[90,230,120],[255,60,60],[60,140,255],[255,220,60],[255,120,200],[90,230,120]],np.uint8)
    p=out[k0:k1].max(axis=1); Image.fromarray(lut[p][::-1]).save(D+"forearm_hand_front.png"); p2=out[k0:k1].max(axis=2); Image.fromarray(lut[p2][::-1]).save(D+"forearm_hand_side.png")
print("FULLRES_DONE")
