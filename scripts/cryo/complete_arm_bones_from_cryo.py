"""Arm bones through the photographs, v2.
1. Local registration per arm and slice: shift between the CT bone labels (frame coords) and the
   photograph's bone-coloured ring inside a window around them, by masked cross-correlation; smoothed
   along z, extrapolated beyond the CT labels. The photograph crop is then shifted into CT-aligned coords.
2. Walk: humerus distally, radius/ulna proximally, from the last solid CT slice. Next slice = largest
   bone-coloured component inside prev dilated by 2 (closing 1, fill), area within [0.5, 1.3] x prev,
   and it must not lie mostly outside the prior. The humerus stops when its area falls under 40 % of
   its running maximum (the trochlea has ended). Radius/ulna stop where they touch the humerus label.
Output: arm_bones_completed_frame.npy (CT-aligned frame coords) and renders."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from scipy.signal import fftconvolve
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r")
L=np.asarray(nib.load(S+"vhm_ts/arm_bones_labels.nii.gz").dataobj)
n,H,W=cls.shape; OFF=110
lab=np.zeros((n,H,W),np.uint8)
for k in range(n): lab[k][:,OFF:OFF+480]=ndi.zoom(L[:,:,k],480/512,order=0).T
LAB={"humerus_right":1,"radius_right":2,"ulna_right":3,"hand_right":4,"humerus_left":5,"radius_left":6,"ulna_left":7,"hand_left":8}
SIDES={"right":(slice(0,300),(1,2,3,4)),"left":(slice(400,700),(5,6,7,8))}
bonecol=lambda k: np.isin(np.asarray(cls[k]),[2,4,5])
def local_shift(k,cols,ids):
    m=np.isin(lab[k][:,cols],ids)
    if m.sum()<40: return None
    b=bonecol(k)[:,cols]&ndi.binary_dilation(m,iterations=25)
    a=m.astype(np.float32)-m.mean(); bb=b.astype(np.float32)-b.mean()
    cc=fftconvolve(bb,a[::-1,::-1],mode="same"); iy,ix=np.unravel_index(np.argmax(cc),cc.shape)
    return (iy-a.shape[0]//2, ix-a.shape[1]//2)   # shift to apply to CT labels to land on the photo bone
report={}; out=np.zeros_like(lab)
for side,(cols,ids) in SIDES.items():
    sh=np.full((n,2),np.nan)
    for k in range(n):
        s=local_shift(k,cols,ids)
        if s is not None and abs(s[0])<30 and abs(s[1])<30: sh[k]=s
    ok=~np.isnan(sh[:,0]); ks=np.where(ok)[0]
    for j in range(2): sh[:,j]=np.interp(np.arange(n),ks,ndi.median_filter(sh[ok,j],size=15))
    print(side,"local shift (rows,cols): median",np.median(sh[ok],0),"range",sh[ok].min(0),sh[ok].max(0),"slices with CT bone",len(ks),flush=True)
    # CT-aligned photo bone mask per slice: shift the photo crop by -sh
    def photo_bone(k):
        b=bonecol(k)[:,cols]; dy,dx=-int(round(sh[k,0])),-int(round(sh[k,1])); return np.roll(np.roll(b,dy,0),dx,1)
    np.save(S+f'vh_cryo/arm_shift_{side}.npy',sh)
    sub=lab[:,:,cols].copy()
    from skimage.segmentation import watershed
    own={}
    def walk(lid,direction,stop_ids,kcap):
        M=np.zeros(sub.shape,bool); own[lid]=M
        kk=np.where((sub==lid).any(axis=(1,2)))[0]; areas={int(k):int((sub[k]==lid).sum()) for k in kk}; med=np.median(list(areas.values()))
        order=sorted(kk) if direction<0 else sorted(kk,reverse=True)
        k=next(int(q) for q in order if areas[int(q)]>=0.6*med); prev=sub[k]==lid; amax=prev.sum(); steps=0
        while True:
            k+=direction
            if k<0 or k>=n or (direction<0 and k<kcap) or (direction>0 and k>kcap): break
            sub[k][sub[k]==lid]=0
            prior=ndi.binary_dilation(prev,iterations=2); cand=photo_bone(k)&prior
            cl,m=ndi.label(cand)
            if m==0: break
            sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1))
            ring=cl==(np.argmax(sizes)+1)
            new=ndi.binary_fill_holes(ndi.binary_closing(ring,iterations=1))&prior; a=new.sum()
            if lid in (2,6) and steps<3: print(f'   radius step k={k} prev={prev.sum()} cand={int(cand.sum())} comps={m} ring={int(ring.sum())} new={int(a)}',flush=True)
            hi=1.3*max(prev.sum(),med) if steps<10 else 1.3*prev.sum()
            if a<25 or a>hi or a<0.5*prev.sum(): break
            amax=max(amax,a)
            if lid in (1,5) and a<0.4*amax: break
            M[k]|=new; prev=new; steps+=1
        return steps
    r={}
    ktop=int(np.where((sub==ids[0]).any(axis=(1,2)))[0].max()); elbow=ktop-340
    print(side,"humeral head top k",ktop,"-> elbow estimate k",elbow,flush=True)
    r["radius"]=walk(ids[1],+1,(ids[0],ids[2],ids[3]),elbow+12)
    r["ulna"]=walk(ids[2],+1,(ids[0],ids[1],ids[3]),elbow+25)
    r["humerus"]=walk(ids[0],-1,(ids[1],ids[2],ids[3]),elbow-12)
    # resolve where two walks claimed the same voxels (the joints): watershed on the photograph luminance,
    # markers = each bone's CT part + its uncontested walked part; the joint line is darker than bone
    ids3=(ids[0],ids[1],ids[2]); claims=np.zeros(sub.shape,np.uint8)
    for lid in ids3: claims+=own[lid]
    union=(claims>0)|np.isin(sub,ids3); mk=np.zeros(sub.shape,np.int32)
    for lid in ids3: mk[(sub==lid)|(own[lid]&(claims==1))]=lid
    ov=claims>1; print(side,"contested voxels",int(ov.sum()),flush=True)
    if ov.any():
        ks=np.where(ov.any(axis=(1,2)))[0]; k0,k1=max(0,ks.min()-5),min(n,ks.max()+6)
        lum=np.zeros((k1-k0,)+sub.shape[1:],np.float32)
        for k in range(k0,k1):
            im=np.asarray(rgb[k])[:,cols]; im=np.roll(np.roll(im,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1); lum[k-k0]=ndi.gaussian_filter(im.astype(np.float32).mean(-1),1.0)
        ws=watershed(-lum,mk[k0:k1],mask=union[k0:k1]); sub[k0:k1][union[k0:k1]]=ws[union[k0:k1]].astype(np.uint8)
    for lid in ids3: sub[(mk==lid)&~ov]=lid
    # anatomy cut: the humerus ends at the elbow joint line (estimated from the humeral head, +-10 mm);
    # anything the walk labelled humerus below that line belongs to the ulna if it touches it, else is dropped
    below=np.zeros(sub.shape,bool); below[:elbow]=True; hb=(sub==ids[0])&below
    if hb.any():
        sub[hb]=ids[2]; r["humerus_cut_voxels"]=int(hb.sum()); r["to_ulna"]=int(hb.sum())   # below the joint line only forearm bone remains; the radius has already claimed its head
    report[side]=r; print(side,r,flush=True)
    out[:,:,cols]=sub
np.save(S+"vh_cryo/arm_bones_completed_frame.npy",out)
# NIfTI in the CT torso frame: voxel (col,row,k) -> RAS (350-col, 240-row, -863+k)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float)
nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/arm_bones_cryo_completed.nii.gz"); json.dump(report,open(S+"vh_cryo/arm_completion_report.json","w"),indent=1)
lut=np.array([[0,0,0],[220,220,220],[255,60,60],[60,140,255],[255,220,60],[220,220,220],[255,120,200],[90,230,120],[240,160,60]],np.uint8)
p=out.max(axis=1); lum=np.array([np.asarray(rgb[k]).max(-1).max(axis=0) for k in range(n)])
img=np.where(p[...,None]>0,lut[p],np.repeat((lum//2)[...,None],3,2)).astype(np.uint8); Image.fromarray(img[::-1]).save(S+"vh_cryo/arm_completed_cor.png")
def tile(k,side):
    cols=SIDES[side][0]; shv=np.load(S+f'vh_cryo/arm_shift_{side}.npy'); im=np.asarray(rgb[k])[:,cols].copy(); im=np.roll(np.roll(im,-int(round(shv[k,0])),0),-int(round(shv[k,1])),1); l=out[k][:,cols]; ys,xs=np.where(l>0)
    if len(ys)==0: return None
    r0,r1,c0,c1=max(ys.min()-30,0),min(ys.max()+30,H),max(xs.min()-30,0),min(xs.max()+30,l.shape[1]); im=im[r0:r1,c0:c1]; l=l[r0:r1,c0:c1]
    for v in np.unique(l[l>0]): im[(l==v)&~ndi.binary_erosion(l==v)]=lut[v]
    return im
for side,ks in (("right",(250,230,220,210,200,190)),("left",(260,240,225,210,195,180))):
    ts=[t for t in (tile(k,side) for k in ks) if t is not None]; h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).resize((w*len(ts)*2,h*2)).save(S+f"vh_cryo/elbow_{side}.png")
print("done")
