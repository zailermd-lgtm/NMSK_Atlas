"""Visible Human FEMALE lower-limb bones from her femur-to-toes CT (IDC series af18f5e4, fresh cadaver,
0.72 mm), registered to her torso block, written as a label volume in the TORSO block's RAS frame.

    python3 scripts/vhf_lower_limb_bones.py LEGS_CT.nii.gz [--torso-seg data/ct_sources/task_outputs/vhf_total.nii.gz]
                                             [--out data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz]

No free TotalSegmentator task labels bones below the femur, so this is threshold + shape:
  bone = HU >= 200; scanner-table/FOV lines (columns present in > 60 % of slices) removed; components taller
  than 450 mm dropped (edge junk). Per side the medullary canals are filled (2-D holes < 300 mm2 that persist as a tube >= 40 mm tall, so joint spaces stay
  open), the bone cores >= 3.5 mm from the surface (distance transform) seed markers, a watershed on the distance
  transform grows them back over the mask, and fragments whose common boundary is thick bone (saddle height >= 2 mm)
  are re-united. What stays apart is separated by a thin partial-volume sheet: the joint contacts (knee, ankle,
  tibiofibular, tarsal). Then, per side (RAS x sign):
    femur   = the component reaching the top of the block (registration, and label 13/14 below);
    tibia   = largest remaining component > 250 mm tall; fibula = split from that label slice by slice (the smaller, lateral
              2-D component; touching slices by a 2-D watershed seeded from the neighbouring slice), plus any
              lateral piece the 3-D watershed had left apart;
    patella = largest 5-60 cm3 component anterior (+y) of the distal femur, within its z window;
    femur   = the block's femur united with the torso block's TotalSegmentator femur (labels 13/14, the grid is
              extended 200 slices upward to hold the head);
    foot    = every component below the tibia's lower end, grouped by planes along the foot's long axis from
              the heel: tarsals < 115 mm, metatarsals 115-190 mm, phalanges beyond (the male CT feet planes).
Registration: the legs block starts at mid-thigh, so no femoral head is shared with the torso block. The
shift comes from CONTINUITY across the junction: a quadratic fitted to the inter-femur distance (centroid
distance of the two femoral shafts, per slice) over the torso's bottom 24 slices and the legs block's top 24
slices, for candidate z shifts at 0.25 mm; x/y from the femur centroids extrapolated to the junction plane.
A first run (with TotalSegmentator femurs on the legs block, lost with the container) gave the same answer
from body area (-943.5) and subcutaneous-fat area (-942.5): z = -943.5 +- 4 mm. Femur cross-section areas
disagree by ~7 mm (a ~2 % partial-volume bias between the two grids) and are not used.
Label ids follow mappings/vhf_legs_labels.json. A report JSON (volumes, extents, registration) is written
next to the output."""
import argparse, json, numpy as np, nibabel as nib
from pathlib import Path
from scipy import ndimage as ndi
from skimage.segmentation import watershed
ap=argparse.ArgumentParser(); ap.add_argument("legs_ct"); ap.add_argument("--torso-seg",default="data/ct_sources/task_outputs/vhf_total.nii.gz")
ap.add_argument("--out",default="data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz"); ap.add_argument("--z-prior",type=float,default=-943.5); ap.add_argument("--keep-components",action="store_true")
a=ap.parse_args()
MARKER_MM=3.5; SADDLE_MM=2.0   # a bone core must be at least this far from the bone surface to seed a label: opens joint contacts (ankle, tibiofibular, tarsal) that are thin bridges in the HU>=200 mask
_labs={v:int(k) for k,v in json.load(open(Path(__file__).resolve().parents[1]/"mappings"/"totalsegmentator_labels.json"))["labels"].items()}
FEMUR_R,FEMUR_L=_labs["femur_right"],_labs["femur_left"]   # TotalSegmentator v2 `total` ids (76, 75)
im=nib.load(a.legs_ct); A=im.affine; zm=im.header.get_zooms(); vox=float(np.prod(zm)); sh=im.shape
bone=np.zeros(sh,bool)
for k0 in range(0,sh[2],100):
    c=np.asarray(im.dataobj[:,:,k0:k0+100]); bone[:,:,k0:k0+100]=c>=200; del c
