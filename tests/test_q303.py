"""Q303: imaging that centres itself on what the user already chose, a four-pane view of one model, a custom
orientation ("facing me") with named saved views, and an emphasis of the nerves that reaches the small ones.

These are the static checks; the browser ones are scripts/anatomy/q303/verify_q303.py.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VIEWER = REPO / "viewer"
Q303 = VIEWER / "q303"
TEMPLATES = {"own": VIEWER / "atlas_viewer.template.html", "zan": VIEWER / "zan_atlas.template.html"}
MODULES = ["pca.js", "step.js", "px.js", "nervepass.js", "target.js", "autofocus.js", "fourup.js", "views.js",
           "nerves.js", "q303.js"]
GLUE = {"zan": REPO / "scripts" / "anatomy" / "q303" / "glue_zan.js",
        "own": REPO / "scripts" / "anatomy" / "q303" / "glue_own.js"}
CALIBRE = REPO / "data" / "anatomy" / "calibre.json"
NODE = "node"


@pytest.fixture(scope="module")
def tpl():
    return {k: v.read_text(encoding="utf-8") for k, v in TEMPLATES.items()}


@pytest.fixture(scope="module")
def cal():
    return json.loads(CALIBRE.read_text(encoding="utf-8"))


def node(script: str):
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def load(*names):
    """require the modules into one node context; they are plain IIFEs with module.exports"""
    out = []
    for n in names:
        out.append("const %s = require(%s);" % (n.split(".")[0].upper(), json.dumps(str(Q303 / n))))
    return "\n".join(out)


# ---------------------------------------------------------------- the modules exist and are spliced ---------------
def test_every_module_is_present():
    for n in MODULES + ["q303.css"]:
        p = Q303 / n
        assert p.is_file() and p.stat().st_size > 200, n


def test_both_templates_carry_every_module(tpl):
    for eng, t in tpl.items():
        assert t.count("<!-- Q303 html begin -->") == 1 and t.count("<!-- Q303 html end -->") == 1, eng
        for sym in ("NMSKPCA", "NMSKStep", "NMSKPx", "NMSKNervePass", "NMSKTarget", "NMSKAutoFocus",
                    "NMSKFourUp", "NMSKViews", "NMSKNerves", "NMSKQ303"):
            assert t.count("var %s = (function()" % sym) == 1, (eng, sym)
        assert "/* Q303 glue begin */" in t and "/* Q303 glue end */" in t, eng
        g = t[t.index("/* Q303 glue begin */"):t.index("/* Q303 glue end */")]
        assert "NMSKQ303.start({" in g, eng                     # the call, not the module's own doc comment
        for a in ("target:", "autofocus:", "fourup:", "views:", "nerves:"):
            assert a in g, (eng, a)


def test_the_earlier_rounds_survive(tpl):
    """Q303 builds on Q298's search, Q299's cut face, Q300's show-everything / model reset and Q301's control bar."""
    for eng, t in tpl.items():
        for sym in ("NMSKShowAll", "NMSKModelReset", "NMSKBoneRead", "NMSKGroups", "NMSKCombos", "NMSKQ301",
                    "NMSKHistory", "NMSKCapCore"):
            assert "var %s = (function()" % sym in t or "function %s(" % sym in t, (eng, sym)
        assert t.count('id="nmsk-q298"') == 1, eng
        assert t.count("<!-- Q300 html begin -->") == 1 and t.count("<!-- Q301 html begin -->") == 1, eng
        # Q303's block comes AFTER Q301's, so every module it builds on already exists when it runs
        assert t.index("<!-- Q301 html end -->") < t.index("<!-- Q303 html begin -->"), eng


def test_the_sync_script_lists_exactly_these_modules():
    s = (REPO / "scripts" / "sync_q303.py").read_text(encoding="utf-8")
    m = re.search(r"^JS = (\[[^\]]*\])", s, re.M)
    assert m, "the module list must be readable from the script"
    assert json.loads(m.group(1).replace("'", '"')) == MODULES


def test_the_view_group_is_joined_rather_than_a_new_top_level_button(tpl):
    """the project's UI rule, and the owner's own words: no new top-level buttons."""
    q = (Q303 / "q303.js").read_text(encoding="utf-8")
    assert 'G.addTo("view"' in q
    assert "addTo" in (VIEWER / "q301" / "groups.js").read_text(encoding="utf-8")
    for eng, t in tpl.items():
        assert 'addTo:function(key, m)' in t, eng
        assert 'addPair:function(r)' in t, eng


def test_the_nerve_shader_is_byte_identical_in_both_templates(tpl):
    """Q301 D3(7) refused to ship physics the two engines would compute differently. This pass is one GLSL string,
       compiled by the Z engine into its own program and by the own engine into a RawShaderMaterial."""
    needle = '"  gl_PointSize = uPt;\\n" +'
    for eng, t in tpl.items():
        assert needle in t, eng
    vs = (Q303 / "nervepass.js").read_text(encoding="utf-8")
    body = vs[vs.index('var VS ='):vs.index('var FS =')]
    for eng, t in tpl.items():
        assert body in t, eng
    assert "RawShaderMaterial" in GLUE["own"].read_text(encoding="utf-8")
    assert "createProgram" in GLUE["zan"].read_text(encoding="utf-8")


def test_the_width_formula_is_the_same_in_both_glues():
    """max(the step's minimum, the nerve's TRUE width in pixels) * dpr -- one function, called by both glues."""
    for eng, p in GLUE.items():
        s = p.read_text(encoding="utf-8")
        assert "NMSKNervePass.width(" in s, eng
    assert "Math.max(wmin_px || 0, truePx) * (dpr || 1)" in (Q303 / "nervepass.js").read_text(encoding="utf-8")


def test_every_module_parses(tmp_path):
    """Q301 lost a whole engine to a `//` comment spliced mid-line; nothing short of parsing catches that class."""
    for n in MODULES + [str(p) for p in GLUE.values()]:
        p = Q303 / n if not n.startswith("/") else Path(n)
        r = subprocess.run([NODE, "--check", str(p)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (n, r.stderr[-800:])


def test_the_hidden_attribute_is_guarded_in_the_css():
    """Q301: the `hidden` attribute is only display:none from the UA stylesheet and loses to any author display rule."""
    css = (Q303 / "q303.css").read_text(encoding="utf-8")
    m = re.search(r"^([^\n{]*)\{display:none !important\}", css, re.M)
    assert m, "every element toggled with `hidden` needs its own guard"
    guarded = {x.strip().split("[")[0] for x in m.group(1).split(",")}
    declared = set(re.findall(r"^\.(q3-[a-z]+|nv-box)\{", css, re.M))
    toggled = {".q3-grid", ".q3-note", ".nv-box", ".q3-views", ".q3-focus"}
    assert toggled <= guarded, toggled - guarded
    assert declared, "the stylesheet must declare the classes it guards"


def test_the_status_line_can_never_swallow_a_tap():
    """Q301 lost Undo twice to floating furniture. A transient status line is pointer-events:none, by rule."""
    css = (Q303 / "q303.css").read_text(encoding="utf-8")
    note = css[css.index(".q3-note{"):css.index(".q3-note-t")]
    assert "pointer-events:none" in note
    assert "pointer-events:auto" in css[css.index(".q3-note-x{"):css.index(".q3-note-x:hover")]


def test_the_four_pane_overlay_sits_under_q301s_bar():
    """Q301's bar is z-index 62, its sheet 61, its circled i 60, its drawer 70; Q300's chip bar is 2147482000."""
    css = (Q303 / "q303.css").read_text(encoding="utf-8")
    z = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\.(q3-grid|q3-note)\{[^}]*z-index:(\d+)", css, re.M)}
    assert z, "the overlay must declare its z-index"
    assert max(z.values()) < 60, z


# ---------------------------------------------------------------- the arithmetic -----------------------------------
def test_the_principal_axes_of_a_sheet_and_of_a_rod():
    """the rule "facing me" uses: look along the axis of LEAST spread. For a sheet that is its surface normal; for a
       rod it is across the shaft. Checked on shapes whose answer is known by construction."""
    out = node(load("pca.js") + r"""
      function sheet(){ const a = []; for (let i = 0; i < 40; i++) for (let j = 0; j < 40; j++) for (let k = 0; k < 2; k++)
        a.push((i - 20) * 4, (j - 20) * 9, (k - 0.5) * 0.8); return a; }
      function rod(){ const a = []; for (let i = 0; i < 800; i++){ const t = (i / 799 - 0.5) * 400, p = i * 2.399963;
        a.push(Math.cos(p) * 3, t, Math.sin(p) * 3); } return a; }
      const s = PCA.axes([sheet()]), r = PCA.axes([rod()]);
      console.log(JSON.stringify({sheet:{e3:s.e[2], lam:s.lam}, rod:{e1:r.e[0], e3:r.e[2], lam:r.lam}}));
    """)
    assert abs(abs(out["sheet"]["e3"][2]) - 1) < 1e-3, out["sheet"]
    assert out["sheet"]["lam"][2] < out["sheet"]["lam"][1] * 0.02
    assert abs(abs(out["rod"]["e1"][1]) - 1) < 1e-3, out["rod"]
    assert abs(out["rod"]["e3"][1]) < 1e-3, out["rod"]
    # the rule's own justification: looking along the minor axis is the larger silhouette, by sqrt(l1/l3)
    for k in ("sheet", "rod"):
        lam = out[k]["lam"]
        assert math.sqrt(lam[0] * lam[1]) > math.sqrt(lam[1] * lam[2]) * 2, (k, lam)


def test_one_undo_step_is_one_history_entry():
    """the defect this round's own harness found: publishing a "before" value and committing it produced TWO entries,
       so a second Undo press did nothing. NMSKStep keeps a counter in the history and the values beside it."""
    out = node(load("step.js") + r"""
      const H = {P:{}, hist:[], idx:-1};
      const api = {
        register:(k, p) => { H.P[k] = p; },
        commit:() => { const s = JSON.stringify(Object.keys(H.P).sort().map(k => [k, H.P[k].get()]));
                       if (H.idx >= 0 && H.hist[H.idx] === s) return false;
                       H.hist = H.hist.slice(0, H.idx + 1); H.hist.push(s); H.idx++; return true; },
        undo:() => { if (H.idx <= 0) return false; H.idx--; const e = JSON.parse(H.hist[H.idx]);
                     e.forEach(([k, v]) => H.P[k].set(v)); return true; },
        redo:() => { if (H.idx >= H.hist.length - 1) return false; H.idx++; const e = JSON.parse(H.hist[H.idx]);
                     e.forEach(([k, v]) => H.P[k].set(v)); return true; }
      };
      let cam = 1;
      const S = STEP.make(api, "cam", () => cam, (v) => { cam = v; });
      api.commit();
      const n0 = H.hist.length;
      S.step(() => { cam = 7; });
      const n1 = H.hist.length;
      api.undo(); const back = cam;
      api.redo(); const fwd = cam;
      S.step(() => { cam = 9; });
      api.undo(); const back2 = cam;
      console.log(JSON.stringify({entriesAdded:n1 - n0, back:back, fwd:fwd, back2:back2, len:H.hist.length}));
    """)
    assert out["entriesAdded"] == 1, out
    assert out["back"] == 1 and out["fwd"] == 7, out
    assert out["back2"] == 7, out


def test_two_modules_that_must_move_together_still_make_one_entry():
    """returning to a saved view puts back the camera (NMSKViews) AND the pane layout (NMSKFourUp); two nested steps
       would commit twice, which is the very defect NMSKStep exists to prevent."""
    out = node(load("step.js") + r"""
      const H = {P:{}, hist:[], idx:-1};
      const api = {
        register:(k, p) => { H.P[k] = p; },
        commit:() => { const s = JSON.stringify(Object.keys(H.P).sort().map(k => [k, H.P[k].get()]));
                       if (H.idx >= 0 && H.hist[H.idx] === s) return false;
                       H.hist = H.hist.slice(0, H.idx + 1); H.hist.push(s); H.idx++; return true; },
        undo:() => { if (H.idx <= 0) return false; H.idx--; JSON.parse(H.hist[H.idx]).forEach(([k, v]) => H.P[k].set(v)); return true; }
      };
      let cam = 1, lay = "one";
      const A = STEP.make(api, "cam", () => cam, (v) => { cam = v; });
      const B = STEP.make(api, "lay", () => lay, (v) => { lay = v; });
      api.commit();
      const n0 = H.hist.length;
      STEP.hold(() => { A.step(() => { cam = 7; }); B.step(() => { lay = "four"; }); });
      const n1 = H.hist.length;
      api.undo();
      console.log(JSON.stringify({added:n1 - n0, cam:cam, lay:lay, held:STEP.held()}));
    """)
    assert out["added"] == 1, out
    assert out["cam"] == 1 and out["lay"] == "one", out
    assert out["held"] is False, out


def test_the_pane_grid_tiles_the_canvas_exactly():
    """four panes, each exactly half the canvas in each direction -- which is WHY a pointer inside a pane maps to the
       full-canvas pixel it corresponds to with one linear scale, and the engines' picking needs no edit."""
    src = (Q303 / "fourup.js").read_text(encoding="utf-8")
    cells = re.findall(r"cell:\[(\d), ?(\d)\]", src)
    assert len(cells) == 4, cells
    assert sorted(cells) == [("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")], cells
    keys = re.findall(r'\{key:"(\w+)", label:"([^"]+)"', src)
    assert [k for k, _ in keys] == ["ant", "lat", "sup", "free"], keys
    assert [l for _, l in keys] == ["Anterior", "Lateral", "Superior", "3-D"], keys
    assert "Math.PI / 2" in src and "Math.PI / 2 - 0.035" in src


