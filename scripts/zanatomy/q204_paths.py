"""Q204: point the (unchanged) Q198 loader at the six CURRENTLY PUBLISHED pages. Import this BEFORE any q198_* module that uses MODELS."""
from scripts.zanatomy import q198_load as L

PAGES = {  # key: (dir relative to build/q197 (loader joins it), html, kind, label)
    "own_m": ("../q203/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (VH reconstruction)"),
    "own_f": ("../q203/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction)"),
    "z_male": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Z male base"),
    "z_base_f": ("../q202/viewer_base_female", "atlas_viewer_base_female.html", "zan", "Z generic body (female variant)"),
    "z_male_fit": ("../q202/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction"),
    "z_female_fit": ("../q202/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction"),
}
L.MODELS.clear()
L.MODELS.update(PAGES)


# ---- optional: Q200/Q203 ship the Z-completion of an own structure as a SEPARATE entry "<id>_zfill*"; the Q198 code looks bones/muscles up by exact id and measures
# flat cut faces per mesh, so a measured structure with its continuation looks "cut" / "gapped". Q204_MERGE=1 merges each continuation into its base structure before the
# (unchanged) audit and drops the base's flat cut faces that lie under the continuation's footprint (approximation of q200_merge). Q204_RAW selects the output dir.
import os, re
import numpy as np

RAW_DIR = os.environ.get("Q204_RAW", "build/q204_raw")
_ZF = re.compile(r"_zfill\w*$")


def merge_zfill(S):
    cont = {}
    for s_ in S:
        if _ZF.search(s_["id"]):
            cont.setdefault(_ZF.sub("", s_["id"]), []).append(s_)
    out = []
    for s_ in S:
        if _ZF.search(s_["id"]):
            continue
        cs = cont.get(s_["id"])
        if not cs or s_["sys"] == "skin":
            out.append(s_)
            continue
        v, f = s_["v"], s_["f"]
        keep = np.ones(len(f), bool)
        vf = v[f]
        nrm = np.cross(vf[:, 1] - vf[:, 0], vf[:, 2] - vf[:, 0]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
        cen = vf.mean(1)
        cv = np.concatenate([c["v"] for c in cs])
        for ax in range(3):
            flat = (np.abs(nrm[:, ax]) > 0.95) & (np.ptp(vf[:, :, ax], axis=1) < 0.3)
            if not flat.any():
                continue
            pos = np.round(cen[flat, ax] / 0.5) * 0.5
            for pl in np.unique(pos):
                m = flat.copy(); m[flat] = pos == pl
                near = cv[np.abs(cv[:, ax] - pl) < 3.0]
                if len(near) < 10:
                    continue
                o = [a for a in range(3) if a != ax]
                lo, hi = near[:, o].min(0) - 5, near[:, o].max(0) + 5
                inside = (cen[m][:, o] >= lo).all(1) & (cen[m][:, o] <= hi).all(1)
                idx = np.where(m)[0][inside]
                keep[idx] = False
        parts_v = [v]; parts_f = [f[keep]]; off = len(v)
        for c in cs:
            parts_v.append(c["v"]); parts_f.append(c["f"] + off); off += len(c["v"])
        m_ = dict(s_); m_["v"] = np.concatenate(parts_v); m_["f"] = np.concatenate(parts_f)
        m_["merged_zfill"] = [c["id"] for c in cs]
        out.append(m_)
    return out


if os.environ.get("Q204_MERGE"):
    _orig_load = L.load

    def _load_merged(key, with_markers=False):
        S = _orig_load(key, with_markers)
        return merge_zfill(S) if L.MODELS[key][2] == "own" else S
    L.load = _load_merged