bone[:5]=False; bone[-5:]=False; bone[:,:5]=False; bone[:,-5:]=False; bone[:,:,:3]=False; bone[:,:,-3:]=False
col=bone.sum(axis=2); bone[col>0.6*sh[2]]=False
cl0,n0=ndi.label(bone,structure=np.ones((3,3,3)))
for i,o in enumerate(ndi.find_objects(cl0)):
    if o is None: continue
    ext=(o[2].stop-o[2].start)*zm[2]; nv=int((cl0[o]==i+1).sum())
    if ext>450 and nv*vox/ext<150: bone[cl0==i+1]=False   # a line thinner than 150 mm2 in section running >450 mm: FOV/table edge, not bone
del cl0; print("bone voxels",int(bone.sum()),flush=True)
cl=np.zeros(sh,np.int32); nlab=0
xr=A[0,3]+np.arange(sh[0])*A[0,0]
for sgn in (1,-1):
    b=bone.copy(); b[sgn*xr<=0]=False
    if not b.any(): continue
    o=ndi.find_objects(b.astype(np.uint8))[0]; sub=b[o]; del b
    # medullary canals: 2-D holes < 300 mm2 that persist as a tube >= 40 mm tall. A cortical ring 2 voxels thick would
    # not seed a marker; joint spaces (ankle crescents, tarsal joints) are enclosed for a few slices only and stay open.
    holes=np.zeros_like(sub)
    for k in range(sub.shape[2]):
        sl=sub[:,:,k]; h=ndi.binary_fill_holes(sl)&~sl
        if h.any():
            hl,hn=ndi.label(h); hs=ndi.sum(np.ones_like(hl,dtype=np.uint8),hl,np.arange(1,hn+1)); holes[:,:,k]=np.isin(hl,np.arange(1,hn+1)[hs*zm[0]*zm[1]<300])
    hl,hn=ndi.label(holes,structure=np.ones((3,3,3)))
    for i,ho in enumerate(ndi.find_objects(hl)):
        if ho is not None and (ho[2].stop-ho[2].start)*zm[2]<40: holes[ho][hl[ho]==i+1]=False
    del hl; filled=sub|holes; del holes
    dist=ndi.distance_transform_edt(filled,sampling=zm).astype(np.float32); del filled
    mk,n=ndi.label(dist>=MARKER_MM,structure=np.ones((3,3,3))); sizes=ndi.sum(np.ones_like(mk),mk,np.arange(1,n+1))
    mk[np.isin(mk,np.arange(1,n+1)[sizes<50])]=0
    w=watershed(-dist,mk,mask=sub).astype(np.int32); del mk
    # the distance-transform watershed cuts at EVERY constriction (femoral condyles, fibular shaft). Fragments whose common
    # boundary is thick bone (saddle height >= SADDLE_MM) are re-united; a joint bridge is a 1-voxel partial-volume sheet.
    parent=np.arange(w.max()+1)
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    K=int(w.max())+1; sad={}
    for ax in range(3):
        sl0=[slice(None)]*3; sl1=[slice(None)]*3; sl0[ax]=slice(None,-1); sl1[ax]=slice(1,None)
        a_=w[tuple(sl0)]; b_=w[tuple(sl1)]; m=(a_!=b_)&(a_>0)&(b_>0)
        if not m.any(): continue
        lo=np.minimum(a_[m],b_[m]); hi=np.maximum(a_[m],b_[m]); d=np.maximum(dist[tuple(sl0)][m],dist[tuple(sl1)][m])
        key=lo.astype(np.int64)*K+hi; uk,inv_=np.unique(key,return_inverse=True); mx=np.zeros(len(uk),np.float32); np.maximum.at(mx,inv_,d)
        for kk,v in zip(uk,mx): sad[int(kk)]=max(sad.get(int(kk),0.0),float(v))
        del a_,b_,m,lo,hi,d,key
    del dist
    nmerge=0
    for kk,v in sad.items():
        if v>=SADDLE_MM:
            ra,rb=find(kk//K),find(kk%K)
            if ra!=rb: parent[rb]=ra; nmerge+=1
    lut=np.array([find(i) for i in range(K)],np.int32); w=lut[w]; print("side",sgn,"fragments",K-1,"merged",nmerge,flush=True)
    rest,nr=ndi.label(sub&(w==0),structure=np.ones((3,3,3)))   # bones too small to survive the erosion (distal phalanges, sesamoids) keep their own labels
    w[rest>0]=rest[rest>0]+w.max(); del rest
    w[w>0]+=nlab; view=cl[o]; view[sub]=w[sub]; nlab=int(cl.max()); del w,sub
    print("side",sgn,"labels so far",nlab,flush=True)
np.save(str(Path(a.out).with_suffix('')).replace('.nii','')+'_components.npy',cl) if a.keep_components else None
n=nlab; objs=ndi.find_objects(cl); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,n+1))
ztop=A[2,3]+(sh[2]-4)*A[2,2]