def test_the_frame_statistics_are_one_shared_function():
    """both engines read their own pixels and hand them to the SAME arithmetic, so the two measurements are comparable"""
    for eng, p in GLUE.items():
        s = p.read_text(encoding="utf-8")
        assert "NMSKPx.stats(" in s and "NMSKPx.quadrants(" in s, eng
        assert "readPixels" in s, eng
    out = node(load("px.js") + r"""
      const w = 8, h = 8, buf = new Uint8Array(w * h * 4);
      for (let i = 0; i < w * h; i++){ buf[i*4] = 10; buf[i*4+1] = 10; buf[i*4+2] = 10; buf[i*4+3] = 255; }
      // a block of the nerve's own chromaticity, bright
      for (let y = 2; y < 6; y++) for (let x = 2; x < 6; x++){
        const o = (y * w + x) * 4; buf[o] = 217; buf[o+1] = 181; buf[o+2] = 66; buf[o+3] = 255;
      }
      console.log(JSON.stringify(PX.stats(buf, w, h, 1, [0.85, 0.71, 0.26])));
    """)
    assert out["nerve"] == 16, out
    assert out["michelson"] > 0.3, out


def test_the_five_imaging_modes_and_the_target_order():
    src = (Q303 / "autofocus.js").read_text(encoding="utf-8")
    keys = re.findall(r'\{key:"(\w+)", label:"[^"]+", probe:', src)
    assert keys == ["style", "ct", "us", "cut", "xsec"], keys
    t = (Q303 / "target.js").read_text(encoding="utf-8")
    order = [m for m in re.findall(r'kind:"(marked|selected|search)"', t)]
    assert order == ["marked", "selected", "search"], order
    assert "return null;" in t.split('kind:"search"')[1], "with nothing chosen there must be no target at all"


