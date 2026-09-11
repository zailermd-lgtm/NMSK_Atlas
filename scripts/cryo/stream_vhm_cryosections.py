"""Stream the VH male cryosection series from IDC into one 3x-downsampled RGB volume (~1 mm),
never writing the 7.5 MB DICOMs to disk. Output: cryo_1mm.u8 memmap (Z,Y,X,3) + cryo_index.json."""
import json, urllib.request, io, os, sys, numpy as np, pydicom, concurrent.futures as cf, time
S=os.path.dirname(os.path.abspath(__file__)); B='idc-open-data'
names=[n for n,_ in json.load(open(f"{S}/objects.json"))]
F=3; H,W=1216//F,2048//F   # 405 x 682
# first pass: instance numbers -> z order (from the object list we need headers; fetch header via range request of first 4 KB)
def head(n):
    for a in range(4):
        try:
            req=urllib.request.Request(f"https://storage.googleapis.com/{B}/{n}",headers={"Range":"bytes=0-8191"}); d=urllib.request.urlopen(req).read()
            ds=pydicom.dcmread(io.BytesIO(d),stop_before_pixels=True,force=True); return n,int(ds.InstanceNumber),float(ds.ImagePositionPatient[2])
        except Exception as e: err=e; time.sleep(1)
    raise err
with cf.ThreadPoolExecutor(16) as ex: idx=list(ex.map(head,names))
idx.sort(key=lambda t:-t[2])  # superior (largest z) first
json.dump(idx,open(f"{S}/cryo_index.json","w")); print("indexed",len(idx),"z",idx[0][2],idx[-1][2],flush=True)
Z=len(idx); vol=np.lib.format.open_memmap(f"{S}/cryo_1mm.npy",mode="w+",dtype=np.uint8,shape=(Z,H,W,3))
def fetch(k):
    n=idx[k][0]
    for a in range(4):
        try:
            d=urllib.request.urlopen(f"https://storage.googleapis.com/{B}/{n}").read(); ds=pydicom.dcmread(io.BytesIO(d)); px=ds.pixel_array
            small=px[:H*F,:W*F].reshape(H,F,W,F,3).mean(axis=(1,3)).astype(np.uint8); return k,small
        except Exception as e: err=e; time.sleep(2)
    raise err
done=0; t0=time.time()
with cf.ThreadPoolExecutor(6) as ex:
    for k,small in ex.map(fetch,range(Z)):
        vol[k]=small; done+=1
        if done%100==0: vol.flush(); print(f"{done}/{Z} {time.time()-t0:.0f}s",flush=True)
vol.flush(); print("CRYO_DONE",flush=True)