def split_fibula(mask,sgn):
    """Tibia and fibula from one merged label, slice by slice. On most slices the two are separate 2-D components
    (the smaller, more lateral one is the fibula); where they touch (proximal tibiofibular joint, syndesmosis) the
    slice is split by a 2-D watershed seeded from the nearest already-assigned slice."""
    nz=mask.shape[2]; fib=np.zeros_like(mask); assigned=np.zeros(nz,bool); clean=[]
    ks=np.argwhere(mask.any(axis=(0,1))).ravel(); k0,k1=ks.min(),ks.max()
    for k in range(nz):
        sl=mask[:,:,k]
        if not sl.any() or k<k0+0.15*(k1-k0) or k>k1-0.15*(k1-k0): continue   # seed only from the shaft; the ends (plateau, plafond) are reached by propagation
        l2,n2=ndi.label(sl,structure=np.ones((3,3))); 
        if n2<2: continue
        ar=ndi.sum(np.ones_like(l2),l2,np.arange(1,n2+1))*zm[0]*zm[1]; big=np.argsort(ar)[::-1][:2]
        if ar[big[1]]<30: continue
        cx=[ndi.center_of_mass(l2==b+1)[0] for b in big]; xr_=[A[0,3]+c*A[0,0] for c in cx]
        f=big[1] if sgn*(xr_[1]-xr_[0])>0 else big[0]      # the more lateral of the two large pieces
        if f==big[0] or ar[f]>0.6*ar[big[0]]: continue   # the lateral piece must be the clearly smaller one, or this is not a tibia/fibula pair
        fib[:,:,k]=l2==f+1; assigned[k]=True; clean.append(k)
    if not clean: return mask,fib
    order=sorted([k for k in range(nz) if mask[:,:,k].any() and not assigned[k]],key=lambda k:min(abs(k-c) for c in clean))
    for k in order:
        near=[j for j in (k-1,k+1) if 0<=j<nz and assigned[j]]
        if not near: assigned[k]=True; continue
        j=near[0]; sl=mask[:,:,k]; pf=ndi.binary_erosion(fib[:,:,j])&sl; pt=ndi.binary_erosion(mask[:,:,j]&~fib[:,:,j])&sl
        if pf.any() and pt.any():
            mk=np.zeros(sl.shape,np.int32); mk[pt]=1; mk[pf]=2; d=ndi.distance_transform_edt(sl,sampling=zm[:2]); fib[:,:,k]=watershed(-d,mk,mask=sl)==2
        elif pf.any() and not pt.any(): fib[:,:,k]=sl
        assigned[k]=True
    return mask&~fib,fib

