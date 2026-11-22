#!/usr/bin/env python3
"""Q217: rebuild a bundle dir (bundle.json + bundle.bin + bundle.b64 + clinical_*) from a published own page (the page embeds the bundle json + the geometry blob).
    python3 scripts/transfer/q217_bundle_from_page.py build/q214/viewer_m_hr atlas_viewer_male.html build/viewer_m_hr_q214"""
import base64
import json
import re
import shutil
import sys
from pathlib import Path

d, html, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
t = (d / html).read_text(encoding="utf-8")
b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', t, re.S).group(1))
files = json.loads(re.search(r"BIN_FILES\s*=\s*(\[.*?\])\s*;?\s*$", t, re.M).group(1))
blob = b"".join(base64.b64decode((d / f["path"]).read_text().strip()) for f in files)
out.mkdir(parents=True, exist_ok=True)
(out / "bundle.json").write_text(json.dumps(b))
(out / "bundle.bin").write_bytes(blob)
(out / "bundle.b64").write_text(base64.b64encode(blob).decode("ascii"))
for p in d.glob("clinical_*"):
    shutil.copy2(p, out / p.name)
print(len(b["structures"]), "structures", len(blob), "bytes")
