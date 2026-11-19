"""Register the Visible Human FEMALE 1 mm cryosection volume (scratchpad vh_cryo_f, from stream_cryosections.py)
to her CT: whole-body body-surface volume on the torso grid extended over both CT blocks
(vhf_ts/skin_ct.nii.gz, 0.9375 mm, from vhf_whole_body_skin.py) -> 480 x 480 silhouettes at 1 mm, one anchor
every 40 slices; for each anchor the cryo index is searched +-110 around the guess under four flips, aligning by
phase correlation of the silhouettes (IoU), then refined by the normalised cross-correlation of the CT muscle
pattern (HU 20-150) with the photograph's muscle class over +-25 slices. Output vh_cryo_f/anchors.json.
The female's CT is a FRESH scan and the photographs are of the frozen block: the pose may differ, which the
per-anchor shifts and the IoU will show (the male, scanned frozen, gave IoU 0.84-0.95 and one rigid mapping)."""
import numpy as np, json, nibabel as nib
from skimage.registration import phase_cross_correlation
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
cls=np.load(D+"cryo_1mm_classes.npy",mmap_mode="r"); Z=cls.shape[0]; idx=json.load(open(D+"cryo_index.json"))
skin=nib.load(S+"vhf_ts/skin_ct.nii.gz"); sk=skin.dataobj; z0=float(skin.affine[2,3]); nz=skin.shape[2]
ctT=nib.load(S+"vh_idc/nii/vhf_torso_0937.nii.gz"); zT0=float(ctT.affine[2,3]); ctL=nib.load(S+"vh_idc/nii/vhf_legs_0723.nii.gz")
reg=json.load(open("/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhf_lower_limb_bones_report.json"))["registration"]["shift_ras_legs_to_torso"]
FLIPS={"id":lambda a:a,"fy":lambda a:a[::-1,:],"fx":lambda a:a[:,::-1],"fxy":lambda a:a[::-1,::-1]}
def pad(a,shape=(480,700)):
    out=np.zeros(shape,bool); h=min(a.shape[0],shape[0]); w=min(a.shape[1],shape[1]); out[:h,:w]=a[:h,:w]; return out
def cryo_mask(z): m=np.asarray(cls[z])>0; return ndi.binary_fill_holes(ndi.binary_opening(m,iterations=2))
def ct_body(k): return ndi.zoom(np.asarray(sk[:,:,k]).astype(np.float32),480/512,order=1).T>0.5
def ct_muscle(zr):   # HU 20-150 pattern at RAS z, from whichever block holds it (torso first)
    kT=int(round(zr-zT0))
    if 0<=kT<ctT.shape[2]: s=np.asarray(ctT.dataobj[:,:,kT]).astype(np.float32); return ((ndi.zoom(s,480/512,order=1).T>20)&(ndi.zoom(s,480/512,order=1).T<150)).astype(np.float32)
    kL=int(round(zr-reg[2]-float(ctL.affine[2,3])))
    if 0<=kL<ctL.shape[2]:
        s=np.asarray(ctL.dataobj[:,:,kL]).astype(np.float32); b=ndi.zoom(s,480/ctL.shape[0],order=1).T
        b=ndi.shift(b,(-reg[1],-reg[0]),order=1,cval=-1024)   # legs block into torso RAS (row=y, col=x; both axes reversed in this grid)
        return ((b>20)&(b<150)).astype(np.float32)
    return None
def cryo_muscle(z,flip,sh):
    m=FLIPS[flip](np.asarray(cls[z])==3); P=pad(m); m=np.roll(np.roll(P,int(sh[0]),0),int(sh[1]),1); return m[:480,:480].astype(np.float32)
def ncc(a,b): a=a-a.mean(); b=b-b.mean(); return float((a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum()+1e-6))
def score(a,b):
    a=pad(a); b=pad(b); sh,_,_=phase_cross_correlation(a.astype(np.float32),b.astype(np.float32),upsample_factor=1)
    bs=np.roll(np.roll(b,int(sh[0]),0),int(sh[1]),1); return (a&bs).sum()/((a|bs).sum()+1), sh
res=[]
for k in range(20,nz-20,40):
    zr=z0+k; a=ct_body(k)
    if a.sum()<3000: continue
    guess=int(round(-30-zr)); best=None
    for cz in range(max(0,guess-110),min(Z,guess+111),2):
        b=cryo_mask(cz)
        for fn,f in FLIPS.items():
            s,sh=score(a,f(b))
            if best is None or s>best[0]: best=(s,cz,fn,sh)
    r=dict(ct_k=k,ct_z=zr,cryo_z=int(best[1]),flip=best[2],shift=[float(v) for v in best[3]],iou=float(best[0]))
    A=ct_muscle(zr)
    if A is not None:
        bz=None
        for z in range(max(0,r["cryo_z"]-25),min(Z,r["cryo_z"]+26)):
            s=ncc(A,cryo_muscle(z,r["flip"],r["shift"]))
            if bz is None or s>bz[0]: bz=(s,z)
        r["cryo_z_refined"]=bz[1]; r["ncc"]=round(bz[0],3)
    res.append(r); print(r,flush=True); json.dump(res,open(D+"anchors.json","w"),indent=1)
print("REG_DONE",flush=True)
