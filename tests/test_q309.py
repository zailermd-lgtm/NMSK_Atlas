"""Q309: the systems as on/off buttons, and the depth peel with three scopes.

Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the
whole body, per system, and for the displayed systems only."

These are the static checks; the browser ones are scripts/anatomy/q309/verify_q309.py.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VIEWER = REPO / "viewer"
Q309 = VIEWER / "q309"
TEMPLATES = {"own": VIEWER / "atlas_viewer.template.html", "zan": VIEWER / "zan_atlas.template.html"}
MODULES = ["sysmap.js", "systoggle.js", "syspeel.js", "q309.js"]
TABLE = REPO / "data" / "anatomy" / "system_layers_q309.json"
NODE = "node"


@pytest.fixture(scope="module")
def tpl():
    return {k: v.read_text(encoding="utf-8") for k, v in TEMPLATES.items()}


@pytest.fixture(scope="module")
def table():
    return json.loads(TABLE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the modules and the splice ----------------------
def test_every_module_is_present():
    for n in MODULES + ["q309.css"]:
        p = Q309 / n
        assert p.is_file() and p.stat().st_size > 400, n


def test_both_templates_carry_every_module(tpl):
    for eng, t in tpl.items():
        assert t.count("<!-- Q309 html begin -->") == 1 and t.count("<!-- Q309 html end -->") == 1, eng
        for sym in ("NMSKSysMap", "NMSKSysToggle", "NMSKSysPeel", "NMSKQ309"):
            assert t.count("var %s = (function()" % sym) == 1, (eng, sym)


def test_the_block_comes_after_everything_it_builds_on(tpl):
    for eng, t in tpl.items():
        for m in ("<!-- Q294 html begin -->", "<!-- Q300 html begin -->", "<!-- Q301 html begin -->",
                  "<!-- Q303 html begin -->", "<!-- Q305 html begin -->", "<!-- Q306 html begin -->"):
            assert t.index(m) < t.index("<!-- Q309 html begin -->"), (eng, m)


def test_the_two_templates_carry_the_same_bytes(tpl):
    a, b = tpl["own"], tpl["zan"]
    ga = a[a.index("<!-- Q309 html begin -->"):a.index("<!-- Q309 html end -->")]
    gb = b[b.index("<!-- Q309 html begin -->"):b.index("<!-- Q309 html end -->")]
    assert ga == gb, "the Q309 block must be byte-identical in both engines"


def test_the_table_travels_with_the_page_and_is_the_same_bytes(tpl):
    for eng, t in tpl.items():
        assert t.count("<!-- NMSK-Q309-LAYERS begin -->") == 1, eng
        assert t.count('<script type="application/json" id="nmsk-q309-layers">') == 1, eng
    a, b = tpl["own"], tpl["zan"]
    ra = a[a.index("<!-- NMSK-Q309-LAYERS begin -->"):a.index("<!-- NMSK-Q309-LAYERS end -->")]
    rb = b[b.index("<!-- NMSK-Q309-LAYERS begin -->"):b.index("<!-- NMSK-Q309-LAYERS end -->")]
    assert ra == rb and len(ra) > 5000


def test_the_sync_script_is_up_to_date():
    r = subprocess.run(["python3", str(REPO / "scripts" / "sync_q309.py"), "--check"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_engine_patch_is_applied(tpl):
    r = subprocess.run(["python3", str(REPO / "scripts" / "anatomy" / "q309" / "patch_engines_q309.py"), "--check"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    for eng, t in tpl.items():
        assert t.count("/* Q309 glue begin */") == 1 and t.count("/* Q309 glue end */") == 1, eng
        assert "NMSKQ309.start({" in t, eng


def test_the_veto_is_its_own_set_and_is_read_in_the_visibility_predicate(tpl):
    """Not the per-layer `on` table (the rows, the presets and Q301's whole-body peel write that) and not
       `hidden` / `hideOverride` (the card's own hide, which Q300 counts and exits separately)."""
    z, o = tpl["zan"], tpl["own"]
    assert "var q309Off = new Set();" in z
    assert "if (q309Off.size && q309Off.has(o.id || o.name)) return false;" in z
    assert z.index("if (hidden.has(o)) return false;") < z.index("if (q309Off.size")
    assert "var q309Off = {};" in o
    assert "if (q309Off[s.id]) vis = false;" in o
    assert o.index("if (hideOverride[s.id]) vis = false;") < o.index("if (q309Off[s.id])")
    for eng, t in tpl.items():
        # the module writes it only through its single off(ids) entry point
        assert t.count("q309Off = new Set(ids || []);") + t.count("q309Off = {};") >= 1, eng


def test_the_engines_own_reset_also_puts_the_systems_back(tpl):
    assert 'NMSKSysToggle.put("")' in tpl["zan"]


# ---------------------------------------------------------------- the UI rules -------------------------------------
def test_the_controls_go_into_q301s_existing_layers_group_not_a_new_top_level_button():
    s = (Q309 / "q309.js").read_text(encoding="utf-8")
    assert s.count('G.addTo("layers"') == 2
    assert "NMSKGroups" in s and "document.body.appendChild" not in s


def test_the_depth_control_is_taps_and_not_a_slider():
    s = (Q309 / "syspeel.js").read_text(encoding="utf-8")
    assert 'type="range"' not in s and "input type" not in s
    assert s.count('createElement("button")') >= 4
    assert "aria-live" in s                      # the layer name and number are on the screen, not in a tooltip


def test_the_whole_body_scope_drives_q301s_module_and_does_not_reimplement_it():
    s = (Q309 / "syspeel.js").read_text(encoding="utf-8")
    assert "WB.set(i)" in s and "window.NMSKPeel" in s
    # no second copy of Q301's own order
    assert "skin" not in s and "insertion" not in s


def test_the_round_is_one_history_provider_so_a_change_is_one_undo_step():
    s = (Q309 / "q309.js").read_text(encoding="utf-8")
    assert s.count('hist.register("q309"') == 1
    assert "reset:function()" in s
    for n in ("systoggle.js", "syspeel.js"):
        assert 'register(' not in (Q309 / n).read_text(encoding="utf-8"), n


def test_both_paths_are_registered_with_q300s_show_everything():
    s = (Q309 / "q309.js").read_text(encoding="utf-8")
    assert "sa.add(NMSKSysToggle.source())" in s and "sa.add(NMSKSysPeel.source())" in s
    for n, key in (("systoggle.js", "q309sys"), ("syspeel.js", "q309peel")):
        src = (Q309 / n).read_text(encoding="utf-8")
        assert 'key:"%s"' % key in src, n
        for fn in ("label:function", "active:function", "clear:function", "drive:function"):
            assert fn in src, (n, fn)


def test_the_hidden_attribute_is_guarded_in_css():
    """Q301's lesson H2(ii): `hidden` is only display:none from the UA stylesheet, so every author display rule
       beats it -- which is how an info drawer once swallowed the Undo button. Every selector this file gives a
       `display` of its own must also appear in the `[hidden]` guard rule."""
    css = (Q309 / "q309.css").read_text(encoding="utf-8")
    guard = [ln for ln in css.splitlines() if "[hidden]" in ln and "display:none !important" in ln]
    assert len(guard) == 1, css
    guarded = set(re.findall(r"([.#][\w-]+)\[hidden\]", guard[0]))
    assert guarded, guard[0]
    display = set()
    for blk in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
        if "display:" not in blk.group(2) or blk.group(1).strip() == guard[0].split("{")[0].strip():
            continue
        for sel in blk.group(1).split(","):
            sel = sel.strip().split()[0] if sel.strip() else ""
            sel = sel.split("[")[0]                      # `.sp-all[hidden]` is the guard, not a selector to guard
            if sel.startswith((".", "#")):
                display.add(sel)
    assert display, css
    missing = sorted(s for s in display if s not in guarded and s not in {".sy-b", ".sp-b", ".sp-s", ".sy-l", ".sp-l"})
    assert not missing, missing


def test_the_q309_block_of_each_template_parses(tpl):
    """Q301's lesson H2(iii): a `//` comment spliced into the middle of a line killed a whole engine, and nothing
       short of parsing would have caught it. The whole built page is parsed by tests/test_q301.py; this parses
       exactly what this round splices, so a broken splice fails here first."""
    import tempfile
    for eng, t in tpl.items():
        blk = t[t.index("<!-- Q309 html begin -->"):t.index("<!-- Q309 html end -->")]
        m = re.search(r"<script>(.*)</script>", blk, re.S)
        assert m, eng
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(m.group(1))
            tmp = fh.name
        r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True, timeout=120)
        Path(tmp).unlink()
        assert r.returncode == 0, (eng, r.stderr[-1500:])


# ---------------------------------------------------------------- the table and its honesty -----------------------
def test_the_table_is_the_only_place_a_stratum_is_named(table):
    """nothing in the viewer retypes a system, a stratum or a count"""
    names = {s["key"] for s in table["systems"]}
    for n in MODULES:
        s = (Q309 / n).read_text(encoding="utf-8")
        for k in names:
            assert ('"%s"' % k) not in s, (n, k)


def test_every_system_names_its_categories_and_every_stratum_its_basis(table):
    assert table["schema"] == "nmsk.system_layers.v1" and table["round"] == "Q309"
    for s in table["systems"]:
        assert s["key"] and s["label"] and s["he"] and s["cats"]
        for t in s["strata"]:
            assert t["key"] and t["label"] and t["he"]
            assert t["basis"] in ("literature", "data", "mixed", "none"), (s["key"], t["key"])
            if t["basis"] != "none":
                assert t.get("cite"), (s["key"], t["key"])
            for c in t.get("cite", "").split(","):
                if c:
                    assert c in table["sources"], c


def test_the_systems_that_carry_no_sourced_depth_order_offer_no_strata(table):
    bare = {s["key"] for s in table["systems"] if not s["strata"]}
    assert bare == {"lymphatic", "visceral", "integument"}, bare
    assert any("lymphatic" in c for c in table["conventions"])


def test_the_conventions_are_written_down_and_name_themselves(table):
    assert len(table["conventions"]) >= 5
    assert any("OUR CONVENTION" in c for c in table["conventions"])
    assert "rule_peel_offered" in table and "half" in table["rule_peel_offered"]
    assert "he_note" in table and table["he_note"].strip()


def test_every_regex_in_the_table_compiles_in_python_and_in_javascript(table):
    pats = [t["re"] for s in table["systems"] for t in s["strata"] if t.get("re")]
    assert len(pats) >= 10
    for p in pats:
        re.compile(p, re.I)
        assert "(?<" not in p, p                    # no lookbehind: it is not safe in every browser we target
    js = "const P = %s; P.forEach(p => new RegExp(p, 'i')); console.log(JSON.stringify(P.length));" % json.dumps(pats)
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-1500:]
    assert json.loads(r.stdout.strip()) == len(pats)