out=np.zeros(sh,np.uint8); report={}; femur_mask={}
for side,sgn,base in (("right",1,0),("left",-1,6)):
    comps=[]
    for i in range(n):
        if objs[i] is None or sizes[i]<300: continue
        m=cl[objs[i]]==i+1; idx=np.argwhere(m)+[o.start for o in objs[i]]; r=nib.affines.apply_affine(A,idx)
        if sgn*r[:,0].mean()<=0: continue
        comps.append(dict(i=i+1,n=int(sizes[i]),zmin=r[:,2].min(),zmax=r[:,2].max(),cx=r[:,0].mean(),cy=r[:,1].mean(),cz=r[:,2].mean(),ext=r[:,2].max()-r[:,2].min()))
    for c in sorted(comps,key=lambda c:-c["n"])[:12]: print(side,"comp",c["i"],"n",c["n"],"z",round(c["zmin"]),round(c["zmax"]),"ext",round(c["ext"]),"cx",round(c["cx"]),"cy",round(c["cy"]),flush=True)
    tops=[c for c in comps if c["zmax"]>=ztop-6 and c["ext"]>150]
    if not tops: print(side,"no femur reaching the top"); continue
    fe=max(tops,key=lambda c:c["n"]); femur_mask[side]=cl==fe["i"]; fz_min=fe["zmin"]
    fr=nib.affines.apply_affine(A,np.argwhere(femur_mask[side])); fy=fr[fr[:,2]<fz_min+60][:,1].mean()
    longs=sorted([c for c in comps if c["i"]!=fe["i"] and c["ext"]>250],key=lambda c:-c["n"])
    rep={"femur_in_block_cm3":round(fe["n"]*vox/1000,1),"femur_in_block_len_mm":round(fe["ext"])}
    if not longs: print(side,"tibia not found"); report[side]=rep; continue
    tib=longs[0]; tm=cl==tib["i"]
    if tib["ext"]>420: print(side,"WARNING tibia component too tall (joined to the foot?)",round(tib["ext"]),flush=True)
    # fibula: lateral pieces beside the tibia (if the watershed left any), plus the slice-wise split of the tibia label
    fibs=[c for c in comps if c["i"] not in (tib["i"],fe["i"]) and c["ext"]>40 and c["zmin"]>tib["zmin"]-15 and c["zmax"]<tib["zmax"]+15 and sgn*(c["cx"]-tib["cx"])>10]
    tm,fm=split_fibula(tm,sgn); fm|=np.isin(cl,[c["i"] for c in fibs]); out[tm]=base+1; out[fm]=base+2
    fz=np.argwhere(fm.any(axis=(0,1))).ravel(); fib=dict(n=int(fm.sum()),ext=float((fz.max()-fz.min())*zm[2]) if len(fz) else 0.0)
    rep.update({"tibia_cm3":round(float(tm.sum())*vox/1000,1),"tibia_len_mm":round(tib["ext"]),"fibula_cm3":round(fib["n"]*vox/1000,1),"fibula_len_mm":round(fib["ext"]),"fibula_pieces_from_watershed":len(fibs)})
    used={tib["i"],fe["i"]}|{c["i"] for c in fibs}
    pat=[c for c in comps if c["i"] not in used and c["cz"]>tib["zmax"]-40 and c["cz"]<fz_min+80 and c["cy"]>fy+15 and 5000<c["n"]*vox<60000]
    if pat: p=max(pat,key=lambda c:c["n"]); out[cl==p["i"]]=base+3; used.add(p["i"]); rep["patella_cm3"]=round(p["n"]*vox/1000,1)
    foot=[c for c in comps if c["i"] not in used and c["cz"]<tib["zmin"]+45 and c["n"]*vox>200]
    fm=np.isin(cl,[c["i"] for c in foot])
    if fm.any():
        idx=np.argwhere(fm); r=nib.affines.apply_affine(A,idx.astype(float)); mu=r.mean(0); u=np.linalg.svd(r-mu,full_matrices=False)[2][0]
        if u[1]<0: u=-u
        t=(r-mu)@u; t-=np.percentile(t,0.5); g=np.where(t<115,0,np.where(t<190,1,2)).astype(np.uint8); out[tuple(idx.T)]=base+4+g
        rep["foot_len_mm"]=round(float(t.max())); rep["foot_pieces"]=len(foot)
        rep["tarsals_cm3"],rep["metatarsals_cm3"],rep["phalanges_cm3"]=[round(float((out==base+4+k).sum())*vox/1000,1) for k in range(3)]
    report[side]=rep; print(side,rep,flush=True)
# ---- registration by continuity of the inter-femur distance across the junction
N=24
def centroids_legs(k):
    row={}
    for side in ("right","left"):
        m=ndi.binary_fill_holes(femur_mask[side][:,:,k]); ij=np.argwhere(m)
        r=nib.affines.apply_affine(A,np.c_[ij,np.full(len(ij),k)]); row[side]=(r[:,0].mean(),r[:,1].mean(),len(ij))
    return row
imT=nib.load(a.torso_seg); segT=np.asarray(imT.dataobj); AT=imT.affine
def centroids_torso(k):
    row={}
    for side,fid in (("right",FEMUR_R),("left",FEMUR_L)):
        ij=np.argwhere(segT[:,:,k]==fid); r=nib.affines.apply_affine(AT,np.c_[ij,np.full(len(ij),k)]); row[side]=(r[:,0].mean(),r[:,1].mean(),len(ij))
    return row
zt=np.array([AT[2,3]+k*AT[2,2] for k in range(N)]); ct_=[centroids_torso(k) for k in range(N)]
K0=sh[2]-4; zl=np.array([A[2,3]+k*A[2,2] for k in range(K0,K0-N,-1)]); cl_=[centroids_legs(k) for k in range(K0,K0-N,-1)]
Dt=np.array([c["right"][0]-c["left"][0] for c in ct_]); Dl=np.array([c["right"][0]-c["left"][0] for c in cl_])
res=[]
for t in np.arange(-960,-925,0.25):
    z=np.r_[zt,zl+t]; q=np.r_[Dt,Dl]; zz=z-z.mean(); X=np.c_[np.ones_like(zz),zz,zz**2]
    coef=np.linalg.lstsq(X,q,rcond=None)[0]; res.append((float(np.sqrt(((X@coef-q)**2).mean())),float(t)))
