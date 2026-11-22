"""Female RIGHT forearm compartments by the male's rule (arm_compartments_from_cryo.py, forearm branch) on her
registered cryosections with her CT radius and ulna (ct_vhf_armb, shifted onto the photographs by the right arm's
constant: rows 0, cols +11): within the forearm's OWN cross-section (the tissue silhouette eroded 8 px until the forearm separates from the
trunk and thigh it rests on, the piece holding the bones grown back), every muscle piece (female colour classes)
within 45 mm of a bone, not bone, is split by the line through
the radius and ulna centroids: the side away from the ulna's subcutaneous border -> flexor-pronator group, the side of that border (dorsal)
-> extensor group (the forearm is pronated with the hand on the thigh). Segment: from 10 mm below her humerus label's lower end to the radius' distal end. The left forearm has no
bones in the CT and is not attempted. Rule-based: badge; record volumes. Output vhf_ts/forearm_compartments_cryo.nii.gz."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"; R="/home/user/NMSK_Atlas/"; T=R+"data/ct_sources/task_outputs/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); rgb=np.load(D+"cryo_frame_rgb.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
def load(name): im=nib.load(T+name); return np.asarray(im.dataobj),float(im.affine[2,3])
arm,zA0=load("vhf_arm_bones_ct.nii.gz"); tot,zT0=load("vhf_total.nii.gz")
labs={v:int(k) for k,v in json.load(open(R+"mappings/totalsegmentator_labels.json"))["labels"].items()}
dy,dx=0,11; cols=slice(0,300)
def frame_ct(arr,zoff,k):
    kk=int(round(z0+k-zoff)); f=np.zeros((H,W),np.int32)
    if 0<=kk<arr.shape[2]: f[:,OFF:OFF+480]=ndi.zoom(arr[:,:,kk],480/512,order=0).T
    return np.roll(np.roll(f,dy,0),dx,1)
kh=np.where((tot==labs["humerus_right"]).any(axis=(0,1)))[0]; k_elbow=int(round(zT0+kh.min()-z0))-10
kr=np.where((arm==1).any(axis=(0,1)))[0]; k_wrist=int(round(zA0+kr.min()-z0))
print("segment frame k",k_wrist,"..",k_elbow,"z",z0+k_wrist,z0+k_elbow,flush=True)
out=np.zeros((n,H,W),np.uint8)
for k in range(k_wrist,k_elbow+1):
    a=frame_ct(arm,zA0,k)[:,cols]; r=a==1; u=a==2; bone=r|u
    if bone.sum()<20: continue
    c=np.asarray(cls[k])[:,cols]; tissue=ndi.binary_fill_holes(ndi.binary_closing(c>0,iterations=3)); tl,tn=ndi.label(tissue)
    ys,xs=np.where(bone); cy,cx=ys.mean(),xs.mean(); yy,xx=np.mgrid[0:H,0:cols.stop-cols.start]
    # the forearm's OWN cross-section: her forearm rests on the trunk and thigh, so the tissue silhouette is eroded 8 px until
    # the forearm separates, the piece holding the bones is taken and grown back 8 px inside the tissue
    er=ndi.binary_erosion(tissue,iterations=8); el0,_=ndi.label(er); ids=np.unique(el0[bone]); ids=ids[ids>0]
    if len(ids)==0: continue
    comp=ndi.binary_dilation(np.isin(el0,ids),iterations=8)&tissue; comp&=((yy-cy)**2+(xx-cx)**2)<70**2
    mall=comp&(c==3)&~bone; op=ndi.binary_opening(mall,iterations=1); el,en=ndi.label(op)
    if en==0: continue
    db=ndi.distance_transform_edt(~bone); mind=np.asarray(ndi.minimum(db,el,np.arange(1,en+1)))
    cms=np.array(ndi.center_of_mass(op,el,np.arange(1,en+1))); dcm=np.hypot(cms[:,0]-cy,cms[:,1]-cx)
    keep=np.arange(1,en+1)[(mind<=45)&(dcm<=45)]
    if len(keep)==0: continue
    musc=ndi.binary_dilation(np.isin(el,keep),iterations=1)&mall
    if r.sum()>=20 and u.sum()>=20:
        ry,rx=np.where(r); uy,ux=np.where(u); p=np.array([ry.mean(),rx.mean()]); q=np.array([uy.mean(),ux.mean()]); d=q-p; nrm=np.array([-d[1],d[0]])
        # dorsal = the side of the ulna's subcutaneous border: the skin point nearest the ulna; the forearm is pronated with the
        # hand on the thigh, so a fixed anterior direction would split it wrongly
        dsk=ndi.distance_transform_edt(tissue); sk=np.argwhere(~tissue&ndi.binary_dilation(tissue,iterations=1))
        near=sk[np.argmin(np.hypot(sk[:,0]-q[0],sk[:,1]-q[1]))]; mid=(p+q)/2; dors=np.array([near[0]-mid[0],near[1]-mid[1]])
        if np.dot(nrm,dors)>0: nrm=-nrm   # nrm now points away from the dorsal side = towards the flexor side
        ant=((yy-p[0])*nrm[0]+(xx-p[1])*nrm[1])>0
    else: ant=yy<cy
    o=out[k][:,cols]; o[musc&ant]=1; o[musc&~ant]=2
rep={"flexor_pronator_right_cm3":round(float((out==1).sum())/1000,1),"extensor_right_cm3":round(float((out==2).sum())/1000,1)}; print("volumes",rep,flush=True)
nz=np.where(out.any(axis=(1,2)))[0]; ka,kb=nz.min(),nz.max()+1
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+ka],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out[ka:kb].transpose(2,1,0)),aff),S+"vhf_ts/forearm_compartments_cryo.nii.gz")
json.dump({"_README":["Female right forearm compartments by the male's radius-ulna line rule on her registered cryosections (scripts/cryo/vhf_forearm_compartments.py). Rule-based, derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections and CT via the NCI Imaging Data Commons.","volumes_cm3":rep},open(D+"forearm_comp_report.json","w"),indent=1)
lut=np.array([[0,0,0],[255,200,90],[120,255,140]],np.uint8); ts=[]
ks=np.where((out>0).any(axis=(1,2)))[0]
for k in np.linspace(ks.min()+3,ks.max()-3,6).astype(int):
    im=np.asarray(rgb[k])[:,cols].copy(); m=out[k][:,cols]; ys,xs=np.where(m>0)
    if len(ys)==0: continue
    r0,r1,c0,c1=max(ys.min()-15,0),min(ys.max()+15,H),max(xs.min()-15,0),min(xs.max()+15,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
    im[mm>0]=(0.5*im[mm>0]+0.5*lut[mm[mm>0]]).astype(np.uint8); ts.append(im)
h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(D+"forearm_comp_right.png"); print("FORE_DONE")