def test_the_muscle_strata_come_from_the_projects_own_superficial_deep_group_pairs(table):
    """The claim in `sources.project`, checked against the data files it names rather than taken on trust."""
    g83 = json.loads((REPO / "data" / "anatomy" / "muscle_groups_q283.json").read_text(encoding="utf-8"))["groups"]
    g06 = json.loads((REPO / "data" / "anatomy" / "muscle_groups_q306.json").read_text(encoding="utf-8"))["groups"]
    ids83 = {g["id"] for g in g83}
    ids06 = {g["id"] for g in g06}
    assert {"gluteal", "deep_gluteal", "erector_spinae"} <= ids83
    assert {"leg_posterior_superficial", "leg_posterior_deep", "transversospinalis"} <= ids06
    mus = [s for s in table["systems"] if s["key"] == "muscular"][0]
    sup = [t for t in mus["strata"] if t["key"] == "sup"][0]["re"]
    deep = [t for t in mus["strata"] if t["key"] == "deep"][0]["re"]
    # the pairs the project's own groups settle must fall on the two sides they say
    for g in g83:
        if g["id"] == "gluteal":
            for m in g["members"]:
                assert re.search(sup, m.replace("_", " "), re.I), m
        if g["id"] == "deep_gluteal":
            for m in g["members"]:
                assert re.search(deep, m.replace("_", " "), re.I), m
    for g in g06:
        if g["id"] == "leg_posterior_superficial":
            for m in g["members"]:
                assert re.search(sup, m, re.I), m
        if g["id"] == "leg_posterior_deep":
            for m in g["members"]:
                assert re.search(deep, m, re.I), m
        if g["id"] == "transversospinalis":
            for m in g["members"]:
                assert re.search(deep, m, re.I), m


