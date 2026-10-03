"""Female cryosections, second pass: FULL-RESOLUTION (0.33 mm) crops of both forearms and hands, elbow to fingertips
(RAS z -500 .. -990), from the slices kept by stream_cryosections.py (1 mm apart). The crop window per side is a
fixed box in the registered frame (rows 110-370, frame cols 0-275 right / 425-700 left; vhf_resample_cryo.py's
piecewise mapping turns it into photograph pixels, x3 for full resolution). Output in scratchpad/vh_cryo_f/:
arm_full_<side>.npy memmap (Z, h, w, 3) uint8 and arm_full_bbox.json (per-slice window in full-res px, the frame
z of each slice, and the mapping used)."""
import numpy as np, json, urllib.request, io, pydicom, os, concurrent.futures as cf, time
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
fr=json.load(open(D+"frame.json")); idx=json.load(open(D+"cryo_index.json")); a0,b=fr["z_offset_line"]
A=json.load(open(D+"anchors.json")); A=[a for a in A if a["flip"]=="fy" and a["iou"]>=0.7]
zs_a=np.array([a["ct_z"] for a in A]); rs=ndi.median_filter(np.array([a["shift"][0] for a in A],float),size=5,mode="nearest"); cs=ndi.median_filter(np.array([a["shift"][1] for a in A],float),size=5,mode="nearest")
o=np.argsort(zs_a); zs_a,rs,cs=zs_a[o],rs[o],cs[o]
H=405; sc=0.99; ZT,ZB=-500,-990
BOX={"right":(110,370,0,275),"left":(110,370,425,700)}   # frame rows r0,r1, cols c0,c1
win={}; zlist=[]
for z in range(ZT,ZB-1,-1):
    zi=int(round(-(a0+b*z)-z))
    if zi<0 or zi>=len(idx): continue
    RS=float(np.interp(z,zs_a,rs)); CS=float(np.interp(z,zs_a,cs)); w={}
    for side,(r0,r1,c0,c1) in BOX.items():
        src_r=[(H-1)-(r-RS)/sc for r in (r0,r1)]; src_c=[(c-110-CS)/sc for c in (c0,c1)]
        rr0,rr1=int(max(0,min(src_r)))*3,int(min(H,max(src_r)))*3; cc0,cc1=int(max(0,min(src_c)))*3,int(min(682,max(src_c)))*3
        w[side]=[rr0,rr1,cc0,cc1]
    win[zi]=w; zlist.append((z,zi))
zis=[zi for _,zi in zlist]; print("slices",len(zis),"cryo idx",zis[0],zis[-1],flush=True)
hmax=max(max(v[s][1]-v[s][0] for s in v) for v in win.values()); wmax=max(max(v[s][3]-v[s][2] for s in v) for v in win.values()); print("crop max h,w",hmax,wmax,flush=True)
mm={s:np.lib.format.open_memmap(D+f"arm_full_{s}.npy",mode="w+",dtype=np.uint8,shape=(len(zis),hmax,wmax,3)) for s in BOX}
def fetch(j):
    n_=idx[zis[j]][0]
    for _ in range(4):
        try: d=urllib.request.urlopen(f"https://storage.googleapis.com/idc-open-data/{n_}").read(); return j,pydicom.dcmread(io.BytesIO(d)).pixel_array
        except Exception as e: err=e; time.sleep(2)
    raise err
t0=time.time()
with cf.ThreadPoolExecutor(6) as ex:
    for j,px in ex.map(fetch,range(len(zis))):
        for side,w in win[zis[j]].items():
            crop=px[w[0]:w[1],w[2]:w[3]]; mm[side][j,:crop.shape[0],:crop.shape[1]]=crop
        if j%100==0: print(j,f"{time.time()-t0:.0f}s",flush=True)
for s in mm: mm[s].flush()
json.dump({"z_ras":[z for z,_ in zlist],"cryo_idx":zis,"windows":{str(k):v for k,v in win.items()},"box_frame":BOX,"note":"full-res px = 3 x (1 mm cryo px); frame mapping as vhf_resample_cryo.py"},open(D+"arm_full_bbox.json","w")); print("ARMS_FULL_DONE",flush=True)
