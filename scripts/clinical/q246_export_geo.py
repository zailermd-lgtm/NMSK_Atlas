#!/usr/bin/env python3
"""Q246 -- dump the packed imaging geometry of a BUILT page (what NMSKImaging.geo() holds) to raw files so the continuity harness can run the kernels under node.

    python3 scripts/clinical/q246_export_geo.py PAGE_DIR PAGE.html OUT_DIR

Writes OUT_DIR/<name>.bin (little-endian typed arrays: pos f32, idx u32, vStart u32, tStart u32, bbox f32, cls u8, kind u8, skin u8, render u8, order u32, skinList u32)
and OUT_DIR/meta.json (names, ids, n, nv, nt, bodyBox).  Headless Chromium (swiftshader), same loader as q239_check.py."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q239_host import serve  # noqa: E402

THREE = "/tmp/three_x/package/build/three.min.js"
FIELDS = ["pos", "idx", "vStart", "tStart", "bbox", "cls", "kind", "skin", "render", "order", "skinList"]
CHUNK = 4_000_000


def main(page_dir, page, out_dir):
    from playwright.sync_api import sync_playwright
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    srv, port = serve(page_dir, page=page)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_context(viewport={"width": 1366, "height": 768}).new_page(); pg.set_default_timeout(900000)
        pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        pg.route("**/three*.js", lambda r: r.fulfill(path=THREE, content_type="application/javascript"))
        pg.goto(f"http://127.0.0.1:{port}/{page}")
        pg.wait_for_function("window.NMSKImaging", timeout=900000)
        pg.wait_for_timeout(2000)
        pg.evaluate("NMSKImaging.ready()")
        pg.wait_for_function("NMSKImaging.geo() !== null", timeout=900000)
        meta = pg.evaluate("""()=>{var g=NMSKImaging.geo(); window.__q246=g; return {n:g.n,nv:g.nv,nt:g.nt,names:g.names,bodyBox:g.bodyBox,ids:g.recs.map(function(r){return r.id}),
          classKeys:NMSKImaging.table().classes.map(function(c){return c.key}), len:%s}}""" % json.dumps({f: 0 for f in FIELDS}))
        meta["bytes"] = {}
        for f in FIELDS:
            nbytes = pg.evaluate("(f)=>window.__q246[f].byteLength", f)
            meta["bytes"][f] = nbytes
            with open(out / f"{f}.bin", "wb") as fh:
                for o in range(0, nbytes, CHUNK):
                    s = pg.evaluate("""([f,o,c])=>{var a=window.__q246[f], u=new Uint8Array(a.buffer,a.byteOffset+o,Math.min(c,a.byteLength-o)), s='', i;
                        for(i=0;i<u.length;i+=32768) s+=String.fromCharCode.apply(null,u.subarray(i,Math.min(u.length,i+32768))); return btoa(s);}""", [f, o, CHUNK])
                    fh.write(base64.b64decode(s))
        meta["dtype"] = {"pos": "f4", "idx": "u4", "vStart": "u4", "tStart": "u4", "bbox": "f4", "cls": "u1", "kind": "u1", "skin": "u1", "render": "u1", "order": "u4", "skinList": "u4"}
        (out / "meta.json").write_text(json.dumps(meta))
        b.close()
    srv.shutdown()
    print("exported", meta["n"], "structures,", meta["nv"], "vertices,", meta["nt"], "triangles ->", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
