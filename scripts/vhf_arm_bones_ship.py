"""Package the female RIGHT forearm and hand from scripts/vhf_arm_bones_ct.py (her torso CT, marker watershed):
radius and ulna as they come (clipped by the field of view: the ulna's proximal part is outside it), the hand mass
grouped by planes along its long axis from the wrist -- carpals < 45 mm, metacarpals 45-115 mm, phalanges beyond
(the male's hand rule). The humerus is not repackaged (ct_vhf ships the TotalSegmentator one); the left arm lies
outside the CT field of view. Output data/ct_sources/task_outputs/vhf_arm_bones_ct.nii.gz + report."""
import numpy as np, nibabel as nib, json
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; R="/home/user/NMSK_Atlas/"
im=nib.load(S+"vhf_ts/arm_bones_ct.nii.gz"); v=np.asarray(im.dataobj); A=im.affine; vox=float(np.prod(im.header.get_zooms()))
out=np.zeros(v.shape,np.uint8); out[v==2]=1; out[v==3]=2
hand=np.argwhere(v==4); ras=nib.affines.apply_affine(A,hand); rep={}
if len(hand)>2000:
    # hand axis: from the wrist (the end nearest the radius' distal end) towards the fingertips
    rd=nib.affines.apply_affine(A,np.argwhere(v==2)); wrist=rd[np.argmin(np.linalg.norm(rd-ras.mean(0),axis=1))]
    mu=ras.mean(0); u=np.linalg.svd(ras-mu,full_matrices=False)[2][0]
    if np.dot(mu-wrist,u)<0: u=-u
    t=(ras-mu)@u; t-=np.percentile(t,0.5); g=np.where(t<45,0,np.where(t<115,1,2)); out[tuple(hand.T)]=3+g
    rep["hand_len_mm"]=round(float(t.max()))
for name,l in (("radius_right",1),("ulna_right",2),("carpals_right",3),("metacarpals_right",4),("phalanges_right",5)):
    idx=np.argwhere(out==l); r=nib.affines.apply_affine(A,idx) if len(idx) else np.zeros((0,3))
    rep[name]={"cm3":round(float(len(idx))*vox/1000,1),"z_range":[float(r[:,2].min()),float(r[:,2].max())] if len(idx) else None}
print(rep,flush=True)
nib.save(nib.Nifti1Image(out,A),R+"data/ct_sources/task_outputs/vhf_arm_bones_ct.nii.gz")
json.dump({"_README":["Female right forearm and hand bones from her torso CT (scripts/vhf_arm_bones_ct.py + vhf_arm_bones_ship.py); clipped by the field of view; hand grouped by planes. Derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female 'Normal' CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 humerus label as the watershed marker.","volumes":rep,"left_arm":"outside the CT field of view (not segmented)"},open(R+"data/ct_sources/task_outputs/vhf_arm_bones_ct_report.json","w"),indent=1); print("SHIP_DONE")
