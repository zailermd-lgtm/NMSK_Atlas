"""Stream a Visible Human cryosection series from the IDC mirror into one 3x-downsampled RGB volume (~1 mm),
never writing the 7.5 MB DICOMs to disk. Generic and RESUMABLE (the male version, stream_vhm_cryosections.py,
was neither): every STEP-th slice by z order; progress in <out>/done.json so a killed run continues.

    python3 scripts/cryo/stream_cryosections.py SERIES_UUID OUT_DIR [--step 3] [--factor 3] [--workers 6]

Output: OUT_DIR/cryo_1mm.npy memmap (Z,Y,X,3) uint8, OUT_DIR/cryo_index.json [(object, instance, z_mm)] of the
slices kept (superior first), OUT_DIR/done.json. Series: male 4aaf9181 (1878 slices, 1 mm apart, step 1);
female 56f8119f (5186 slices, 0.33 mm apart, step 3 -> 1729 slices at 1 mm). Public domain (NLM VHP)."""
import json, urllib.request, io, os, sys, argparse, numpy as np, pydicom, concurrent.futures as cf, time
ap=argparse.ArgumentParser(); ap.add_argument("uuid"); ap.add_argument("out"); ap.add_argument("--step",type=int,default=3); ap.add_argument("--factor",type=int,default=3); ap.add_argument("--workers",type=int,default=6)
a=ap.parse_args(); B='idc-open-data'; O=a.out; os.makedirs(O,exist_ok=True); F=a.factor
def objects():
    names=[]; tok=None
    while True:
        q=f"https://storage.googleapis.com/storage/v1/b/{B}/o?prefix={a.uuid}/&maxResults=1000&fields=items(name),nextPageToken"+(f"&pageToken={tok}" if tok else "")
        j=json.load(urllib.request.urlopen(q)); names+=[i['name'] for i in j.get('items',[])]; tok=j.get('nextPageToken')
        if not tok: return names
def head(n):
    for _ in range(4):
        try:
            req=urllib.request.Request(f"https://storage.googleapis.com/{B}/{n}",headers={"Range":"bytes=0-8191"}); d=urllib.request.urlopen(req).read()
            ds=pydicom.dcmread(io.BytesIO(d),stop_before_pixels=True,force=True); return n,int(ds.InstanceNumber),float(ds.ImagePositionPatient[2]),int(ds.Rows),int(ds.Columns)
        except Exception as e: err=e; time.sleep(1)
    raise err
ip=f"{O}/cryo_index.json"
if os.path.exists(ip): idx=json.load(open(ip))
else:
    names=objects(); print("objects",len(names),flush=True)
    with cf.ThreadPoolExecutor(16) as ex: allidx=list(ex.map(head,names))
    allidx.sort(key=lambda t:-t[2]); idx=allidx[::a.step]; json.dump(idx,open(ip,"w")); print("indexed",len(allidx),"kept",len(idx),"z",idx[0][2],idx[-1][2],flush=True)
Z=len(idx); R,C=idx[0][3],idx[0][4]; H,W=R//F,C//F
vp=f"{O}/cryo_1mm.npy"; dp=f"{O}/done.json"
vol=np.lib.format.open_memmap(vp,mode="r+" if os.path.exists(vp) else "w+",dtype=np.uint8,shape=(Z,H,W,3))
done=set(json.load(open(dp))) if os.path.exists(dp) else set()
def fetch(k):
    n=idx[k][0]
    for _ in range(4):
        try:
            d=urllib.request.urlopen(f"https://storage.googleapis.com/{B}/{n}").read(); px=pydicom.dcmread(io.BytesIO(d)).pixel_array
            return k,px[:H*F,:W*F].reshape(H,F,W,F,3).mean(axis=(1,3)).astype(np.uint8)
        except Exception as e: err=e; time.sleep(2)
    raise err
todo=[k for k in range(Z) if k not in done]; print("slices",Z,"done",len(done),"todo",len(todo),flush=True); t0=time.time(); n=0
with cf.ThreadPoolExecutor(a.workers) as ex:
    for k,small in ex.map(fetch,todo):
        vol[k]=small; done.add(k); n+=1
        if n%25==0: vol.flush(); json.dump(sorted(done),open(dp,"w")); print(f"{len(done)}/{Z} {time.time()-t0:.0f}s",flush=True)
vol.flush(); json.dump(sorted(done),open(dp,"w")); print("STREAM_DONE",len(done),"/",Z,flush=True)
