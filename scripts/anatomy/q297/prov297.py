"""Q297 provenance reader: every shipped mesh of the six pages -> its recorded provenance, with no geometry decode.

Reads the page as the BROWSER reads it, so what this module reports is what a viewer is actually told:
  * own pages (Imaging M / Imaging F): the `bundle-json` script tag -- one entry per structure, with `subject` and `rec`.
  * Z pages (Base / Combined): `window.__ANATOMY_MANIFEST__` -- one `meshes` entry per structure, with `rec` and the
    `hd` / `fd` default-visibility flags.
It also ports, line for line, the two functions the viewer itself uses to turn that into the sentence on the card
(`baseSubject` / `classifySource` of viewer/atlas_viewer.template.html), so the audit can compare what a structure IS
against what the page SAYS it is."""
from __future__ import annotations
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DIRS = {"own_m": ("viewer_m_hr", "atlas_viewer_male.html", "own"),
        "own_f": ("viewer_f_hr", "atlas_viewer_female.html", "own"),
        "base_m": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan"),
        "base_f": ("viewer_base_female", "atlas_viewer_base_female.html", "zan"),
        "comb_m": ("viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan"),
        "comb_f": ("viewer_zan_female", "atlas_viewer_zan_female.html", "zan")}
KEYS = list(DIRS)
LABEL = {"own_m": "Imaging M", "own_f": "Imaging F", "base_m": "Base M",
         "base_f": "Base F", "comb_m": "Combined M", "comb_f": "Combined F"}


def page_html(key, root="build/q296"):
    dn, hn, kind = DIRS[key]
    d = (REPO / root / dn)
    return (d / hn).read_text(encoding="utf-8"), d, kind


def structures(key, root="build/q296"):
    """[{id, name, sys, side, subject, rec, hd, fd}] exactly as the page carries them."""
    h, d, kind = page_html(key, root)
    out = []
    if kind == "own":
        b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
        for e in b["structures"]:
            rec = e.get("rec") or {}
            out.append(dict(id=e["id"], name=rec.get("name", e["id"]), sys=e.get("cat"),
                            side={"right": "r", "left": "l"}.get(e.get("side"), "m"),
                            subject=e.get("subject", ""), rec=rec, hd=bool(e.get("hd")), fd=bool(e.get("fd"))))
    else:
        man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", h, re.M).group(1))
        for r in man["meshes"]:
            out.append(dict(id=r["id"], name=r["name"], sys=r["sys"], side=r["side"], subject="zan",
                            rec=r.get("rec") or {}, hd=bool(r.get("hd")), fd=bool(r.get("fd"))))
    return out


# ------------------------------------------------------------------ the viewer's own source-class rule, ported
def subject_labels(h):
    m = re.search(r"var SUBJECT_LABELS = \{", h)
    if not m:
        return {}
    i = m.end(); depth = 1; j = i
    while depth:
        c = h[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        j += 1
    return {mm.group(1): mm.group(2) for mm in re.finditer(r'(\w+):\s*"((?:[^"\\]|\\.)*)"', h[i:j - 1])}


def base_subject(sub, L):
    sub = re.sub(r"(_contfix_mesh|_contfix)$", "", sub or "")
    if sub not in L:
        sub = re.sub(r"_fix$", "", sub)
    return sub


def classify_source(sub, badge, L):
    """port of classifySource() in viewer/atlas_viewer.template.html -- the class the own-page card prints."""
    b = base_subject(sub, L)
    for pre, cls in (("mirror_", "mirrored_opposite"), ("xfer_zan2", "filled_zan"),
                     ("xfer_hrasculpt2", "reference_model"), ("xfer_cvh2", "registered_other_person"),
                     ("xfer_hra2", "reference_same_donor")):
        if b.startswith(pre):
            return cls
    if re.search(r"(^|_)xfer", b):
        return "transferred"
    if b.startswith("ct_s1159"):
        return "other_specimen"
    if re.search(r"rule", L.get(b, ""), re.I):
        return "rule_based"
    if re.match(r"\s*(procedural/)?rule-based", badge or "", re.I):
        return "rule_based"
    return "measured"
