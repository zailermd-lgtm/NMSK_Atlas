"""Q391: the muscles peel by the textbook layers of their own region, and can be hidden gently one by one.

Owner (translated from Hebrew, 2026-11-22): "The division into levels in one system does not necessarily match the
levels of another system. For the muscles, for example, it is a MUST to work by the known layers. Also allow gently
hiding muscle by muscle."

Static checks; the browser ones are scripts/anatomy/q391/verify_layers_q391.py (Q391_LAYERS_OK / FAIL).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TABLE = REPO / "data" / "anatomy" / "system_layers_q309.json"
Q309 = REPO / "viewer" / "q309"
ZAN = REPO / "viewer" / "zan_atlas.template.html"
OWN = REPO / "viewer" / "atlas_viewer.template.html"
PRIVATE = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic",
           "mrayl", "b-mode")


@pytest.fixture(scope="module")
def table():
    return json.loads(TABLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def mus(table):
    return [s for s in table["systems"] if s["key"] == "muscular"][0]


def _groups(mus):
    for r in mus["regions"]:
        for i, l in enumerate(r["layers"]):
            for g in l["groups"]:
                yield r, i, l, g


# ---------------------------------------------------------------- the table ---------------------------------------
def test_the_muscles_are_layered_by_region(mus):
    keys = [r["key"] for r in mus["regions"]]
    assert len(keys) == len(set(keys)) >= 25
    for must in ("back", "sole", "forearm_ant", "forearm_post", "gluteal", "leg_post", "thoraxwall", "abdomen",
                 "neck", "hand", "perineum", "face"):
        assert must in keys, must
    for r in mus["regions"]:
        assert r["label"] and r["he"] and r["layers"], r["key"]
        for l in r["layers"]:
            assert l["label"] and l["he"] and l["groups"], (r["key"], l["label"])


def test_the_textbook_layer_counts(mus):
    """the counts the books give: back 3 extrinsic + 4 intrinsic (Sontakke 2023 pp. 217-222), sole 4 (Mannan 2017
       pp. 281-291), forearm front 3 (Gray's Atlas pp. 397-399), pharynx 2 (Sontakke p. 309), suprahyoid 4 (p. 145)"""
    n = {r["key"]: len(r["layers"]) for r in mus["regions"]}
    assert n["back"] == 7 and n["sole"] == 4 and n["forearm_ant"] == 3 and n["forearm_post"] == 2
    assert n["pharynx"] == 2 and n["thoraxwall"] == 3 and n["abdomen"] == 3 and n["perineum"] == 3
    assert n["neck"] == 6          # platysma, SCM, then the four suprahyoid layers with the two infrahyoid ones beside 1 and 2


def test_every_group_is_cited_to_a_named_source_with_a_page(table, mus):
    keys = set(table["sources"])
    for r, i, l, g in _groups(mus):
        assert g["basis"] in ("literature", "convention"), (r["key"], i)
        # one or more "<source key> p(p). N (what the page says)" parts, joined by "; " before the next key
        parts = [p.strip() for p in re.split(r";\s+(?=(?:%s)\b)" % "|".join(map(re.escape, keys)), g["cite"]) if p.strip()]
        assert parts, (r["key"], i)
        for p in parts:
            k = p.split()[0]
            assert k in keys, (r["key"], i, p)
            assert re.search(r"\bpp?\. \d", p), (r["key"], i, p)        # a page, always
        if g["basis"] == "convention":
            assert g.get("note"), (r["key"], i)                       # a convention says why
    for k in ("sontakke2023", "mannan2017", "grays_atlas", "freilinger1987"):
        assert k in table["sources"], k
    assert "project" not in table["sources"]


def test_the_conventions_are_named_on_the_table(table, mus):
    c = [x for x in table["conventions"] if x.startswith("muscular (Q391)")]
    assert len(c) == 1 and "OUR CONVENTION" in c[0]
    conv = [g for _, _, _, g in _groups(mus) if g["basis"] == "convention"]
    assert 5 <= len(conv) <= 12, len(conv)                  # a handful, each named in the convention line


def test_every_regex_is_anchored_and_safe_in_both_languages(mus):
    pats = [g["re"] for _, _, _, g in _groups(mus)]
    for p in pats:
        assert p.startswith("^(?:") and "(?<" not in p, p
        re.compile(p, re.I)
    js = "const P = %s; P.forEach(p => new RegExp(p, 'i')); console.log(P.length);" % json.dumps(pats)
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and int(r.stdout.strip()) == len(pats), r.stderr[-800:]


def _first(mus, name):
    for r, i, l, g in _groups(mus):
        if re.search(g["re"], name, re.I):
            return r["key"], i + 1
    return None


@pytest.mark.parametrize("name,where", [
    ("Trapezius", ("back", 1)), ("Latissimus dorsi", ("back", 1)), ("Levator scapulae", ("back", 2)),
    ("Rhomboid major", ("back", 2)), ("Serratus posterior inferior", ("back", 3)), ("Splenius capitis", ("back", 4)),
    ("Iliocostalis", ("back", 5)), ("Longissimus capitis muscle", ("back", 5)), ("Multifidus", ("back", 6)),
    ("Semispinalis colli muscle", ("back", 6)), ("Interspinales", ("back", 7)), ("Rectus capitis posterior minor", ("back", 7)),
    ("Abductor hallucis", ("sole", 1)), ("Quadratus plantae", ("sole", 2)), ("Adductor hallucis", ("sole", 3)),
    ("Plantar interossei", ("sole", 4)), ("Dorsal interossei (foot)", ("sole", 4)),
    ("Palmaris longus muscle", ("forearm_ant", 1)), ("Flexor digitorum superficialis", ("forearm_ant", 2)),
    ("Flexor digitorum profundus", ("forearm_ant", 3)), ("Extensor digitorum", ("forearm_post", 1)),
    ("Extensor digitorum longus", ("leg_ant", 1)), ("Extensor digitorum brevis", ("foot_dors", 1)),
    ("Supinator", ("forearm_post", 2)), ("Gluteus maximus", ("gluteal", 1)), ("Gluteus medius", ("gluteal", 2)),
    ("Gluteus minimus", ("gluteal", 3)), ("Gastrocnemius", ("leg_post", 1)), ("Soleus", ("leg_post", 2)),
    ("Tibialis posterior muscle", ("leg_post", 4)), ("External oblique", ("abdomen", 1)),
    ("Transversus abdominis", ("abdomen", 3)), ("Platysma", ("neck", 1)), ("Sternocleidomastoid", ("neck", 2)),
    ("Mylohyoid", ("neck", 4)), ("Genioglossus", ("neck", 6)), ("Opponens digiti minimi", ("hand", 2)),
    ("Opponens digiti minimi (foot)", ("sole", 3)), ("Bulbospongiosus (CVH, both sides joined)", ("perineum", 1)),
    ("Levator ani", ("perineum", 3)), ("Innermost intercostal muscles", ("thoraxwall", 3)),
])
def test_known_layers_land_where_the_books_put_them(mus, name, where):
    assert _first(mus, name) == where


def test_no_muscle_name_on_the_base_pages_matches_two_groups(mus):
    """first match wins in the viewer; on the Base pages no name may even be ambiguous"""
    import sys
    sys.path.insert(0, str(REPO / "tests"))
    import test_q309 as T  # noqa
    M = T._build_dir()
    seen = 0
    for key in ("base_m", "base_f"):
        d = Path(M.page_dir(key))
        if not (d / "index.html").is_file():
            continue
        for r in T._rows(d):
            if r["cat"] not in mus["cats"]:
                continue
            hits = [(rg["key"], i) for rg, i, l, g in _groups(mus) if re.search(g["re"], r["name"] or "", re.I)]
            assert len(hits) == 1, (key, r["name"], hits)
            seen += 1
    if not seen:
        pytest.skip("no built Base page")


# ---------------------------------------------------------------- the module and the engine ------------------------
def test_the_module_is_spliced_into_both_templates_and_runs_inside_the_depth_control():
    s = (Q309 / "q309.js").read_text(encoding="utf-8")
    assert "NMSKMusHide.start(E" in s and "NMSKSysPeel.element().appendChild(NMSKMusHide.element())" in s
    assert s.count('G.addTo("systems"') == 2                    # no new top-level control
    assert "sa.add(NMSKMusHide.source())" in s
    for t in (ZAN, OWN):
        x = t.read_text(encoding="utf-8")
        assert x.count("var NMSKMusHide = (function()") == 1, t.name


def test_the_fade_is_short_smooth_and_through_the_engine():
    m = (Q309 / "mushide.js").read_text(encoding="utf-8")
    assert "var MS = 250" in m and "smoothstep" in m and "E.fade" in m
    assert 'register(' not in m                                 # it travels in Q309's one history provider
    assert "localStorage" not in m
    z = ZAN.read_text(encoding="utf-8")
    assert "var q391Fade = new Map();" in z and "q391Fade.forEach" in z
    assert z.count("&& (!q391Fade.size || q391F(e) === undefined)") == 3
    assert 'NMSKMusHide.put("");   /* Q391' in z
    r = subprocess.run(["python3", str(REPO / "scripts" / "anatomy" / "q391" / "patch_engines_q391.py"), "--check"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_card_offers_a_gentle_hide():
    m = (Q309 / "mushide.js").read_text(encoding="utf-8")
    assert 'Q.addon({key:"q391"' in m and 'id = "mh-card-hide"' in m.replace("b.id = ", 'id = ')


def test_the_history_string_never_uses_q309s_separator():
    m = (Q309 / "mushide.js").read_text(encoding="utf-8")
    get = m[m.index("get:function(){"):m.index("put:function(v){")]
    assert '";"' not in get and "'|'" not in get


def test_no_private_word_and_no_model_identifier_in_this_rounds_files():
    files = [Q309 / "mushide.js", Q309 / "sysmap.js", Q309 / "q309.js", Q309 / "q309.css", TABLE,
             REPO / "scripts" / "anatomy" / "q391" / "patch_engines_q391.py",
             REPO / "scripts" / "anatomy" / "q391" / "verify_layers_q391.py"]
    for f in files:
        t = f.read_text(encoding="utf-8").lower()
        for w in PRIVATE:
            assert w not in t, (f.name, w)
        assert not re.search(r"\b(?:claude|opus|sonnet|haiku|fable)\b", t), f.name
