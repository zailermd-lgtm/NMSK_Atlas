"""Q200: edit a viewer bundle (bundle.json + bundle.bin) -- replace / add structures, keep every other entry byte-identical."""
from __future__ import annotations
import json
import base64
import shutil
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree


class Bundle:
    def __init__(self, d):
        self.dir = Path(d)
        self.j = json.loads((self.dir / "bundle.json").read_text())
        blob = (self.dir / "bundle.bin").read_bytes()
        self.q = float(self.j["quantum_mm"])
        off = 0
        self.items = []
        for e in self.j["structures"]:
            nv, nf = int(e["nv"]), int(e["nf"])
            n = nv * 6 + nf * 6
            raw = blob[off:off + n]
            off += n
            self.items.append(dict(e=dict(e), raw=raw, new=None, orig=True))
        assert off == len(blob)
        self._skin = None

    # ---- access
    def mesh(self, it):
        e = it["e"]; nv, nf = int(e["nv"]), int(e["nf"])
        v = np.frombuffer(it["raw"], np.int16, nv * 3, 0).reshape(-1, 3).astype(np.float64) * self.q
        f = np.frombuffer(it["raw"], np.uint16, nf * 3, nv * 6).reshape(-1, 3).astype(np.int64)
        return v, f

    def find(self, sid):
        return [i for i, it in enumerate(self.items) if it["e"]["id"] == sid]

    def get(self, sid):
        i = self.find(sid)
        if not i:
            return None
        v, f = self.mesh(self.items[i[0]])
        return dict(e=self.items[i[0]]["e"], v=v, f=f)

    # ---- edit
    def _skin_tree(self):
        if self._skin is None:
            s = self.get("skin")
            from scripts.transfer.q200_geom import sample_surface
            self._skin = cKDTree(sample_surface(s["v"], s["f"], 60000, 3))
        return self._skin

    def _depth(self, v):
        d = self._skin_tree().query(v[:: max(1, len(v) // 4000)])[0]
        return round(float(d.min()), 1), round(float(np.median(d)), 1)

    def _set(self, it, v, f):
        assert len(v) < 65536
        e = it["e"]
        vq = np.round(v / self.q)
        assert np.abs(vq).max() < 32767
        e["nv"], e["nf"], e["tris_full"] = int(len(v)), int(len(f)), int(len(f))
        e["depth_min"], e["depth_med"] = self._depth(vq * self.q)
        it["raw"] = vq.astype(np.int16).tobytes() + np.asarray(f, np.uint16).tobytes()
        it["orig"] = False

    def replace(self, sid, v, f, rec_updates=None, subject=None):
        i = self.find(sid)
        assert len(i) == 1, (sid, i)
        it = self.items[i[0]]
        self._set(it, v, f)
        if rec_updates:
            it["e"]["rec"] = {**it["e"]["rec"], **rec_updates}
        if subject:
            it["e"]["subject"] = subject

    def add(self, sid, cat, side, subject, rec, v, f):
        assert not self.find(sid), sid
        e = dict(id=sid, cat=cat, side=side, nv=0, nf=0, cell=0.0, tris_full=0, subject=subject, rec=rec)
        it = dict(e=e, raw=b"", new=None, orig=False)
        self._set(it, v, f)
        self.items.append(it)

    # ---- write
    def write(self, out, new_subject_attribution=None, copy_clinical=True):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        j = dict(self.j)
        j["structures"] = [it["e"] for it in self.items]
        j["triangles"] = int(sum(it["e"]["nf"] for it in self.items))
        subs = j["subject"].split("+")
        att = list(j["attribution"])
        for s, a in (new_subject_attribution or {}).items():
            if s not in subs:
                subs.append(s); att.append(a)
        j["subject"] = "+".join(subs); j["attribution"] = att
        blob = b"".join(it["raw"] for it in self.items)
        (out / "bundle.json").write_text(json.dumps(j))
        (out / "bundle.bin").write_bytes(blob)
        (out / "bundle.b64").write_text(base64.b64encode(blob).decode("ascii"))
        if copy_clinical:
            for p in self.dir.glob("clinical_*"):
                shutil.copy2(p, out / p.name)
        return len(blob)
