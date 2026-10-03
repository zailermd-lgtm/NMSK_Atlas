"""Download whole DICOM series from the Imaging Data Commons public GCS mirror.

    python3 scripts/download_idc_series.py [--root DIR] SERIES_UUID [SERIES_UUID ...]

Files land in `DIR/dcm/<UUID>/`. Anonymous HTTPS to storage.googleapis.com,
bucket `idc-open-data` (the `public-datasets-idc` bucket named in IDC's
s5cmd manifests does not resolve from here; the same object prefixes do on
`idc-open-data`). Retries each object four times. Used for the NLM Visible
Human Project series (public domain); the manifest with all 39 VHP series is
Zenodo record 12690050."""
import json, urllib.request, os, sys, concurrent.futures as cf
args=sys.argv[1:]; S=os.path.dirname(os.path.abspath(__file__)); B='idc-open-data'
if args and args[0]=='--root': S=args[1]; args=args[2:]
for u in args:
    names=[]; tok=None
    while True:
        q=f"https://storage.googleapis.com/storage/v1/b/{B}/o?prefix={u}/&maxResults=1000&fields=items(name),nextPageToken"+(f"&pageToken={tok}" if tok else "")
        j=json.load(urllib.request.urlopen(q)); names+=[i['name'] for i in j.get('items',[])]; tok=j.get('nextPageToken')
        if not tok: break
    d=os.path.join(S,'dcm',u); os.makedirs(d,exist_ok=True)
    def get(n):
        out=os.path.join(d,os.path.basename(n))
        if os.path.exists(out) and os.path.getsize(out)>0: return 0
        for a in range(4):
            try: urllib.request.urlretrieve(f"https://storage.googleapis.com/{B}/{n}",out); return 1
            except Exception as e: err=e
        raise err
    with cf.ThreadPoolExecutor(8) as ex: got=sum(ex.map(get,names))
    print(u,"files",len(names),"downloaded",got,flush=True)
print("DL_DONE",flush=True)
