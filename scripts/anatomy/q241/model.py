"""Q241 model loader: one of the six CURRENT pages -> structures + midsagittal plane + bone registry (bone key -> merged mesh).
Frame of every model: mm, +X = the subject's right, +Y superior, +Z anterior (scripts/anatomy/q237/core.py). Reads the page dirs, never edits them."""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q237")); sys.path.insert(0, str(REPO / "scripts" / "zanatomy")); sys.path.insert(0, str(REPO))
import core as C  # noqa: E402  (scripts/anatomy/q237/core.py)

# the current page dirs (Hub v34 = Q236 labels + Q237 symmetric view); override a page with Q241_SRC_<key>
SRC = {"own_m": "build/q238/viewer_m_hr", "own_f": "build/q238/viewer_f_hr", "base_m": "build/q238/viewer_zan_atlas",
       "base_f": "build/q238/viewer_base_female", "comb_m": "build/q238/viewer_zan_vhm", "comb_f": "build/q238/viewer_zan_female"}
LABEL = {k: v[3] for k, v in C.PAGES.items()}
KEYS = list(C.PAGES)


def page_dir(key):
    d = os.environ.get("Q241_SRC_" + key, SRC[key])
    return Path(d) if os.path.isabs(d) else REPO / d


class Model:
    def __init__(self, key, load=True):
        self.key = key
        self.kind = C.PAGES[key][2]
        self.dir = page_dir(key)
        os.environ["Q237_SRC_" + key] = str(self.dir)
        self.S = C.load(key) if load else []
        pj = json.load(open(REPO / "data/derived/Q237_pairing.json"))["pages"][key]["plane"]
        self.plane = C.Plane(pj["n"], pj["d_mm"])
        if self.plane.n[0] < 0:
            self.plane = C.Plane(-self.plane.n, -self.plane.d)
        self._bones = None

    # ------------------------------------------------------------------ bones
    def bones(self):
        """{key: dict(v, f, idx[list of structure idx])}: one merged mesh per anatomical bone (pieces such as _zfill / _q212 join their bone)."""
        if self._bones is None:
            B = {}
            for x in self.S:
                if x["sys"] != "bone":
                    continue
                k = bone_key(x["id"], x["side"])
                if k is None:
                    continue
                B.setdefault(k, []).append(x["idx"])
            out = {}
            for k, ids in B.items():
                v, f = C.merge(self.S, ids)
                out[k] = dict(v=v, f=f, idx=ids)
            self._bones = out
        return self._bones


# ------------------------------------------------------------------ naming
NUM = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12}
DROP = re.compile(r"_(zfill\w*|q\d+\w*|distal|proximal)(?=_|$)")


def bone_key(i, side_field="m"):
    """canonical bone key from a structure id (Z names and own names): 'femur_r', 'vert_c3', 'vert_t5', 'vert_l2', 'rib_5_l', 'mc_2_r', 'ph_hand_2_prox_r', 'carpal_lunate_r' ... or None.
    Merged own meshes keep their group name ('ribs_l', 'metacarpals_r', 'phalanges_hand_l', 'phalanges_foot_r', 'carpals_l', 'metatarsals_l', 'cervical_vertebrae#2' ...)."""
    s = i.lower()
    s = re.sub(r"^zan_", "", s)
    s = DROP.sub("", s)
    m = re.match(r"^(.*)_(l|r)$", s)
    side = m.group(2) if m else None
    base = m.group(1) if m else s
    sfx = ("_" + side) if side else ""
    if re.match(r"^(skin|sinus|nasal_septal|lateral_process|major_alar|minor_alar|corniculate|cricoid|arytenoid|cuneiform_cart|thyroid_cart|epiglott|tracheal|costal|xiphoid)", base) and not base.startswith("xiphoid"):
        return None
    if re.search(r"molar|incisor|canine|premolar|tooth|incus|malleus|stapes|ossicle", base):
        return "head_misc_" + base + sfx
    mm = re.match(r"^vertebra_([ctl])(\d+)$", base)
    if mm:
        return "vert_%s%d" % (mm.group(1), int(mm.group(2)))
    if base == "atlas_c1": return "vert_c1"
    if base == "axis_c2": return "vert_c2"
    base = re.sub(r"^(sacrum|coccyx)#\d+$", r"\1", base)
    mm = re.match(r"^(cervical|thoracic|lumbar)_vertebrae(#\d+)?$", base)
    if mm:
        return "%s_vertebrae%s" % (mm.group(1), mm.group(2) or "")
    mm = re.match(r"^(\w+)_rib$", base)
    if mm and mm.group(1) in NUM:
        return "rib_%d%s" % (NUM[mm.group(1)], sfx)
    mm = re.match(r"^(first|second|third|fourth|fifth)_metacarpal_bone$", base)
    mm2 = re.match(r"^metacarpal_(\d)$", base)
    if mm2: return "mc_%d%s" % (int(mm2.group(1)), sfx)
    if mm: return "mc_%d%s" % (NUM[mm.group(1)], sfx)
    mm = re.match(r"^(first|second|third|fourth|fifth)_metatarsal_bone$", base)
    if mm: return "mt_%d%s" % (NUM[mm.group(1)], sfx)
    mm = re.match(r"^(proximal|middle|distal)_phalanx_of_(first|second|third|fourth|fifth)_finger_of_(hand|foot)$", base + "")
    if not mm:
        mm = re.match(r"^(proximal|middle|distal)_phalanx_of_(first|second|third|fourth|fifth)_finger_of_(hand|foot)$", re.sub(DROP, "", i.lower().replace("zan_", "", 1))[: -len(sfx)] if sfx else "")
    if mm:
        return "ph_%s_%d_%s%s" % (mm.group(3), NUM[mm.group(2)], mm.group(1)[:4], sfx)
    mm = re.match(r"^(capitate|hamate|lunate|pisiform|scaphoid|trapezium|trapezoid|triquetrum)_bone$", base)
    if mm: return "carpal_%s%s" % (mm.group(1), sfx)
    return base + sfx


if __name__ == "__main__":
    import sys as _s
    k = _s.argv[1]
    M = Model(k)
    B = M.bones()
    print(k, len(B), "bones")
    print(sorted(B)[:400])