def test_the_off_switch_defaults_to_on():
    src = (Q303 / "autofocus.js").read_text(encoding="utf-8")
    assert 'return v == null ? true : v === "1"' in src
    assert 'nmsk.q303.autofocus' in src


def test_the_nerve_steps_are_taps_and_not_a_slider():
    """the project's mobile rule, as Q300's bone strength and Q301's path length already are."""
    src = (Q303 / "nerves.js").read_text(encoding="utf-8")
    assert 'type="range"' not in src and "input" not in src.split("var STEP =")[1].split("];")[0]
    steps = re.findall(r'\{w:([\d.]+), a:([\d.]+), label:"(\w+)"\}', src)
    assert [s[2] for s in steps] == ["Off", "Clear", "Strong"], steps
    assert float(steps[0][0]) == 0 and float(steps[1][0]) > 1.5 and float(steps[2][0]) > float(steps[1][0])


def test_the_emphasis_never_claims_to_change_the_geometry():
    """the honesty rule: the drawn width is a DISPLAY AID and the recorded calibre stays the record."""
    src = (Q303 / "nerves.js").read_text(encoding="utf-8")
    assert "display aid" in src
    assert "nmsk-calibre" in src, "the diameters must come from the page's own measured table"
    for eng, p in GLUE.items():
        g = p.read_text(encoding="utf-8")
        assert "bufferSubData" not in g, eng          # nothing is ever written back into any mesh
        assert "drawArrays(gl.POINTS" in g or "THREE.Points(m.geometry" in g, eng   # the pass reads the mesh, never writes it