# ---------------------------------------------------------------- measured against the built pages ----------------
PAGES = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas",
         "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}


def _build_dir():
    import sys as _s
    _s.path.insert(0, str(REPO / "scripts" / "anatomy" / "q241"))
    import model as M  # noqa
    return M


def _rows(page_dir: Path):
    """the structures of a built page, read the way each engine reads them"""
    t = (page_dir / "index.html").read_text(encoding="utf-8", errors="replace")
    if 'id="bundle-json"' in t:
        i = t.index('id="bundle-json"')
        s = t.index(">", i) + 1
        b = json.loads(t[s:t.index("</script>", s)])
        src = [{"id": x["id"], "cat": x.get("cat"), "name": (x.get("rec") or {}).get("name") or x["id"]}
               for x in b["structures"]]
    else:
        k = t.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
        depth, j, instr, esc = 0, k, False, False
        while j < len(t):
            c = t[j]
            if instr:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    instr = False
            else:
                if c == '"':
                    instr = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
            j += 1
        mf = json.loads(t[k:j])
        src = [{"id": o.get("id") or o.get("name"), "cat": o.get("sys") or o.get("layer"),
                "name": o.get("name") or o.get("id")} for o in mf["meshes"]]
    seen, out = set(), []
    for r in src:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
    return out


