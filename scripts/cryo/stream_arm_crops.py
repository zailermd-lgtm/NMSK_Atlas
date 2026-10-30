"""Second streaming pass over the cryosections: keep FULL-RESOLUTION (0.33 mm) crops of both arms and hands.
Crop windows per slice from the 1 mm arm/hand labels (torso frame -> cryo 1 mm coords -> x3), 25 mm margin.
Output: arm_full_<side>.npy memmap (Z, h, w, 3) + arm_full_<side>_bbox.json (per-slice window in full-res px)."""
import numpy as np, json, urllib.request, io, pydicom, os, concurrent.futures as cf, time
S=os.path.dirname(os.path.abspath(__file__))
lab=np.load(f"{S}/arm_bones_ext_frame.npy",mmap_mode="r"); EXT=250; n=lab.shape[0]
idx=json.load(open(f"{S}/cryo_index.json")); byz={int(-t[2]):t[0] for t in idx}
# frame (k', row, col) -> cryo 1 mm (r, c, i): z_RAS = -1113 + k' ; i = -16 - z ; row = (404 - r)*0.99 + 0 ; col = 0.99 c + 12
win={}
for side,ids in (("right",(1,2,3,9,10,11)),("left",(5,6,7,12,13,14))):
    ks=np.where(np.isin(np.asarray(lab),ids).any(axis=(1,2)))[0]
    for k in ks:
        m=np.isin(lab[k],ids); ys,xs=np.where(m); i=-16-(-1113+int(k))
        r0=int((404-(ys.max()))/0.99)-75; r1=int((404-(ys.min()))/0.99)+75; c0=int((xs.min()-12)/0.99)-75; c1=int((xs.max()-12)/0.99)+75
        win.setdefault(i,{})[side]=[max(0,r0)*3,min(405,r1)*3,max(0,c0)*3,min(682,c1)*3]
zs=sorted(win); print("slices",len(zs),zs[0],zs[-1],flush=True)
hmax=max(max(v[side][1]-v[side][0] for side in v) for v in win.values()); wmax=max(max(v[side][3]-v[side][2] for side in v) for v in win.values())
print("crop max h,w",hmax,wmax,flush=True)
mm={side:np.lib.format.open_memmap(f"{S}/arm_full_{side}.npy",mode="w+",dtype=np.uint8,shape=(len(zs),hmax,wmax,3)) for side in ("right","left")}
def fetch(j):
    i=zs[j]; n_=byz.get(1001+i)
    if n_ is None: return j,None
    for a in range(4):
        try: d=urllib.request.urlopen(f"https://storage.googleapis.com/idc-open-data/{n_}").read(); return j,pydicom.dcmread(io.BytesIO(d)).pixel_array
        except Exception as e: err=e; time.sleep(2)
    raise err
t0=time.time()
with cf.ThreadPoolExecutor(6) as ex:
    for j,px in ex.map(fetch,range(len(zs))):
        if px is None: continue
        for side,w in win[zs[j]].items():
            crop=px[w[0]:w[1],w[2]:w[3]]; mm[side][j,:crop.shape[0],:crop.shape[1]]=crop
        if j%100==0: print(j,f"{time.time()-t0:.0f}s",flush=True)
for side in mm: mm[side].flush()
json.dump({"slices":zs,"windows":{str(k):v for k,v in win.items()}},open(f"{S}/arm_full_bbox.json","w")); print("ARMS_FULL_DONE",flush=True)