def test_the_compatibility_rows_this_round_adds():
    src = (Q303 / "q303.js").read_text(encoding="utf-8")
    rows = re.findall(r'\{a:"(\w+)", b:"(\w+)", ok:(true|false),', src)
    assert len(rows) == 7, rows
    byp = {(a, b): ok for a, b, ok in rows}
    assert byp[("fourup", "measure")] == "false"
    assert byp[("nerves", "imaging")] == "false"
    assert byp[("fourup", "imaging")] == "true"
    assert byp[("nerves", "cut")] == "true"
    # the incompatible rows must say what to use INSTEAD, on the screen, not in a tooltip
    nerve_row = src.split('{a:"nerves", b:"imaging"')[1][:400]
    assert "Colour" in nerve_row and "Marked" in nerve_row


# ---------------------------------------------------------------- the data the round rests on ----------------------
def test_every_page_has_nerve_calibres_to_drive_the_emphasis(cal):
    pages = {"viewer_m_hr", "viewer_f_hr", "viewer_zan_vhm", "viewer_zan_female", "viewer_base_female",
             "viewer_zan_atlas"}
    assert pages <= set(cal["pages"]), pages - set(cal["pages"])
    for p in sorted(pages):
        c = cal["pages"][p]["c"]
        n = {k: v for k, v in c.items() if v[0] == "n"}
        assert len(n) > 150, (p, len(n))
        d = sorted(v[1] for v in n.values())
        assert d[0] > 0, p
        # the round's premise: most nerves are a millimetre or two across, which is sub-pixel at a whole-body view
        assert d[len(d) // 2] <= 2.0, (p, d[len(d) // 2])


def test_every_page_now_carries_the_fibular_nerve(cal):
    """Q303 pinned the opposite of this: the two Imaging pages carried NO fibular / peroneal mesh, which is why the
    emphasis control said so on the screen. Q304 carried 18 of them onto each Imaging page from the Combined page of
    the same body (bone-point registration; see tests/test_q304.py), so the claim this test pins has moved -- what it
    still guards is that the page's own calibre table is where the answer comes from, on all six pages."""
    rx = re.compile(r"fibular|peroneal", re.I)
    own = {p: [k for k in cal["pages"][p]["c"] if rx.search(k)] for p in ("viewer_m_hr", "viewer_f_hr")}
    for p, got in own.items():
        assert len(got) == 18, (p, len(got))
        assert any(k.startswith("common_fibular_n") for k in got), p
    for p in ("viewer_zan_atlas", "viewer_zan_vhm", "viewer_zan_female", "viewer_base_female"):
        got = [k for k in cal["pages"][p]["c"] if rx.search(k)]
        assert len(got) >= 10, (p, len(got))


def test_the_major_nerve_probe_list_is_a_stated_convention():
    src = (Q303 / "nerves.js").read_text(encoding="utf-8")
    block = src[src.index("var MAJOR = ["):src.index("];", src.index("var MAJOR = ["))]
    names = re.findall(r'\["([^"]+)",', block)
    assert len(names) >= 20, names
    assert "fibular (peroneal)" in names and "sciatic" in names
    assert "conventional list" in src, "a rule-based list must say so"


def test_the_research_doc_exists_and_names_its_sources():
    p = REPO / "docs" / "research" / "Q303_views_and_autofocus.md"
    s = p.read_text(encoding="utf-8")
    assert len(s) > 4000
    for needle in ("Four-Up", "Align View to Active", "Jump slices", "Visible Body", "3D Slicer"):
        assert needle in s, needle
    assert "לא אומת" in s or "not verified" in s, "anything unverified must be marked as such"


def test_the_viewer_readme_documents_the_round():
    s = (REPO / "docs" / "VIEWER_README.md").read_text(encoding="utf-8")
    assert "Q303" in s
    for needle in ("Four views", "Facing me", "nerve"):
        assert needle in s, needle


# ---------------------------------------------------------------- the traps earlier rounds fell into ---------------
def test_no_q303_edit_appends_a_line_comment_mid_line():
    """Q301 lost a whole engine to `   // Q301` appended to a replacement spliced into the middle of a line that
       continued past it. Caught here at the source, for this round's own patcher."""
    import ast as A
    src = (REPO / "scripts" / "anatomy" / "q303" / "patch_engines_q303.py").read_text(encoding="utf-8")
    news = []
    for node in A.walk(A.parse(src)):
        if isinstance(node, A.Assign) and any(getattr(t, "id", "") in ("Z_EDITS", "OWN_EDITS") for t in node.targets):
            for el in node.value.elts:
                vals = [v for v in el.elts if isinstance(v, A.Constant) and isinstance(v.value, str)]
                if len(vals) >= 2:
                    news.append((vals[0].value, vals[1].value))
    assert len(news) == 7, len(news)
    for old, new in news:
        last = new.rstrip("\n").splitlines()[-1]
        if "//" in last and not last.rstrip().endswith("*/"):
            ol = old.rstrip("\n").splitlines()[-1].rstrip()
            assert ol.endswith((";", "{", "}", ")", "+", ",")), f"mid-line // comment after an anchor ending {ol[-40:]!r}"


def test_every_inline_script_of_every_built_page_parses():
    """nothing short of parsing catches a comment that swallowed the rest of a line (Q301's own finding)."""
    import glob
    import tempfile
    pages = sorted(glob.glob(str(REPO / "build" / "q303" / "viewer_*" / "index.html")))
    if not pages:
        pytest.skip("no build/q303 on disk")
    inline = re.compile(r'<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>(.*?)</script>', re.S)
    for f in pages:
        blocks = inline.findall(Path(f).read_text(encoding="utf-8"))
        assert len(blocks) >= 5, (f, len(blocks))
        for i, js in enumerate(blocks, 1):
            if not js.strip():
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as h:
                h.write(js); tmp = h.name
            r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True)
            assert r.returncode == 0, f"{Path(f).parent.name} inline script #{i}: {r.stderr[:400]}"


