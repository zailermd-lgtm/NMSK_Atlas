"""Q198 loader: the six q197 pages -> list of structures {id,name,sys,side,v,f,src} in one atlas frame (mm; +X right, +Y sup, +Z ant).
Reads the data literals the page itself embeds (geo_NN.txt = base64 blob; own pages: bundle-json + blob; Z pages: manifest with quantised boxes)."""
from __future__ import annotations
import base64, json, re, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
Q = REPO / "build" / "q197"
MODELS = {  # key: (dir, html name, kind, label)
    "own_m": ("viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (VH reconstruction)"),
    "own_f": ("viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction)"),
    "z_male": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Z male base"),
    "z_base_f": ("viewer_base_female", "atlas_viewer_base_female.html", "zan", "Z generic body (female variant)"),
    "z_male_fit": ("viewer_zan_male_fitted", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction"),
    "z_female_fit": ("viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction"),
}
SIDE_RE = re.compile(r"\.(o|e)?(l|r)$", re.I)


def _blob(d: Path, html: str) -> bytes:
    m = re.search(r"^(?:\s*var\s+)?(?:window\.__ANATOMY_)?BIN_FILES(?:__)?\s*=\s*(\[.*?\]);?$", html, re.M)
    files = json.loads(re.search(r"BIN_FILES(?:__)?\s*=\s*(\[.*?\])\s*;?\s*$", html, re.M).group(1))
    parts = [base64.b64decode((d / f["path"]).read_text().strip()) for f in files]
    return b"".join(parts)


def load(key: str, with_markers=False):
    dn, hn, kind, _ = MODELS[key]
    d = Q / dn
    html = (d / hn).read_text(encoding="utf-8")
    blob = _blob(d, html)
    out = []
    if kind == "own":
        sys.path.insert(0, str(REPO))
        from scripts.transfer.bundle_io import decode
        b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', html, re.S).group(1))
        for e, v, f in decode(b, blob):
            rec = e.get("rec") or {}
            side = {"right": "r", "left": "l"}.get(e.get("side"), "m")
            out.append(dict(id=e["id"], name=rec.get("name", e["id"]), sys=e["cat"], side=side, v=v.astype(np.float64), f=f.astype(np.int64),
                            src=e.get("subject", ""), rec=rec))
    else:
        man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", html, re.M).group(1))
        u16 = np.frombuffer(blob, np.uint8)
        for r in man["meshes"]:
            vc, ic = r["vc"], r["ic"]
            q = np.frombuffer(blob, np.uint16, vc * 3, r["vo"]).reshape(-1, 3).astype(np.float64)
            f = np.frombuffer(blob, np.uint16, ic * 3, r["io"]).reshape(-1, 3).astype(np.int64)
            v = np.asarray(r["min"]) + q / 65535.0 * np.asarray(r["span"])
            out.append(dict(id=r["id"], name=r["name"], sys=r["sys"], side=r["side"], v=v, f=f, src="zan", rec=r.get("rec") or {}))
    cnt = {}
    for s_ in out:
        if s_["sys"] == "bone":
            cnt[s_["id"]] = cnt.get(s_["id"], 0) + 1
    seen = {}
    for s_ in out:
        if s_["sys"] == "bone" and cnt[s_["id"]] > 1:
            seen[s_["id"]] = seen.get(s_["id"], 0) + 1
            s_["id"] = f"{s_['id']}#{seen[s_['id']]}"
    return out


if __name__ == "__main__":
    for k in MODELS:
        s = load(k)
        print(k, len(s), sum(len(x["v"]) for x in s))
