"""Foot bones from the VH male frozen CT feet block. Registration feet->legs by the shared slice:
legs (i,j,k=0) = feet (i+7, j+39, k=221); in RAS (both LAS grids, same in-plane affine): x_legs = x_feet + 6.56,
y_legs = y_feet - 36.56, z_legs = z_feet - 407. Distal tibia/fibula removed within 4 mm of the DU meshes
(atlas frame -> legs RAS via the legs origin). Groups by planes along each foot's PCA axis from the heel."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
Fz=nib.load(S+"vh_idc/nii/vhm_94755b62_2.nii.gz"); feet=np.asarray(Fz.dataobj); A=Fz.affine.copy()
# affine expressed in the LEGS frame
A[0,3]+=6.56; A[1,3]-=36.56; A[2,3]-=407.0
bone=feet>=200; bone[:8]=False; bone[-8:]=False
colcount=bone.sum(axis=2); streak=colcount>150; bone[streak]=False; print('streak columns removed',int(streak.sum()),flush=True)   # the block-edge/table line is present in every slice at the same (i,j)
# DU tibia/fibula in legs RAS: atlas (x,y=S,z=A) + legs origin o -> RAS (x+ox, z+oz, y+oy)
R="/home/user/NMSK_Atlas/build/vh/vhm_both/"; m=json.load(open(R+"manifest.json")); V=np.fromfile(R+"vertices.f32",np.float32).reshape(-1,3); st={s["atlas_id"]:s for s in m["structures"]}
o=np.array([-8.754,-202.476,5.678]); pts=[]
for aid in ("tibia_r","tibia_l","fibula_r","fibula_l"):
    s=st[aid]; a=s.get("vertex_offset",s.get("vertex_start")); p=V[a:a+s["vertex_count"]]; pts.append(np.stack([p[:,0]+o[0],p[:,2]+o[2],p[:,1]+o[1]],axis=1))
pts=np.concatenate(pts); tree=cKDTree(pts)
idx=np.argwhere(bone); ras=nib.affines.apply_affine(A,idx); d,_=tree.query(ras,distance_upper_bound=4.0); keep=~np.isfinite(d)
print("bone voxels",len(idx),"removed as tibia/fibula",int((~keep).sum()),flush=True)
mask=np.zeros(bone.shape,bool); mask[tuple(idx[keep].T)]=True
mask=ndi.binary_opening(mask,iterations=1)
cl,n=ndi.label(mask,structure=np.ones((3,3,3))); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,n+1))
out=np.zeros(bone.shape,np.uint8); rep={}
for side,sgn,base in (("right",1,1),("left",-1,4)):
    comps=[]
    for i in range(n):
        if sizes[i]<200: continue
        v=np.argwhere(cl==i+1); zext=(v[:,2].max()-v[:,2].min())
        if sgn*nib.affines.apply_affine(A,v.mean(0)[None])[0,0]>0: comps.append(i+1)
    fm=np.isin(cl,comps); fi=np.argwhere(fm).astype(float); fr=nib.affines.apply_affine(A,fi); mu=fr.mean(0)
    u=np.linalg.svd(fr-mu,full_matrices=False)[2][0]
    if u[1]<0: u=-u                      # foot axis points anteriorly (toes are anterior, RAS +y)
    t=(fr-mu)@u; t-=np.percentile(t,0.5)  # heel = 0
    g=np.where(t<115,0,np.where(t<190,1,2)).astype(np.uint8); out[tuple(fi.astype(int).T)]=base+g
    print(side,"foot length mm",round(float(t.max())),"components",len(comps),flush=True)
    for gi,name in enumerate(("tarsals","metatarsals","phalanges")): rep[f"{name}_{side}"]=round(float((out==base+gi).sum())*0.879/1000,1)
print("volumes cm3",rep)
nib.save(nib.Nifti1Image(out,A),S+"vhm_ts/foot_bones.nii.gz"); json.dump(rep,open(S+"vhm_ts/foot_report.json","w"))
lut=np.zeros((7,3),np.uint8); lut[1]=lut[4]=(255,220,60); lut[2]=lut[5]=(255,140,0); lut[3]=lut[6]=(120,255,120)
p=out.max(axis=1).T[::-1]; Image.fromarray(lut[p]).save(S+"vh_cryo/feet_cor.png"); p2=out.max(axis=0).T[::-1]; Image.fromarray(lut[p2]).save(S+"vh_cryo/feet_sag.png"); print("done")
