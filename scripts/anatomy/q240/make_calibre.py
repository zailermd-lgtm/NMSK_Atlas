#!/usr/bin/env python3
"""Q240: calibre table of the arteries / veins / nerves of the six pages (vessel + nerve label levels in the Labels panel).

    python3 scripts/anatomy/q240/make_calibre.py                     # write data/anatomy/calibre.json from the latest page dirs (geometry of each page's own bodies)
    python3 scripts/anatomy/q240/make_calibre.py --inject DIR...     # put the page's table into the page html (and index.html) of each page dir (needs data/anatomy/calibre.json)
    python3 scripts/anatomy/q240/make_calibre.py --validate          # the 20 named checks against textbook calibres (printed + stored in calibre.json)

Per structure: kind (a = artery, v = vein, n = nerve; from the atlas layer + the name, others such as heart chambers / valves get none), diameter_mm (mean tube diameter
estimated from the mesh: calibre.py) and level 1..4. Levels (documented in the Labels panel and the abbreviation list):
    arteries / veins   1 main  >= 6 mm or a named trunk   2 secondary 3 - 6 mm   3 tertiary 1.5 - 3 mm   4 small < 1.5 mm
    nerves             1 trunk >= 4 mm or a named trunk   2 branches  2 - 4 mm   3 small    1 - 2 mm     4 fine  < 1 mm
A named trunk (TRUNKS below) is level 1 whatever the mesh calibre: the atlas meshes are stylised, e.g. the median nerve mesh is ~1.5 mm where the nerve is 4-5 mm, and a
reader asking for "main vessels / nerves only" expects the named trunks; the promotion is stored in the table (field p = 1) so it stays visible and reviewable.
The page embeds {"v":1,"c":{id:[kind, diameter_mm, level, promoted]}} between the `NMSK-CALIBRE begin/end` markers of the template.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/anatomy/q220"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q236"))
from calibre import tube_diameter  # noqa: E402
from pages import PAGES  # noqa: E402

OUT = REPO / "data/anatomy/calibre.json"
SRC_ROOTS = ["build/q240", "build/q238", "build/q236", "build/q235"]
BEGIN, END = "<!-- NMSK-CALIBRE begin -->", "<!-- NMSK-CALIBRE end -->"
LEVEL_A = [("main", 6.0), ("secondary", 3.0), ("tertiary", 1.5), ("small", 0.0)]
LEVEL_N = [("trunk", 4.0), ("branches", 2.0), ("small", 1.0), ("fine", 0.0)]

VEIN = re.compile(r"(^|_)(vein|veins|vena|v|sinus|sinuses|venous|plexus)(_|$)")
ART = re.compile(r"(^|_)(artery|arteries|a|aorta|arterial|trunk|arch|branch|branches|anastomosis|circle)(_|$)|aort|arter")
NERVE = re.compile(r"(^|_)(n|nn|nerve|nerves|plexus|trunk|trunks|root|roots|rami|ramus|branch|branches|cord|cords|div|division|divisions|ansa|ganglion|ganglia|chorda)(_|$)")
NOT_VESSEL = re.compile(r"atrium|ventricle|leaflet|papillary|valve|unnamed|(^|_)x(_|$)|chordae|septum")
# named main trunks (level 1 whatever the mesh calibre), matched on the id without the zan_ prefix and side suffix
TRUNKS_A = re.compile(r"^(aorta|ascending_aorta|aortic_arch.*|descending_thoracic_aorta|abdominal_aorta|thoracic_aorta|brachiocephalic_trunk|common_carotid_a|internal_carotid_a|external_carotid_a|"
                      r"subclavian_a|axillary_a|axillary_artery|brachial_a|brachial_artery|common_iliac_a|external_iliac_a|internal_iliac_a|femoral_a|femoral_artery|popliteal_a|popliteal_artery|"
                      r"superior_vena_cava|inferior_vena_cava|brachiocephalic_v|internal_jugular_v|subclavian_v|axillary_v|axillary_vein|common_iliac_v|external_iliac_v|femoral_v|femoral_vein|popliteal_v|popliteal_vein|"
                      r"pulmonary_trunk|pulmonary_a.*|renal_a|renal_v|superior_mesenteric_a|inferior_mesenteric_a|coeliac_trunk|celiac_trunk|portal_vein|hepatic_portal_vein|azygos_v)$")
TRUNKS_N = re.compile(r"^(sciatic_n|tibial_n|common_fibular_n|common_peroneal_n|femoral_n|obturator_n|median_n.*|ulnar_n|radial_n|musculocutaneous_n|axillary_n|vagus_n|phrenic_n|optic_n|"
                      r"brachial_trunk_.*|brachial_cord_.*|lumbar_plexus.*|sacral_plexus.*|spinal_accessory_n|accessory_n|facial_n|trigeminal_n|hypoglossal_n|glossopharyngeal_n|oculomotor_n|"
                      r"trochlear_n|abducens_n|vestibulocochlear_n|olfactory_n|recurrent_laryngeal_n|superficial_fibular_n|deep_fibular_n|saphenous_n)$")


def norm(sid: str) -> str:
    s = re.sub(r"^zan_", "", sid)
    return re.sub(r"_(l|r)$", "", s)


def kind_of(sid: str, cat: str) -> str | None:
    n = norm(sid)
    if cat == "nerve":                       # the Z "nerve" layer also holds brain / cord / eye parts (nuclei, tracts, fornix, sclera ...): those get none
        return "n" if NERVE.search(n) else None
    if cat != "vessel" or NOT_VESSEL.search(n):
        return None
    if VEIN.search(n):
        return "v"
    if ART.search(n):
        return "a"
    return None


def level_of(kind: str, d: float | None, sid: str) -> tuple[int, int]:
    """-> (level 1..4, promoted 0|1)"""
    ladder = LEVEL_N if kind == "n" else LEVEL_A
    lv = 4
    if d is not None:
        for i, (_, lo) in enumerate(ladder):
            if d >= lo:
                lv = i + 1
                break
    trunk = (TRUNKS_N if kind == "n" else TRUNKS_A).match(norm(sid))
    if trunk and lv > 1:
        return 1, 1
    return lv, 0


def page_path(d: str) -> Path | None:
    for r in SRC_ROOTS:
        p = REPO / r / d / PAGES[d]
        if p.exists():
            return p
    return None


def table_for(html_path: Path) -> dict[str, list]:
    import build_parts_sidecar as sc
    kind, out = sc.load_page(html_path)
    by: dict[str, list] = {}
    for sid, sd, cat, V, F in out:
        k = kind_of(sid, cat)
        if not k:
            continue
        e = by.setdefault(sid, [k, [], [], 0])
        e[1].append(V); e[2].append(F + e[3]); e[3] += len(V)
    tab = {}
    for sid, (k, Vs, Fs, _) in by.items():
        r = tube_diameter(np.vstack(Vs), np.vstack(Fs))
        d = r["diameter_mm"]
        lv, pr = level_of(k, d, sid)
        tab[sid] = [k, d, lv, pr]
    return tab


# ---- the 20 named checks: (label, id regex on the page, kind, expected low, expected high [mm], source of the figure)
CHECKS = [
    ("Descending thoracic aorta", r"^descending_thoracic_aorta$", 20, 30),
    ("Abdominal aorta", r"^abdominal_aorta$", 15, 25),
    ("Aortic arch (arch + great vessels mesh)", r"^aortic_arch_and_great_vessels$", 22, 35),
    ("Inferior vena cava", r"^inferior_vena_cava$", 15, 30),
    ("Superior vena cava", r"^superior_vena_cava$", 15, 25),
    ("Common carotid artery R", r"^common_carotid_a_r$|^zan_common_carotid_artery_r$", 6, 9),
    ("Subclavian artery R", r"^subclavian_a_r$|^zan_subclavian_artery_r$", 6, 11),
    ("Femoral artery R", r"^femoral_a_r$|^zan_femoral_artery_r$", 8, 10),
    ("Femoral vein R", r"^femoral_v_r$|^zan_femoral_vein_r$", 9, 13),
    ("Popliteal artery R", r"^popliteal_a_r$|^zan_popliteal_artery_r$", 5, 8),
    ("Brachial artery R", r"^zan_brachial_artery_r$", 3.5, 5.5),
    ("Radial artery R", r"^zan_radial_artery_r$", 2.5, 3.5),
    ("Ulnar artery R", r"^zan_ulnar_artery_r$", 2.5, 4),
    ("Posterior tibial artery R", r"^zan_posterior_tibial_artery_r$", 3, 5),
    ("Dorsal digital arteries of hand R", r"^zan_dorsal_digital_arteries_of_hand_r$", 0.8, 2),
    ("Sciatic nerve R", r"^sciatic_n$|^sciatic_n_r$|^zan_sciatic_nerve_r$", 10, 15),
    ("Tibial nerve R", r"^tibial_n$|^tibial_n_r$", 5, 9),
    ("Median nerve R", r"^median_n_lateral_root_r$|^median_n_r$|^zan_median_nerve_r$", 4, 5),
    ("Ulnar nerve R", r"^ulnar_n_r$|^zan_ulnar_nerve_r$", 3, 5),
    ("Proper palmar digital branches of ulnar nerve R", r"^zan_proper_palmar_digital_branches_of_ulnar_nerve_r$", 0.8, 1.6),
]


def validate(tab: dict) -> list[dict]:
    rows = []
    for label, rx, lo, hi in CHECKS:
        m = [(sid, v) for sid, v in tab.items() if re.search(rx, sid)]
        if not m:
            rows.append({"check": label, "id": None, "expected_mm": [lo, hi], "model_mm": None, "ratio": None, "verdict": "not in this page"})
            continue
        sid, v = sorted(m)[0]
        d = v[1]
        mid = (lo + hi) / 2
        ratio = d / mid if d else None
        verdict = "within range" if d is not None and lo <= d <= hi else ("within x1.6" if d is not None and lo / 1.6 <= d <= hi * 1.6 else "outside x1.6")
        rows.append({"check": label, "id": sid, "expected_mm": [lo, hi], "model_mm": d, "ratio": round(ratio, 2) if ratio else None, "level": v[2], "verdict": verdict})
    return rows


def block(tab: dict) -> str:
    js = json.dumps({"v": 1, "c": {k: [v[0], v[1], v[2], v[3]] for k, v in sorted(tab.items())}}, separators=(",", ":")).replace("<", "\\u003c")
    return f'{BEGIN}<script type="application/json" id="nmsk-calibre">{js}</script>{END}'


def load_out() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def inject(d: Path) -> int:
    pages = load_out()["pages"]
    key = None
    for f in sorted(d.glob("atlas_viewer*.html")):
        for k, name in PAGES.items():
            if f.name == name:
                key = k
    if key is None or key not in pages:
        raise SystemExit(f"no calibre table for {d}")
    tab = {sid: [kk, dd, lv, pr] for sid, (kk, dd, lv, pr) in pages[key]["c"].items()}
    n = 0
    for f in sorted(d.glob("*.html")):
        s = f.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            continue
        i, j = s.index(BEGIN), s.index(END) + len(END)
        f.write_text(s[:i] + block(tab) + s[j:], encoding="utf-8")
        print(f"calibre: {f.relative_to(REPO) if f.is_relative_to(REPO) else f}: {len(tab)} vessels / nerves")
        n += 1
    if not n:
        raise SystemExit(f"no page with the NMSK-CALIBRE markers in {d}")
    return n


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--inject":
        for a in argv[1:]:
            inject(Path(a))
        return 0
    pages = {}
    for d in PAGES:
        p = page_path(d)
        if p is None:
            print(f"skip {d}: no page found under {SRC_ROOTS}")
            continue
        tab = table_for(p)
        from collections import Counter
        cnt = Counter((v[0], v[2]) for v in tab.values())
        pages[d] = {"source": str(p.parent.relative_to(REPO)), "count": len(tab), "c": {k: v for k, v in sorted(tab.items())},
                    "by_kind_level": {f"{k}{l}": n for (k, l), n in sorted(cnt.items())}, "checks": validate(tab)}
        print(d, p.parent.relative_to(REPO), len(tab), dict(sorted(pages[d]["by_kind_level"].items())))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = {"version": 1, "definition": {
               "kinds": {"a": "artery", "v": "vein", "n": "nerve"},
               "arteries_veins": [{"level": i + 1, "name": n, "min_diameter_mm": lo} for i, (n, lo) in enumerate(LEVEL_A)],
               "nerves": [{"level": i + 1, "name": n, "min_diameter_mm": lo} for i, (n, lo) in enumerate(LEVEL_N)],
               "diameter": "mean tube diameter estimated from the mesh (scripts/anatomy/q240/calibre.py): median over slabs of the median perpendicular vertex distance to the local axis x 2, cross-checked with lateral area / (pi x centreline length)",
               "promoted": "p = 1: a named main trunk whose mesh calibre would give a lower level is level 1 (TRUNKS_A / TRUNKS_N in make_calibre.py)"},
           "pages": pages}
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", OUT.relative_to(REPO), OUT.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--validate"]:
        doc = load_out()
        for k, pg in doc["pages"].items():
            print("==", k)
            for r in pg["checks"]:
                print(f"  {r['check']:48s} {str(r['id']):42s} model {r['model_mm']} mm  expected {r['expected_mm'][0]}-{r['expected_mm'][1]}  {r['verdict']}")
        raise SystemExit(0)
    raise SystemExit(main(sys.argv[1:]))
