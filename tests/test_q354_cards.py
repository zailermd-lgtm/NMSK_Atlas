"""Q354: name cards carry only their own record. Exact part-of links (no bone record on a gyrus, no muscle record on a bursa), a
sided nerve lists its own side, no raw id / triangle count / build-provenance note in card text, brain and middle-ear parts
classed by what they are, serratus posterior inferior T9-T12 (Mannan 2017 p. 408). The page patch is
scripts/zanatomy/patch_manifest_cards_q354.py (run by regen_template_only.py); the browser check is the QA card check rerun."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "scripts/zanatomy")]
import card_rules_q354 as R  # noqa: E402
import patch_manifest_cards_q354 as P  # noqa: E402

KEY = "window.__ANATOMY_MANIFEST__="
PAGES = {"base_m": REPO / "build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html",
         "base_f": REPO / "build/q309/viewer_base_female/atlas_viewer_base_female.html"}
BANNED = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")


# ---- the link rule itself
@pytest.mark.parametrize("child,sys_,pid,pname,cat", [
    ("Middle temporal gyrus", "cns", "temporal_l", "Temporal bone", "bone"),
    ("Lacrimal gland", "viscera", "lacrimal_l", "Lacrimal bone", "bone"),
    ("Greater palatine artery", "vessel", "palatine_r", "Palatine bone", "bone"),
    ("Subtendinous bursa of obturator internus", "bursa", "obturator_internus_r", "Obturator internus", "muscle"),
    ("Ilio-inguinal nerve", "nerve", "inguinal_ligament_r", "Inguinal ligament (Poupart's ligament)", "fascia"),
    ("Trochlea of superior oblique muscle", "muscle", "superior_oblique_l", "Superior oblique", "muscle"),
    ("Lateral patellar retinaculum", "joint", "patellar_ligament_l", "Patellar ligament (patellar tendon)", "ligament"),
    ("Node of arch of azygos vein", "lymph", "azygos_v", "Azygos vein", "vessel"),
])
def test_borrowed_links_are_refused(child, sys_, pid, pname, cat):
    assert not R.part_link_ok(child, sys_, pid, pname, cat)


@pytest.mark.parametrize("child,sys_,pid,pname,cat,comps", [
    ("Acromial part of deltoid muscle", "muscle", "deltoid_l", "Deltoid", "muscle", []),
    ("Iliacus muscle", "muscle", "iliopsoas_l", "Iliopsoas (iliacus + psoas major)", "muscle", []),
    ("Pubococcygeus muscle", "muscle", "levator_ani_l", "Levator ani", "muscle", ["levator_ani_l_pubococcygeus"]),
    ("Muscular branches of ulnar nerve", "nerve", "ulnar_n", "Ulnar nerve", "nerve", []),
    ("Calcaneal tendon", "insertion", "achilles_tendon_l", "Achilles (calcaneal) tendon", "tendon", []),
    ("Scaphoid bone", "bone", "carpals_l", "Carpal bones (8, proximal+distal row)", "bone", []),
    ("Central superior mesenteric nodes", "lymph", "superior_mesenteric_lymph_nodes", "Superior mesenteric lymph nodes", "vessel", []),
])
def test_true_pieces_keep_their_parent(child, sys_, pid, pname, cat, comps):
    assert R.part_link_ok(child, sys_, pid, pname, cat, comps)


def test_layer_and_names():
    assert R.layer_fix("Lat_Fis-ant-Vertical", "nerve") == "cns"
    assert R.layer_fix("Auditory tube", "nerve") == "viscera"
    assert R.layer_fix("Superior gluteal nerve (left)", "nerve") is None and R.layer_fix("Chorda tympani (left)", "nerve") is None
    assert R.display_name("zan_lat_fis_ant_vertical_r", "Lat_Fis-ant-Vertical") == "Anterior ascending ramus of lateral sulcus"
    assert R.display_name("zan_x_l", "Paracentral gyrus and sulcus*") == "Paracentral gyrus and sulcus"
    for stem, (name, src) in R.NAMES.items():           # every readable name is sourced (book + page) or declared mechanical
        assert src == "mechanical" or re.search(r"\bp\. \d+", src), stem


# ---- the serratus posterior inferior correction (Mannan 2017 p. 408)
NEW = ["thoracoabdominal_n_t9_intercostal_muscular", "thoracoabdominal_n_t10_intercostal_muscular",
       "thoracoabdominal_n_t11_intercostal_muscular", "subcostal_n"]


def _tree():
    out = {}
    for p in sorted((REPO / "data/nerves").glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if isinstance(e, dict) and "id" in e:
                out[e["id"]] = e
    return out


@pytest.mark.parametrize("s", ["l", "r"])
def test_serratus_posterior_inferior_record(s):
    r = json.loads((REPO / f"data/muscles/trunk/serratus_posterior_inferior_{s}.json").read_text(encoding="utf-8"))
    inn = r["innervation"]
    assert inn["nerve"] == NEW and inn["root_levels"] == "T9-T12" and inn["note"].startswith("Q354")
    assert "Mannan" in inn["source"] and "p. 408" in inn["source"] and "p. 408" in r["source"]
    assert all(c["innervation_branch_ids"] == NEW for c in r["functional_compartments"])
    assert not any(w in json.dumps(inn).lower() for w in BANNED)


def test_serratus_posterior_inferior_wired_both_ways():
    t = _tree()
    for i in range(1, 9):
        nid = f"intercostal_n_t{i}_muscular" if i <= 6 else f"thoracoabdominal_n_t{i}_intercostal_muscular"
        assert not any(x.startswith("serratus_posterior_inferior") for x in t[nid]["targets"]), nid
    for nid in NEW:
        assert {"serratus_posterior_inferior_r_main", "serratus_posterior_inferior_l_main"} <= set(t[nid]["targets"]), nid
    g = json.loads((REPO / "data/anatomy/innervation_groups_q342.json").read_text(encoding="utf-8"))
    assert g["muscles"]["serratus_posterior_inferior"]["nerves"] == NEW


# ---- the page manifest after the patch (in memory, never written)
@pytest.fixture(scope="module", params=sorted(PAGES))
def patched(request):
    f = PAGES[request.param]
    if not f.exists():
        pytest.skip(f"{f} not built")
    html = f.read_text(encoding="utf-8")
    i = html.index(KEY) + len(KEY)
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    P.patch_manifest(man, R.atlas_categories(), P._muscle_recs())
    return request.param, man


def test_no_borrowed_bone_record_on_a_non_bone(patched):
    key, man = patched
    cats = R.atlas_categories()
    bad = [m["id"] for m in man["meshes"] if (m.get("rec") or {}).get("part_of_id") and m["sys"] != "bone"
           and cats.get(m["rec"]["part_of_id"]) == "bone"]
    assert not bad, (key, bad[:5])
    bur = [m["id"] for m in man["meshes"] if m["sys"] == "bursa" and (m.get("rec") or {}).get("origin")]
    assert not bur, (key, bur[:5])
    by = {m["id"]: m for m in man["meshes"]}
    assert by["zan_subtendinous_bursa_of_obturator_internus_r"].get("rel") == "obturator_internus_r"
    assert "rec" not in by["zan_middle_temporal_gyrus_l"] or "part_of" not in by["zan_middle_temporal_gyrus_l"]["rec"]


def test_sided_nerve_lists_its_own_side_only(patched):
    key, man = patched
    bad = []
    for m in man["meshes"]:
        if m.get("side") not in ("l", "r"):
            continue
        other = {"l": "r", "r": "l"}[m["side"]]
        for k in ("targets", "supplies", "nerve"):
            if any(R.token_side(t) == other for t in (m.get("rec") or {}).get(k) or []):
                bad.append((m["id"], k))
    assert not bad, (key, bad[:5])
    sg = {m["id"]: m for m in man["meshes"]}["superior_gluteal_n_l"]["rec"]["targets"]
    assert sg and all("(left)" in t for t in sg)


def test_no_raw_id_tris_or_provenance_in_card_text(patched):
    key, man = patched
    names = {m["id"]: m["name"] for m in man["meshes"]}
    bad = {}
    for m in man["meshes"]:
        t = R.card_text(m.get("rec") or {}, names)
        h = R.raw_hits(t)
        if h or re.search(r"\btris\b", t) or "carried with the deformation of the bones" in t:
            bad[m["id"]] = h or t[:80]
    assert not bad, (key, len(bad), list(bad.items())[:4])
    raw = [m["id"] for m in man["meshes"] if re.search(r"[_*]|''|//|'$", m["name"])]
    assert not raw, (key, raw[:5])


def test_classes(patched):
    key, man = patched
    by = {m["id"]: m for m in man["meshes"]}
    for i in ("zan_lat_fis_ant_vertical_r", "zan_lat_fis_post_l", "zan_orbital_sulci_h_shaped_orbital_sulci_l", "zan_sulcus_interm_prim_jensen_l"):
        assert by[i]["sys"] == "cns", i
    assert by["zan_auditory_tube_l"]["sys"] == "viscera" and by["zan_auditory_tube_r"]["sys"] == "viscera"
    assert not [m["id"] for m in man["meshes"] if R.layer_fix(m["name"], m["sys"])]
    ins = by["lateral_rectus_r"]["rec"]["insertion"]
    assert "sclera" in ins and "ygomatic" not in ins
    spi = by["serratus_posterior_inferior_r"]["rec"]["nerve"]
    assert spi == ["T9 intercostal muscular branch", "T10 intercostal muscular branch", "T11 intercostal muscular branch", "Subcostal nerve (T12)"]


def test_patch_is_idempotent(patched):
    key, man = patched
    again = json.loads(json.dumps(man))
    ch = P.patch_manifest(again, R.atlas_categories(), P._muscle_recs())
    assert again == man and not any(v for k, v in ch.items() if k != "lists"), (key, {k: v[:3] for k, v in ch.items() if v})


# ---- the quick card and the regen wiring
def test_quickcard_source():
    js = (REPO / "viewer/quickcard/quickcard.js").read_text(encoding="utf-8")
    assert "CAP = 0.6" in js and "tidyDet" in js and "tris" in js            # the open card is capped; the triangle count goes
    assert 'key:"rel354"' in js and "qc-rellink" in js                       # Related: <muscle> as a link
    assert "None for this structure in this project's data." in js and '" \\u00b7 none"' in js
    low = js.lower() + (REPO / "viewer/quickcard/quickcard.css").read_text(encoding="utf-8").lower()
    assert not any(w in low for w in BANNED)


def test_regen_runs_the_patch_before_labels_and_after_q350():
    t = (REPO / "scripts/regen_template_only.py").read_text(encoding="utf-8")
    a, ab, q350 = t.index("patch_manifest_cards_q354.py\", str(dst)])"), t.index("make_abbrevs.py\", \"--inject\""), t.index("patch_manifest_nerves_q350.py\", str(dst)])")
    assert a < ab and t.count("patch_manifest_cards_q354.py\", str(dst)])") == 2 and t.rindex("patch_manifest_cards_q354.py\", str(dst)])") > q350


def test_new_files_carry_no_banned_words():
    for f in ("scripts/zanatomy/card_rules_q354.py", "scripts/zanatomy/patch_manifest_cards_q354.py"):
        low = (REPO / f).read_text(encoding="utf-8").lower()
        assert not any(w in low for w in BANNED), f