res.sort(); tz_D=res[0][1]
tz=a.z_prior if abs(tz_D-a.z_prior)<=4 else tz_D
zj=zt[0]-0.5; sh_xy={}
for side in ("right","left"):
    for j,ax in ((0,"x"),(1,"y")):
        qt=np.array([c[side][j] for c in ct_]); ql=np.array([c[side][j] for c in cl_])
        sh_xy[ax+"_"+side]=float(np.polyval(np.polyfit(zt,qt,1),zj)-np.polyval(np.polyfit(zl+tz,ql,1),zj))
tx=float(np.mean([sh_xy["x_right"],sh_xy["x_left"]])); ty=float(np.mean([sh_xy["y_right"],sh_xy["y_left"]]))
reg={"shift_ras_legs_to_torso":[round(tx,2),round(ty,2),tz],"z_from_inter_femur_distance":tz_D,"z_rms_mm":round(res[0][0],2),"z_prior_from_first_run":a.z_prior,"z_uncertainty_mm":4,"xy_by_side":{k:round(v,2) for k,v in sh_xy.items()},
     "method":"block continuity across the torso/legs junction (see script docstring); no femoral head in the legs block"}
print("registration",reg,flush=True)
# ---- whole femur: legs-block femur (mid-thigh to condyles) + torso-block TotalSegmentator femur (head to mid-thigh),
# on the legs grid extended upward by EXT slices; the ~3-slice junction gap is closed along z.
EXT=200; out_ext=np.zeros((sh[0],sh[1],sh[2]+EXT),np.uint8); out_ext[:,:,:sh[2]]=out; del out
for side,lab in (("right",13),("left",14)):
    if side in femur_mask: out_ext[:,:,:sh[2]][femur_mask[side]]=lab
Ainv=np.linalg.inv(AT); ii,jj=np.meshgrid(np.arange(sh[0]),np.arange(sh[1]),indexing="ij")
for k in range(sh[2]-40,sh[2]+EXT):   # from 40 slices below the legs top: the overlap band lets the two labels meet
    ras=nib.affines.apply_affine(A,np.c_[ii.ravel(),jj.ravel(),np.full(ii.size,k)])+[tx,ty,tz]
    vt=np.rint(nib.affines.apply_affine(Ainv,ras)).astype(int)
    ok=(vt[:,0]>=0)&(vt[:,0]<segT.shape[0])&(vt[:,1]>=0)&(vt[:,1]<segT.shape[1])&(vt[:,2]>=0)&(vt[:,2]<segT.shape[2])
    lab=np.zeros(ii.size,np.uint8); st=segT[vt[ok,0],vt[ok,1],vt[ok,2]]; lab[ok]=np.where(st==FEMUR_R,13,np.where(st==FEMUR_L,14,0))
    sl=out_ext[:,:,k]; lab=lab.reshape(sh[0],sh[1]); sl[(sl==0)&(lab>0)]=lab[(sl==0)&(lab>0)]
for lab in (13,14):
    m=out_ext==lab; mc=ndi.binary_closing(m,structure=np.ones((1,1,9)))&~(out_ext>0); out_ext[mc]=lab
    v=np.argwhere(m); print("femur",lab,"cm3",round(m.sum()*vox/1000,1),"z range (legs frame)",round(A[2,3]+v[:,2].min()*A[2,2]),round(A[2,3]+v[:,2].max()*A[2,2]),flush=True)
out=out_ext
A2=A.copy(); A2[:3,3]+=[tx,ty,tz]
outp=Path(a.out); outp.parent.mkdir(parents=True,exist_ok=True)
nib.save(nib.Nifti1Image(out,A2),str(outp))
json.dump({"_README":["Volumes/extents of the Visible Human female lower-limb bone labels (scripts/vhf_lower_limb_bones.py) and the legs->torso block registration. Derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female, IDC series af18f5e4 (femur-to-toes CT) and b9cf8e7a (torso CT, TotalSegmentator v2.18.0 femur labels for the registration).","registration":reg,"bones":report,"femur_cm3":{lab:round(float((out==l).sum())*vox/1000,1) for lab,l in (("right",13),("left",14))}},open(str(outp).replace(".nii.gz","_report.json"),"w"),indent=1)
print("saved",outp,flush=True)