def test_the_sync_and_patch_scripts_report_themselves_up_to_date():
    import sys as S2
    for rel in ("scripts/sync_q303.py", "scripts/anatomy/q303/patch_engines_q303.py",
                "scripts/anatomy/q303/patch_q301_hooks_q303.py"):
        r = subprocess.run([S2.executable, str(REPO / rel), "--check"], capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (rel, r.stdout[-800:])


def test_the_harness_loads_the_real_modules_rather_than_copies():
    """a harness that carries its own copies drifts from what ships; this one is served from the repository root."""
    h = (REPO / "scripts" / "anatomy" / "q303" / "harness" / "host.html").read_text(encoding="utf-8")
    for n in MODULES:
        assert '/viewer/q303/%s"' % n in h, n
    for n in ("/viewer/q294/history.js", "/viewer/q300/showall.js", "/viewer/q301/groups.js"):
        assert n in h, n
    assert "nmsk-calibre" in h, "the nerve census must have a calibre table to read"


def test_the_sub_pixel_diagnosis_this_round_reports(cal):
    """The diagnosis, pinned so the documents cannot drift from the data: at a whole-body view the 3-D view holds the
       body's full height, which is about 1.9 mm per pixel, and at that scale most nerves are drawn UNDER ONE PIXEL
       wide. The counts quoted in docs/VIEWER_README.md, the hub, the research doc and PROJECT_STATE are these."""
    MMPX = 1.9
    # the two Imaging pages' figures moved in Q304, which added 71 and 64 lower-limb nerves to their calibre
    # tables (201 -> 272 and 244 -> 308). The diagnosis is unchanged and is in fact sharper: 175 of 272 and 184 of
    # 308 are still drawn under one pixel wide at this scale.
    exp = {"viewer_m_hr": (272, 175, 257), "viewer_f_hr": (308, 184, 268),
           "viewer_zan_atlas": (439, 357, 426), "viewer_base_female": (435, 350, 413),
           "viewer_zan_vhm": (440, 358, 428), "viewer_zan_female": (443, 373, 428)}
    for page, (n, sub, under) in exp.items():
        d = [v[1] for v in cal["pages"][page]["c"].values() if v[0] == "n"]
        assert len(d) == n, (page, len(d))
        assert sum(1 for x in d if x / MMPX < 1) == sub, (page, "sub-pixel")
        assert sum(1 for x in d if x / MMPX < 2.2) == under, (page, "under the Clear step")
    z = ["viewer_zan_atlas", "viewer_base_female", "viewer_zan_vhm", "viewer_zan_female"]
    frac = sum(exp[p][1] for p in z) / sum(exp[p][0] for p in z)
    assert 0.79 < frac < 0.83, frac          # "about 81 % on a Z page"


def test_the_two_performance_guards_the_real_pages_forced():
    """Both were found by watching a real page's CPU, not by reading the code, and both would otherwise keep the page
       redrawing for ever under software rendering. Pinned so they cannot quietly come back."""
    f = (Q303 / "fourup.js").read_text(encoding="utf-8")
    assert "lastSig" in f and "function sig(L)" in f, "the pane list must only be pushed when it has changed"
    assert "if (q === lastSig) return;" in f
    g = GLUE["own"].read_text(encoding="utf-8")
    assert "sigLast" in g and "if (sg === sigLast){ raf = requestAnimationFrame(tick); return; }" in g, \
        "the nerve pass must only redraw when the view it depends on has moved"


def test_the_frame_is_read_in_the_panes_own_order():
    """gl.readPixels is bottom-up, so a naive quadrant split reports the bottom row first and mislabels the panes."""
    out = node(load("px.js") + r"""
      const w = 16, h = 16, buf = new Uint8Array(w * h * 4);
      for (let i = 0; i < w * h; i++){ buf[i*4+3] = 255; }     // all background; the four corners set the field colour
      // paint a patch INSIDE the picture's top-left quadrant, clear of the corner samples:
      // readPixels is bottom-up, so the picture's top row is the buffer's LAST row
      for (let y = 10; y <= 13; y++) for (let x = 2; x <= 5; x++){
        const o = (y * w + x) * 4; buf[o] = 200; buf[o+1] = 30; buf[o+2] = 30; buf[o+3] = 255;
      }
      console.log(JSON.stringify(PX.quadrants(buf, w, h, 1)));
    """)
    assert out[0] > 0.2 and max(out[1:]) < 0.01, out        # the TOP-LEFT pane is reported first


def test_the_public_layer_never_names_the_private_tools(tpl):
    """The clinical slice tool and probe tool are the project's PRIVATE layer, and `tests/test_q226.py` /
       `tests/test_q228.py` pin that no public template mentions either by name. Q303 is the first public module that
       has to talk to them, so it finds them by SHAPE. Pinned here as well, next to the code that does it, because the
       first draft of this round shipped the names into both templates and only the suite caught it."""
    bad = ("ultrasound", "nmskimaging", "nmskultrasound", "acoustic", "b-mode", "hounsfield")
    for name in MODULES:
        low = (Q303 / name).read_text(encoding="utf-8").lower()
        for b in bad:
            assert b not in low, (name, b)
    for k, p in GLUE.items():
        low = p.read_text(encoding="utf-8").lower()
        for b in bad:
            assert b not in low, (k, b)
    a = (Q303 / "autofocus.js").read_text(encoding="utf-8")
    assert 'if (kind === "slice")' in a and 'typeof o.placeRay === "function"' in a and "tool:find," in a
    assert a.count('ks[i].indexOf("NMSK") !== 0') == 1               # the search is over the page's own NMSK globals