def _assign(table, rows):
    """exactly what NMSKSysMap does, in Python, so the two cannot drift"""
    res = {}
    for sp in table["systems"]:
        mine = [r for r in rows if r["cat"] in sp["cats"]]
        if not mine:
            continue
        left, strata, sourced = list(mine), [], 0
        for stp in sp["strata"]:
            got, rest = [], []
            for r in left:
                ok = True
                if not stp.get("rest"):
                    if stp.get("cats") and r["cat"] not in stp["cats"]:
                        ok = False
                    elif stp.get("re") and not re.search(stp["re"], r["name"] or "", re.I):
                        ok = False
                (got if ok else rest).append(r)
            left = rest
            if not got:
                continue
            if stp.get("basis", "none") != "none":
                sourced += len(got)
            strata.append((stp["key"], len(got)))
        peel = len(strata) > 1 and sourced * 2 >= len(mine)
        res[sp["key"]] = {"n": len(mine), "strata": strata if peel else [], "sourced": sourced, "peel": peel}
    return res


@pytest.fixture(scope="module")
def measured(table):
    M = _build_dir()
    out = {}
    for key, name in PAGES.items():
        d = M.page_dir(key)
        if not (Path(d) / "index.html").is_file():
            pytest.skip("no built page for %s" % key)
        out[key] = _assign(table, _rows(Path(d)))
    return out


def test_every_structure_on_every_page_belongs_to_exactly_one_system(measured, table):
    M = _build_dir()
    for key in measured:
        rows = _rows(Path(M.page_dir(key)))
        cats = {}
        for s in table["systems"]:
            for c in s["cats"]:
                assert c not in cats, (c, s["key"], cats.get(c))
                cats[c] = s["key"]
        orphan = sorted({r["cat"] for r in rows} - set(cats))
        assert not orphan, (key, orphan)
        assert sum(v["n"] for v in measured[key].values()) == len(rows), key


def test_the_z_pages_carry_nine_systems_and_the_imaging_pages_seven(measured):
    for key in ("base_m", "base_f", "comb_m", "comb_f"):
        assert len(measured[key]) == 9, (key, sorted(measured[key]))
    for key in ("own_m", "own_f"):
        assert len(measured[key]) == 7, (key, sorted(measured[key]))
        assert "lymphatic" not in measured[key] and "integument" not in measured[key]


