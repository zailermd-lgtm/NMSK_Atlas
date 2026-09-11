"""Achilles and quadriceps tendons from the photographs, anchored on the DU bone meshes of the same body.
Achilles: white/pale voxels inside a 16 mm-radius cylinder from the calcaneal tuberosity (posterior-superior
point of the DU calcaneus) 160 mm up along the leg axis (tibia PCA axis), posterior to the tibia.
Quadriceps tendon: white/pale voxels inside a 20 mm cylinder from the patella's superior pole 70 mm up the
thigh axis (femur PCA axis), anterior to the femur. Largest connected 3-D component each. Cryo 1 mm grid,
legs-block registration; DU meshes in the atlas frame -> RAS (torso frame) -> cryo."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
R="/home/user/NMSK_Atlas/build/vh/vhm_both/"
m=json.load(open(R+"manifest.json")); V=np.fromfile(R+"vertices.f32",np.float32).reshape(-1,3); st={s["atlas_id"]:s for s in m["structures"]}
def verts(aid): s=st[aid]; a=s.get("vertex_offset",s.get("vertex_start")); return V[a:a+s["vertex_count"]]
o=np.array([-6.035,-895.476,4.787])
def atlas_to_cryo(p):   # atlas (x,y=S,z=A) -> RAS (x, y=A, z=S) -> cryo (r,c,idx)
    x=p[:,0]+o[0]; zr=p[:,1]+o[1]; yr=p[:,2]+o[2]
    return np.stack([(yr+163.96)/0.99,(336-x)/0.99,-16-zr],axis=1)
cls=np.load(S+"vh_cryo/cryo_1mm_classes.npy",mmap_mode="r"); vol=np.load(S+"vh_cryo/cryo_1mm.npy",mmap_mode="r"); Z,H,W=cls.shape
out=np.zeros((Z,H,W),np.uint8); rep={}; LAB={"achilles_right":1,"quadriceps_right":2,"achilles_left":3,"quadriceps_left":4}
def axis(p): mu=p.mean(0); u=np.linalg.svd(p-mu,full_matrices=False)[2][0]; u=u if u[1]>0 else -u; return u   # pointing superior (atlas y)
def extract(name,p0,u,length,radius,side_cond):
    zs=np.arange(0,length); best=np.zeros((Z,H,W),bool)
    pts=p0[None,:]+zs[:,None]*u[None,:]; cr=atlas_to_cryo(pts)
    for j in range(len(zs)):
        r,c,i=cr[j]; i=int(round(i)); 
        if i<0 or i>=Z: continue
        cl=np.asarray(cls[i]); yy,xx=np.mgrid[0:H,0:W]; disk=((yy-r)**2+(xx-c)**2)<=(radius/0.99)**2
        m_=disk&np.isin(cl,[4,5])&side_cond(i,yy,xx,r,c)
        best[i]|=m_
    best=ndi.binary_closing(best,iterations=1); lab,n=ndi.label(best)
    if n==0: return best
    sizes=ndi.sum(np.ones_like(lab),lab,np.arange(1,n+1)); return lab==(np.argmax(sizes)+1)
for side,sfx in (("right","r"),("left","l")):
    tib=verts(f"tibia_{sfx}"); fem=verts(f"femur_{sfx}"); pat=verts(f"patella_{sfx}")
    if f"calcaneus_{sfx}" in st:
        cal=verts(f"calcaneus_{sfx}"); tub=cal[np.argmin(cal[:,2]+0.3*(cal[:,1]-cal[:,1].max()))]   # most posterior, high point
        tub=cal[np.argmin(cal[:,2])]; ut=axis(tib)
        ach=extract("ach",tub+np.array([0,10,0]),ut,160,16,lambda i,yy,xx,r,c:np.ones((H,W),bool))
        out[ach&(out==0)]=LAB[f"achilles_{side}"]; rep[f"achilles_{side}"]=round(float(ach.sum())/1000,1)
    top=pat[np.argmax(pat[:,1])]; uf=axis(fem)
    quad=extract("quad",top,uf,70,20,lambda i,yy,xx,r,c:np.ones((H,W),bool))
    out[quad&(out==0)]=LAB[f"quadriceps_{side}"]; rep[f"quadriceps_{side}"]=round(float(quad.sum())/1000,1)
print("volumes cm3",rep)
data=np.ascontiguousarray(out.transpose(2,1,0)); aff=np.array([[-0.99,0,0,336.0],[0,0.99,0,-163.96],[0,0,-1.0,-16.0],[0,0,0,1]])
nib.save(nib.Nifti1Image(data,aff),S+"vhm_ts/tendons_cryo.nii.gz"); json.dump(rep,open(S+"vhm_ts/tendons_report.json","w"))
ts=[]
for lid in (1,2):
    zs=np.where((out==lid).any(axis=(1,2)))[0]
    for i in np.linspace(zs.min()+5,zs.max()-5,3).astype(int) if zs.size else []:
        im=np.asarray(vol[i]).copy(); mm=out[i]==lid; ys,xs=np.where(mm)
        r0,r1,c0,c1=max(ys.min()-40,0),min(ys.max()+40,H),max(xs.min()-40,0),min(xs.max()+40,W); im=im[r0:r1,c0:c1]; e=mm[r0:r1,c0:c1]&~ndi.binary_erosion(mm[r0:r1,c0:c1]); im[e]=(0,255,0); ts.append(im)
if ts:
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts); Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).resize((w*len(ts)*2,h*2)).save(S+"vh_cryo/tendons.png")
print("done")
