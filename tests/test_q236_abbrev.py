"""Q236: the abbreviation scheme (scripts/anatomy/q236/abbrev.py): deterministic, collision-free, no wrong well-known abbreviation.

Rules under test: BASE[-R|-L]; established abbreviations only from the KNOWN table (each one verified here against an independent gold list), everything else generated and flagged;
no generated abbreviation may equal a KNOWN / reserved clinical one; uniqueness per page (case-insensitive); the committed data/anatomy/abbreviations.json is consistent
with the generator; every regenerated page carries its own table."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q236"))
import abbrev  # noqa: E402
import pages as pg  # noqa: E402

DATA = REPO / "data" / "anatomy" / "abbreviations.json"

# Independent gold list: (cleaned lower-case name, abbreviation) pairs written out by hand from the anatomical literature. KNOWN must not contain anything else that
# would be a surprise, and every gold pair must be produced.
GOLD = {
    "sternocleidomastoid": "SCM", "extensor carpi radialis longus": "ECRL", "extensor carpi radialis brevis": "ECRB", "extensor carpi ulnaris": "ECU",
    "flexor carpi radialis": "FCR", "flexor carpi ulnaris": "FCU", "flexor digitorum superficialis": "FDS", "flexor digitorum profundus": "FDP",
    "flexor pollicis longus": "FPL", "extensor pollicis longus": "EPL", "extensor pollicis brevis": "EPB", "abductor pollicis longus": "APL",
    "biceps femoris": "BF", "semitendinosus": "ST", "semimembranosus": "SM", "rectus femoris": "RF", "vastus lateralis": "VL", "vastus medialis": "VM",
    "tibialis anterior": "TA", "tibialis posterior": "TP", "extensor hallucis longus": "EHL", "tensor fasciae latae": "TFL", "gluteus maximus": "GMax",
    "anterior cruciate ligament": "ACL", "posterior cruciate ligament": "PCL", "medial collateral ligament": "MCL", "lateral collateral ligament": "LCL",
    "anterior talofibular ligament": "ATFL", "calcaneofibular ligament": "CFL", "inferior vena cava": "IVC", "superior vena cava": "SVC",
    "common carotid artery": "CCA", "internal carotid artery": "ICA", "external carotid artery": "ECA", "right atrium": "RA", "left ventricle": "LV",
    "anterior interosseous nerve": "AIN", "posterior interosseous nerve": "PIN", "iliotibial tract": "ITB",
}
# names that look like a known one but are another structure: they must NOT receive the established abbreviation
NOT_KNOWN = ["Sternocleidomastoid region (skin)", "Tendon sheath of extensor carpi ulnaris", "Rectus abdominis", "Inferior oblique", "Superior rectus", "Anterior papillary muscle of right ventricle",
             "Subtendinous bursa of tibialis anterior", "Skull without the mandible", "Right coronary vein", "Ulnar collateral artery", "Sternothyroid", "Extensor carpi ulnaris tendon"]


def build1(name, side=None, sid="x"):
    return abbrev.build([{"id": sid, "name": name, "side": side}])[sid]


def test_known_table_matches_the_gold_list():
    for name, ab in GOLD.items():
        assert abbrev.KNOWN.get(name) == ab, name
    extra = set(abbrev.KNOWN) - set(GOLD)
    # every other KNOWN entry is an eponymous-free standard abbreviation too; they are listed here so that adding one is a deliberate act
    assert extra <= {"brachioradialis", "pronator teres", "pronator quadratus", "soleus", "triceps brachii", "biceps brachii", "latissimus dorsi", "erector spinae", "quadratus lumborum",
                     "levator scapulae", "external oblique", "internal oblique", "transversus abdominis", "gluteus medius", "gluteus minimus", "supraspinatus", "infraspinatus",
                     "subscapularis", "flexor pollicis brevis", "abductor pollicis brevis", "adductor pollicis", "opponens pollicis", "extensor digitorum", "extensor digiti minimi",
                     "extensor indicis", "abductor digiti minimi", "palmaris longus", "vastus intermedius", "extensor digitorum longus", "flexor hallucis longus", "flexor digitorum longus",
                     "tibial collateral ligament", "fibular collateral ligament", "ulnar collateral ligament", "anterior inferior tibiofibular ligament", "posterior inferior tibiofibular ligament",
                     "posterior talofibular ligament", "anterolateral ligament", "iliotibial band", "triangular fibrocartilage complex", "anterior superior iliac spine",
                     "posterior superior iliac spine", "anterior inferior iliac spine", "posterior inferior iliac spine", "internal jugular vein", "external jugular vein",
                     "great saphenous vein", "small saphenous vein", "superior mesenteric artery", "inferior mesenteric artery", "superior mesenteric vein", "middle cerebral artery",
                     "anterior cerebral artery", "posterior cerebral artery", "posterior inferior cerebellar artery", "anterior interventricular artery", "right coronary artery",
                     "left atrium", "right ventricle", "lateral femoral cutaneous nerve"}, sorted(extra - set(GOLD))
    vals = {}
    for k, v in abbrev.KNOWN.items():
        vals.setdefault(v, []).append(k)
    for v, ks in vals.items():                          # one abbreviation = one structure (synonyms of the same structure share it)
        if len(ks) > 1:
            assert v in ("MCL", "LCL", "ITB"), (v, ks)


@pytest.mark.parametrize("name,side,expected", [
    ("Rectus femoris", "right", "RF-R"), ("Sternocleidomastoid", "left", "SCM-L"), ("Biceps femoris", "r", "BF-R"), ("Extensor carpi radialis longus", "left", "ECRL-L"),
    ("Right atrium", "m", "RA"), ("Left ventricle", None, "LV"), ("Inferior vena cava", None, "IVC"), ("Anterior cruciate ligament (ACL)", "right", "ACL-R"),
    ("Fibular (lateral) collateral ligament (LCL)", "left", "LCL-L"), ("Vertebra L3", "m", "L3"), ("L4-L5 intervertebral disc", None, "L4/5"), ("T12-L1 intervertebral disc", None, "T12/L1"),
    ("Intervertebral disc C7-T1", None, "C7/T1"), ("Tibialis posterior muscle", "l", "TP-L"), ("Radial nerve.r", "r", "RN-R"),
])
def test_known_and_derived_abbreviations(name, side, expected):
    assert build1(name, side)[0] == expected


@pytest.mark.parametrize("name", NOT_KNOWN)
def test_look_alike_names_do_not_get_a_wrong_established_abbreviation(name):
    ab, gen, _short = build1(name, "m")
    assert gen == 1
    base = re.sub(r"(-[RL])?(\.\d+)?$", "", ab).lower()
    assert base not in {v.lower() for v in abbrev.KNOWN.values()} | {v.lower() for v in abbrev.RESERVED}


def test_clean_names():
    assert abbrev.clean("Biceps brachii (continuation beyond the data-block cut, filled from Z-Anatomy)", "left")[0] == "Biceps brachii"
    assert abbrev.clean("Skull without the mandible -- composite of the individual cranial and facial bones", "m")[0] == "Skull without the mandible"
    assert abbrev.clean("Ulnar nerve (left)", "l")[0] == "Ulnar nerve"
    assert abbrev.clean("Levator ani right muscle", "r")[0] == "Levator ani"
    assert abbrev.clean("Right atrium", "m")[0] == "Right atrium"                    # midline: 'right' is part of the name
    assert abbrev.clean("Ischiocavernosus (CVH), left (side assigned by registration; not determinable from the source)", "l")[0] == "Ischiocavernosus"
    assert abbrev.clean("Anterior cruciate ligament (ACL)", None)[1] == "ACL"
    assert abbrev.clean("Ischiocavernosus (CVH)", "l")[1] is None                     # a provenance tag is not an abbreviation of the name
    assert abbrev.clean("Abductor digiti minimi (foot)", "l")[2] is True              # a qualifier blocks the hand-muscle abbreviation


def test_collisions_are_resolved_and_deterministic():
    structs = [{"id": f"s{i}", "name": n, "side": None} for i, n in enumerate(
        ["Posterior talocalcaneal ligament", "Posterior tibiotalar ligament", "Pectoral region", "Popliteal region", "Plantar region", "Right atrium", "Rectus abdominis",
         "Anterior cruciate ligament", "Inferior oblique", "Internal oblique", "Sternothyroid", "Semitendinosus"])]
    a = abbrev.build(structs); b = abbrev.build(list(reversed(structs)))
    assert a == b                                        # independent of the order
    vals = [v[0].lower() for v in a.values()]
    assert len(set(vals)) == len(vals)
    assert a["s5"][0] == "RA" and a["s6"][0] != "RA"                               # the heart chamber keeps RA, the muscle gets a generated one
    assert a["s8"][0] != "IO" and a["s9"][0] == "IO"
    assert a["s11"][0] == "ST" and a["s10"][0] != "ST"
    assert a["s0"][0] != a["s1"][0]


def test_sides_and_same_name_ids():
    t = abbrev.build([{"id": "a_r", "name": "Rectus femoris", "side": "right"}, {"id": "a_l", "name": "Rectus femoris", "side": "left"},
                      {"id": "a_r_z", "name": "Rectus femoris (continuation beyond the data-block cut, filled from Z-Anatomy)", "side": "right"}, {"id": "m", "name": "Coccyx", "side": "m"}])
    assert t["a_r"][0] == "RF-R" and t["a_l"][0] == "RF-L" and t["a_r_z"][0] == "RF-R.2" and t["m"][0] == "Coc"
    assert t["m"][1] == 1 and t["a_r"][1] == 0


def committed():
    if not DATA.exists():
        pytest.skip("data/anatomy/abbreviations.json not generated")
    return json.loads(DATA.read_text())


def test_committed_table_is_unique_per_page_and_never_misuses_a_known_abbreviation():
    d = committed()
    assert d["version"] == 1 and len(d["pages"]) == 6
    known_vals = {v.lower() for v in abbrev.KNOWN.values()} | {v.lower() for v in d["reserved"]}
    for page, p in d["pages"].items():
        m = p["map"]
        assert len(m) == p["count"]
        lows = [v[0].lower() for v in m.values()]
        assert len(set(lows)) == len(lows), (page, [x for x in set(lows) if lows.count(x) > 1][:5])
        for sid, (ab, g) in m.items():
            base = re.sub(r"(-[RL])?(\.\d+)?$", "", ab).lower()
            if g:
                assert base not in known_vals, (page, sid, ab)          # a generated one never equals an established one
            else:
                assert base in known_vals or re.fullmatch(r"[ctls]\d{1,2}(/[ctls]?\d{1,2})?", base) or re.fullmatch(r"[a-z]{2,6}", base), (page, sid, ab)
            assert len(ab) <= 24


def test_committed_table_has_the_well_known_ones_on_all_pages():
    d = committed()
    for page, p in d["pages"].items():
        m = p["map"]
        sample = {k: v for k, v in m.items() if v[0] in ("BF-R", "RF-R", "SCM-L", "ACL-R", "PCL-L", "IVC")}
        assert len(sample) >= 3, page
        assert all(v[1] == 0 for v in sample.values())


def built_pages():
    out = []
    for d, f in pg.PAGES.items():
        p = REPO / "build" / "q236" / d / f
        if p.exists():
            out.append((d, p))
    return out


@pytest.mark.skipif(not built_pages(), reason="build/q236 not present")
def test_every_built_page_carries_its_own_table():
    for d, p in built_pages():
        html = p.read_text(encoding="utf-8")
        m = re.search(r'<!-- NMSK-ABBREV begin --><script type="application/json" id="nmsk-abbrev">(.*?)</script><!-- NMSK-ABBREV end -->', html, re.S)
        assert m, d
        tab = json.loads(m.group(1))["a"]
        assert tab == abbrev.build(pg.read_structs(html)), d
        c = committed()["pages"].get(d)
        if c:
            assert {k: v[:2] for k, v in tab.items()} == {k: v for k, v in c["map"].items()}, d