def test_the_systems_with_no_sourced_depth_order_get_no_peel_on_any_page(measured):
    for key, m in measured.items():
        for k in ("lymphatic", "visceral", "integument"):
            if k in m:
                assert not m[k]["peel"] and not m[k]["strata"], (key, k)


def test_the_imaging_pages_get_no_fascial_peel_and_the_z_pages_do(measured):
    """The honest half of the rule: 5 of the 6 fascial structures on an Imaging page are retinacula, an
       interosseous membrane and `Integumentum commune`, which the investing-fascia / septa classification does
       not reach, so that page is offered on / off only."""
    for key in ("own_m", "own_f"):
        assert not measured[key]["fascial"]["peel"], key
    for key in ("base_m", "base_f", "comb_m", "comb_f"):
        assert measured[key]["fascial"]["peel"], key


def test_the_measured_counts_the_round_reports(measured):
    """Pinned so a page that gains or loses structures cannot quietly change what the control claims.
       These are the counts on `build/q308`, the baseline this round builds on -- Q308 added the
       anterolateral and coracoacromial ligaments, the psoas minor and the LACN branches, which is why
       base_m's skeletal is 646 and not Q307's 642, its muscular 434 and not 432, and its cutaneous nerves
       40 and not 36. The psoas minor ships HIDDEN by default on the four Z pages (Q308 E), so it is counted
       here, is printed on the button, and is correctly NOT in the drawn count the browser check measures."""
    assert measured["base_m"]["muscular"]["n"] == 434
    assert dict(measured["base_m"]["muscular"]["strata"]) == {"sup": 160, "int": 98, "deep": 176}
    assert measured["base_m"]["skeletal"]["n"] == 646
    assert dict(measured["base_m"]["skeletal"]["strata"]) == {"capsule": 337, "cartilage": 53, "bone": 256}
    assert measured["base_m"]["nervous"]["n"] == 759
    assert dict(measured["base_m"]["nervous"]["strata"]) == {"cut": 40, "deep": 516, "cns": 203}
    assert measured["base_m"]["fascial"]["n"] == 175
    assert dict(measured["base_m"]["fascial"]["strata"]) == {"subcut": 16, "investing": 40, "septa": 13,
                                                             "deepbursa": 68, "rest": 38}
    assert measured["base_m"]["vascular"]["n"] == 661
    assert dict(measured["base_m"]["vascular"]["strata"]) == {"sup": 41, "deep": 620}
    assert measured["base_m"]["integument"]["n"] == 250
    assert measured["base_m"]["lymphatic"]["n"] == 162
    assert measured["base_m"]["visceral"]["n"] == 124
    assert measured["own_m"]["muscular"]["n"] == 374
    assert dict(measured["own_m"]["muscular"]["strata"]) == {"sup": 125, "int": 96, "deep": 152, "rest": 1}
    assert measured["own_m"]["skeletal"]["n"] == 202
    assert measured["own_m"]["nervous"]["n"] == 337
    assert dict(measured["own_m"]["nervous"]["strata"]) == {"cut": 36, "deep": 301}   # no `cns` on an Imaging page
    assert measured["own_m"]["fascial"]["n"] == 6 and not measured["own_m"]["fascial"]["peel"]
    for key in measured:
        assert measured[key]["adipose"]["n"] == 51, key          # Q295's 51, on all six pages (Q301 pinned it too)
        assert dict(measured[key]["adipose"]["strata"])["subcut"] == 17   # Q301's panniculus-adiposus finding
    # only 21 of 162 lymphatic structures carry a depth word -- the measurement behind "on / off only"
    for key in ("base_m", "base_f", "comb_m", "comb_f"):
        assert measured[key]["lymphatic"]["n"] == 162 and not measured[key]["lymphatic"]["peel"], key


def test_the_muscle_strata_cover_at_least_95_percent_of_every_pages_muscles(measured):
    for key, m in measured.items():
        d = dict(m["muscular"]["strata"])
        rest = d.get("rest", 0)
        assert m["muscular"]["n"] - rest >= 0.95 * m["muscular"]["n"], (key, d)
