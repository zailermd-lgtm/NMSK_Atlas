"""Resample the 1 mm cryo RGB + class volumes into the CT torso-frame grid (480 x 480 x 843, 1 mm,
rows = P->A voxel order like the CT silhouettes, i.e. row j = RAS y 240-j, col i = RAS x 240-i).
Mapping (from silhouette + mutual-information registration): cryo_idx = -16 - z_ras, flip rows,
in-plane shift (rows, cols) = (0, -98) torso block, (4, -96) legs block, scale 0.99."""
import numpy as np, sys
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo/"
vol=np.load(S+"cryo_1mm.npy",mmap_mode="r"); cls=np.load(S+"cryo_1mm_classes.npy",mmap_mode="r")
block=sys.argv[1] if len(sys.argv)>1 else "torso"
if block=="torso": z0,n,sh=-863.0,844,(0,-98)
else: z0,n,sh=-1671.0,809,(4,-96)
rgb=np.lib.format.open_memmap(S+f"cryo_{block}_frame_rgb.npy",mode="w+",dtype=np.uint8,shape=(n,480,480,3))
cl=np.lib.format.open_memmap(S+f"cryo_{block}_frame_cls.npy",mode="w+",dtype=np.uint8,shape=(n,480,480))
H,W=vol.shape[1],vol.shape[2]; sc=0.99
# target pixel (r,c) in padded 480x700 frame <- source (r-sh0, c-sh1)/sc after flip
rr,cc=np.mgrid[0:480,0:480]; src_r=(rr-sh[0])/sc; src_c=(cc-sh[1])/sc
src_r=(H-1)-src_r   # flip rows
for k in range(n):
    zi=int(round(-16-(z0+k)))
    if zi<0 or zi>=vol.shape[0]: continue
    s=np.asarray(vol[zi]); c=np.asarray(cls[zi])
    for ch in range(3): rgb[k,:,:,ch]=ndi.map_coordinates(s[...,ch],[src_r,src_c],order=1,mode="constant",cval=0)
    cl[k]=ndi.map_coordinates(c,[src_r,src_c],order=0,mode="constant",cval=0)
    if k%100==0: print(k,flush=True)
rgb.flush(); cl.flush(); print("RESAMPLE_DONE",block,flush=True)
