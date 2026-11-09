"""Q301: one control bar with undo / redo, groups that unfold, radiographic render styles computed from the project's
own tissue table, a depth peel, fat off by default, and a compatibility matrix that is stated rather than implied.

These are the static checks; the browser ones are scripts/anatomy/q301/verify_q301.py.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VIEWER = REPO / "viewer"
Q301 = VIEWER / "q301"
TEMPLATES = {"own": VIEWER / "atlas_viewer.template.html", "zan": VIEWER / "zan_atlas.template.html"}
MODULES = ["tissue.js", "combos.js", "info.js", "render.js", "peel.js", "fat.js", "groups.js", "q301.js"]
GLUE = {"zan": REPO / "scripts" / "anatomy" / "q301" / "glue_zan.js",
        "own": REPO / "scripts" / "anatomy" / "q301" / "glue_own.js"}
TISSUES = REPO / "clinical" / "data" / "imaging_tissues.json"
NODE = "node"


@pytest.fixture(scope="module")
def tissue():
    return json.loads(TISSUES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tpl():
    return {k: v.read_text(encoding="utf-8") for k, v in TEMPLATES.items()}


# ---------------------------------------------------------------- the modules exist and are spliced ---------------
def test_every_module_is_present():
    for n in MODULES + ["q301.css"]:
        p = Q301 / n
        assert p.is_file() and p.stat().st_size > 200, n


def test_both_templates_carry_every_module(tpl):
    for eng, t in tpl.items():
        assert t.count("<!-- Q301 html begin -->") == 1 and t.count("<!-- Q301 html end -->") == 1, eng
        for sym in ("NMSKTissue", "NMSKCombos", "NMSKInfo", "NMSKRenderStyle", "NMSKPeel", "NMSKFat",
                    "NMSKGroups", "NMSKQ301"):
            assert f"var {sym} = (function()" in t, (eng, sym)
        assert "/* Q301 glue begin */" in t and "/* Q301 glue end */" in t, eng
        assert "NMSKQ301.start({" in t, eng


def test_the_q300_block_and_the_earlier_rounds_survive(tpl):
    """Q301 builds on Q300 and must not displace it, nor Q298's search block, nor Q299's cut face."""
    for eng, t in tpl.items():
        for sym in ("NMSKShowAll", "NMSKModelReset", "NMSKBoneRead"):
            assert f"var {sym} = (function()" in t, (eng, sym)
        assert t.count("<!-- Q300 html begin -->") == 1, eng
        assert "NMSKQ298" in t and "NMSKSearchCore" in t, eng
        assert "bandFrac" in t and "NMSKCapCore" in t, eng
        # the Q301 block comes AFTER the Q300 one, so NMSKShowAll and NMSKModelReset already exist
        assert t.index("<!-- Q301 html begin -->") > t.index("<!-- Q300 html end -->"), eng


def test_sync_script_reports_up_to_date():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_q301.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_engine_patcher_reports_up_to_date():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "anatomy" / "q301" / "patch_engines_q301.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_model_identifier_anywhere_new():
    bad = re.compile(r"\b(claude[-\s]?(opus|sonnet|haiku)|gpt-[0-9]|gemini-[0-9])", re.I)
    for p in list(Q301.glob("*")) + list(GLUE.values()) + [REPO / "scripts" / "sync_q301.py",
                                                           REPO / "scripts" / "anatomy" / "q301" / "patch_engines_q301.py",
                                                           REPO / "scripts" / "anatomy" / "q301" / "verify_q301.py",
                                                           REPO / "docs" / "research" / "Q301_controls_and_render_styles.md"]:
        if p.is_file():
            assert not bad.search(p.read_text(encoding="utf-8")), p.name


# ---------------------------------------------------------------- item 5: the render styles ----------------------
def test_the_tissue_reference_comes_from_the_private_layer_not_from_the_public_one():
    """The styles read the real numbers at run time. WHERE from matters: by the Q226 boundary the public viewer
       templates may hold no tissue number, no table file name and no sequence name of their own
       (tests/test_q226.py::test_public_templates_carry_only_the_generic_hook), so the private clinical layer hands the
       reference over on the generic global the page is allowed to know. This round added those two services; before
       it, Q301 fetched the same 92 KB file a second time and named it in the public layer, which broke the boundary."""
    assert TISSUES.is_file()
    tool = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
    assert "tissues: function ()" in tool, "the private layer must expose the loaded reference"
    assert "mskSequences:" in tool, "and which three of its sequences are the MSK set"
    assert "chained.tissues = sh.tissues" in tool and "chained.mskSequences = sh.mskSequences" in tool, \
        "both must reach the generic window.NMSKClinical the public page already uses"
    ts = (Q301 / "tissue.js").read_text(encoding="utf-8")
    assert "window.NMSKClinical" in ts and "cl.tissues()" in ts, "the public module must only ask"
    assert "fetch(" not in ts, "and must not fetch the reference itself"
    for eng, t in TEMPLATES.items():
        low = t.read_text(encoding="utf-8").lower()
        for banned in ("hounsfield", "t1_se", "imaging_tissues", "tissue table"):
            assert banned not in low, (eng, banned)


def test_no_tissue_number_is_retyped_in_the_viewer():
    """every HU and every T1 / T2 must come from the data file -- a copy in the viewer is a copy that can rot"""
    src = "\n".join((Q301 / n).read_text(encoding="utf-8") for n in MODULES)
    j = json.loads(TISSUES.read_text(encoding="utf-8"))
    for c in j["classes"]:
        hu = (c.get("ct") or {}).get("hu")
        if hu is None or abs(hu) < 150:          # a small integer is too common to be evidence either way
            continue
        # a digit run, so "100" inside the "/ 1000" of the HU definition is not mistaken for the cartilage value
        assert not re.search(r"(?<![\d.])" + re.escape(str(hu)) + r"(?![\d.])", src), (c["key"], hu)


def test_the_js_class_mapper_agrees_with_the_data_files_own_rules(tissue):
    """the mapper walks mapping_rules; these are the answers the rules themselves give"""
    expect = {("bone", "femur_l", "Femur"): "bone_cortical",
              ("muscle", "rectus_femoris_r", "Rectus femoris"): "muscle",
              ("skin", "skin_trunk", "Skin"): "skin",
              ("nerve", "sciatic_n_r", "Sciatic nerve"): "nerve",
              ("fat", "subcut_fat_thigh_l", "Subcutaneous fat"): "fat",
              ("fat", "soft_unlabelled_thigh", "Fat and unlabelled soft tissue"): "soft_unassigned",
              ("cartilage", "meniscus_med_l", "Medial meniscus"): "fibrocartilage",
              ("lymph", "node_ax_l", "Axillary lymph node"): "lymph_node"}
    script = (Q301 / "tissue.js").read_text(encoding="utf-8") + """
      const T = NMSKTissue; T.adopt(JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8')));
      const q = JSON.parse(process.argv[2]);
      console.log(JSON.stringify(q.map(a => T.classOf(a[0], a[1], a[2]))));
    """
    q = [list(k) for k in expect]
    r = subprocess.run([NODE, "-e", script, str(TISSUES), json.dumps(q)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert got == list(expect.values()), dict(zip([tuple(x) for x in q], got))


def _ct(j, key, win="msk"):
    C = {c["key"]: c for c in j["classes"]}
    W = {w["key"]: w for w in j["ct_windows"]}[win]
    hu = C[key]["ct"]["hu"]
    return max(0.0, min(1.0, (hu - (W["level"] - W["width"] / 2)) / W["width"]))


def _se(j, key, seq):
    C = {c["key"]: c for c in j["classes"]}
    S = {s["key"]: s for s in j["mr_sequences"]}[seq]
    res = j["mr_global"]["fat_suppression_residual"]
    tot = 0.0
    for p in C[key]["mri"]["pools"]:
        f = p["frac"]
        if p.get("fat") and S.get("fatsat"):
            f *= res
        tot += f * p["pd"] * (1 - math.exp(-S["tr"] / p["t1"])) * math.exp(-S["te"] / p["t2"])
    return tot


def test_the_ct_style_puts_the_tissues_where_a_ct_puts_them(tissue):
    assert _ct(tissue, "bone_cortical") == 1.0
    assert _ct(tissue, "bone_cortical") > _ct(tissue, "bone_cancellous") > _ct(tissue, "muscle") > _ct(tissue, "fat")
    assert _ct(tissue, "lung") < _ct(tissue, "fat")
    assert _ct(tissue, "tooth") >= _ct(tissue, "bone_cortical")


def test_the_mri_style_puts_the_tissues_where_each_sequence_puts_them(tissue):
    # T1: fat is the bright one, free fluid is dark, cortical bone is signal-free
    assert _se(tissue, "fat", "t1_se") > _se(tissue, "muscle", "t1_se") > _se(tissue, "fluid_free", "t1_se")
    assert _se(tissue, "fat", "t1_se") == max(_se(tissue, k, "t1_se") for k in
                                              ("fat", "muscle", "fluid_free", "bone_cortical", "cartilage", "nerve"))
    # T2: free fluid is the bright one, muscle and tendon are dark
    assert _se(tissue, "fluid_free", "t2_se") > _se(tissue, "muscle", "t2_se")
    assert _se(tissue, "fluid_free", "t2_se") > _se(tissue, "fat", "t2_se")
    assert _se(tissue, "tendon_ligament", "t2_se") < _se(tissue, "muscle", "t2_se")
    # PD fat-suppressed: the fat pool is really suppressed
    assert _se(tissue, "fat", "pd_fs") < _se(tissue, "fat", "pd_se") * 0.2
    assert _se(tissue, "fluid_free", "pd_fs") > _se(tissue, "fat", "pd_fs")
    assert _se(tissue, "bone_cortical", "t1_se") < 0.01


def test_the_xray_style_uses_the_hounsfield_definition_and_nothing_else(tissue):
    C = {c["key"]: c for c in tissue["classes"]}
    src = (Q301 / "tissue.js").read_text(encoding="utf-8")
    assert "1 + hu(cls) / 1000" in src.replace("1 + hu(cls)/1000", "1 + hu(cls) / 1000")
    mu = lambda k: 1 + C[k]["ct"]["hu"] / 1000
    assert mu("bone_cortical") > mu("muscle") > mu("fat") > mu("lung")
    assert mu("bone_cortical") / mu("fat") > 2.0            # the skeleton separates on its own in a DRR
    # and the DRR is Beer-Lambert: alpha = 1 - exp(-mu d), so the product over crossings is exp(-sum mu d).
    # Q317: mu reaches it through xrMu(), the step's tissue window -- the real mu still feeds it, unaltered.
    r = (Q301 / "render.js").read_text(encoding="utf-8")
    assert "1 - Math.exp(-xrMu(T.mu(" in r
    assert "function xrMu(mu){" in r
    for eng, t in TEMPLATES.items():
        s = t.read_text(encoding="utf-8")
        if eng == "zan":
            assert "clamp(1.0-exp(-uMu*uD0)" in s
        else:
            assert "THREE.DoubleSide" in s


def test_the_xray_path_length_is_a_measured_choice_and_is_labelled_as_ours():
    """d0 is the one number in the X-ray that is not physics; it must be a measured choice, not a guess, and must say so"""
    r = (Q301 / "render.js").read_text(encoding="utf-8")
    assert "var D0 = [0.05, 0.10, 0.20];" in r
    # Q317: d0 is no longer what the three taps choose -- it is the exposure, fixed per engine from that same
    # measurement (baseD0, set from xrayStep below). The three taps choose the tissue window instead.
    assert "baseD0 = Math.max(0, Math.min(D0.length - 1, opt.xrayStep | 0))" in r
    assert "D0[baseD0] || D0[1]" in r
    assert 'XW_W = ["Soft tissue", "Combined", "Bone"]' in r        # still three taps, not a slider
    low = r.lower()
    assert "chosen by measuring" in low and "convention" in low
    # and the two engines start at different steps, each with its reason beside its own call
    for eng, p in GLUE.items():
        g = p.read_text(encoding="utf-8")
        assert "xrayStep:" in g and "by measurement" in g.lower() or "measured" in g.lower(), eng
    assert "xrayStep:0" in GLUE["zan"].read_text(encoding="utf-8")   # 3,252 meshes: the same path length burns out
    assert "xrayStep:1" in GLUE["own"].read_text(encoding="utf-8")   # ~950 meshes: the contrast peaks here


def test_the_xray_tissue_window_is_ours_and_actually_separates_the_tissues(tissue):
    """Q317, owner: "there are films where you see only bone, others soft tissue, or a combination".

    The window is the one thing here that is not physics, so it must say so -- and it must do the job: raw mu
    separates cortical bone from muscle by only ~2x per shell, which is why every tissue read as one fog.
    """
    r = (Q301 / "render.js").read_text(encoding="utf-8")
    m = re.search(r"var XW = \[(.+?)\];", r)
    assert m, "the window table must be a literal, so this test reads the shipped numbers"
    XW = [[float(x) for x in g.split(",")] for g in re.findall(r"\[([^\]]+)\]", m.group(1))]
    assert len(XW) == 3 and all(len(w) == 3 for w in XW)
    # labelled as ours, in the same breath as the real definition it sits on top of
    low = r.lower()
    assert "our display convention" in low and "not a measurement" in low

    C = {c["key"]: c for c in tissue["classes"]}
    mu = lambda k: max(0.02, 1 + C[k]["ct"]["hu"] / 1000)
    win = lambda k, w: max(0.0, (mu(k) - w[0]) / (w[1] - w[0])) * w[2]
    soft, comb, bone = XW

    # Bone: the soft tissue is gone, and the trabecular bone is NOT (a bone film still shows it)
    for k in ("fat", "muscle", "tendon_ligament", "cartilage", "nerve", "blood_artery"):
        assert win(k, bone) == 0.0, k
    assert win("bone_cancellous", bone) > 0.0
    assert win("bone_cortical", bone) > win("bone_cancellous", bone) * 5

    # Soft tissue: the soft tissues separate from each other, in the order their attenuation puts them
    assert win("fat", soft) < win("muscle", soft) < win("tendon_ligament", soft) < win("cartilage", soft)
    assert win("bone_cortical", soft) > win("cartilage", soft) * 3        # and bone burns out, as on such a film

    # Combined: both, and far better separated than the raw mu the DRR used to take straight
    alpha = lambda v, d0: min(0.995, max(0.004, 1 - math.exp(-v * d0)))
    for d0 in (0.05, 0.10):                                              # both engines' exposures
        raw = alpha(mu("bone_cortical"), d0) / alpha(mu("muscle"), d0)
        got = alpha(win("bone_cortical", comb), d0) / alpha(win("muscle", comb), d0)
        assert raw < 2.5, "if raw mu ever separates well on its own, this window is no longer needed"
        assert got > raw * 2, (d0, raw, got)
        assert alpha(win("muscle", comb), d0) > 0.02, "the soft tissue must still be visible in Combined"


def test_the_grey_dominates_the_shading_in_ct_and_mri():
    """the grey IS the datum in CT and MRI; a diffuse term multiplying it would mean the picture is not what the table says"""
    r = (Q301 / "render.js").read_text(encoding="utf-8")
    assert "var FLATTEN = 0.6;" in r and "flatten:FLATTEN" in r
    z = TEMPLATES["zan"].read_text(encoding="utf-8")
    assert "uniform float uFlat" in z and "mix(0.34+d*0.74+f,1.0,uFlat)" in z
    o = TEMPLATES["own"].read_text(encoding="utf-8")
    assert "q301spec.flatten == null ? 0.6" in o
    # and the DRR has no shading at all: a radiograph has no surfaces
    assert '"xray", flat:true' in r.replace("mode:", "")


def test_the_three_styles_really_differ_per_class(tissue):
    """if two styles ranked the tissues the same way, switching between them would be decoration"""
    ks = ["fat", "muscle", "bone_cortical", "fluid_free", "tendon_ligament", "cartilage", "nerve", "marrow_yellow"]
    rank = {
        "ct": sorted(ks, key=lambda k: _ct(tissue, k)),
        "t1": sorted(ks, key=lambda k: _se(tissue, k, "t1_se")),
        "t2": sorted(ks, key=lambda k: _se(tissue, k, "t2_se")),
        "pdfs": sorted(ks, key=lambda k: _se(tissue, k, "pd_fs")),
    }
    seen = {}
    for name, r in rank.items():
        key = tuple(r)
        assert key not in seen, (name, seen.get(key))
        seen[key] = name


def test_every_class_the_styles_use_carries_its_own_honesty_flag(tissue):
    allowed = {"verified", "derived", "secondary_checked", "assumption", "recalled_unverified"}
    for c in tissue["classes"]:
        if c.get("ct"):
            assert c["ct"].get("status") in allowed, c["key"]
        if c.get("mri"):
            assert c["mri"].get("status") in allowed, c["key"]


def test_the_info_panel_states_what_is_convention_rather_than_measured():
    q = (Q301 / "q301.js").read_text(encoding="utf-8")
    for must in ("convention", "attenuation unit", "1.5 T", "no patient image", "simulation"):
        assert must.lower() in q.lower(), must
    # the MSK window is the file's own declared convention and the panel must pass that on
    assert "ct_windows" in (Q301 / "tissue.js").read_text(encoding="utf-8")
    j = json.loads(TISSUES.read_text(encoding="utf-8"))
    msk = [w for w in j["ct_windows"] if w["key"] == "msk"][0]
    assert "not from a citation" in msk["note"]


# ---------------------------------------------------------------- item 4: the compatibility matrix ---------------
def _matrix():
    src = (Q301 / "combos.js").read_text(encoding="utf-8")
    rows = re.findall(r'\{a:"(\w+)",\s*b:"(\w+)",\s*ok:(true|false|"over"),(?:\s*over:"\w+",)?\s*\n?\s*why:"((?:[^"\\]|\\.)*)"\}', src)
    assert rows, "the matrix did not parse"
    return [{"a": a, "b": b, "ok": True if ok == "true" else ("over" if ok == '"over"' else False), "why": w}
            for a, b, ok, w in rows]


def test_the_matrix_is_complete_and_every_row_has_a_reason():
    m = _matrix()
    assert len(m) >= 12
    for r in m:
        assert r["a"] != r["b"]
        assert len(r["why"]) > 20, r
        if r["ok"] is not True:
            assert r["why"][0].isupper()
    seen = set()
    for r in m:
        k = tuple(sorted((r["a"], r["b"])))
        assert k not in seen, k
        seen.add(k)


def test_the_owners_own_example_is_in_the_matrix_as_combinable():
    m = {tuple(sorted((r["a"], r["b"]))): r for r in _matrix()}
    cut_img = m[("cut", "imaging")]
    assert cut_img["ok"] is True and "cut face" in cut_img["why"].lower()


def test_every_key_the_matrix_names_is_really_probed_by_both_engines():
    m = _matrix()
    keys = {r["a"] for r in m} | {r["b"] for r in m}
    for eng, p in GLUE.items():
        probed = set(re.findall(r'\{key:"(\w+)",\s*label:', p.read_text(encoding="utf-8")))
        missing = keys - probed
        # a key may legitimately be absent from one engine (spin only exists on the Z pages)
        assert missing <= {"spin"}, (eng, sorted(missing))


def test_incompatible_rows_are_shown_disabled_with_the_reason_on_the_screen():
    g = (Q301 / "groups.js").read_text(encoding="utf-8")
    assert 'tgt.setAttribute("aria-disabled", "true")' in g and "tgt.disabled = true" in g
    assert "qg-why" in g and "m._why.hidden" in g
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    assert ".qg-why-off" in css and ".qg-off" in css


# ---------------------------------------------------------------- items 1 and 2: the control and the groups ------
def test_undo_redo_and_both_resets_are_in_the_bar_with_words():
    g = (Q301 / "groups.js").read_text(encoding="utf-8")
    for want in ('"q301-undo":"Undo"', '"q301-redo":"Redo"', '"q301-reset":"Module"', '"q301-mr-model":"Model"'):
        assert want in g, want
    assert 'hist.mountInto(hRow, "qg-h", "q301-")' in g
    assert "modelreset.mountInto(hRow" in g
    # and they are NOT inside a group that can be folded away
    assert "hRow" in g and 'bar.appendChild(hRow)' in g


def test_the_old_floating_group_is_not_shown_twice():
    """undo / redo / module reset are in the bar now, so Q294's floating copy must not be on the screen as well"""
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    assert re.search(r"body\.q301-on\s+#hist-bar\s*\{[^}]*display:\s*none", css)
    assert 'document.body.classList.add("q301-on")' in (Q301 / "groups.js").read_text(encoding="utf-8")


def test_the_groups_are_the_families_the_owner_named():
    q = (Q301 / "q301.js").read_text(encoding="utf-8")
    # Q318 renamed them to the words the owner used, and promoted Pose and Needle out of the entries
    # they were buried in. The keys are unchanged where another module adds to them by key.
    for key, label in (("mark", "Search"), ("systems", "Systems"), ("imaging", "Imaging"), ("cut", "Dissection"),
                       ("pose", "Pose"), ("measure", "Measure"), ("needle", "Needle"),
                       ("view", "Navigate"), ("learn", "Learn")):
        assert f'key:"{key}", label:"{label}"' in q, key
    # imaging really holds the radiographic styles (x-ray / CT / MRI) and the mode button.
    # Q318: the LEGACY btn-xray left this entry -- it was a transparency preset standing beside the
    # real radiographic styles, and the bar had to carry a note explaining it was not a radiograph.
    assert "rs-box" in q and "t-mode" in q
    assert "btn-xray" not in q, "the old transparency preset does not belong beside the real styles"


def test_a_group_adopts_the_real_buttons_rather_than_copying_them():
    g = (Q301 / "groups.js").read_text(encoding="utf-8")
    assert "row.appendChild(e); got++;" in g                 # the node is MOVED
    assert "document.getElementById(id)" in g
    assert "q301-b" in g


def test_only_one_group_is_open_at_a_time():
    g = (Q301 / "groups.js").read_text(encoding="utf-8")
    assert "if (cur === key){ closeSheet(); return false; }" in g
    assert "sBody.innerHTML = \"\";" in g


def test_the_bar_steps_aside_for_a_clinical_workspace_mode():
    """Q272's modes hide the anatomy chrome and bring their own bar; ours must go with the rest, as Q294's does"""
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    for sel in (".qg-bar", ".qg-sheet", ".qi-wrap", ".qi-corner"):
        assert "body.mode-on " + sel in css, sel
    q294 = (VIEWER / "q294" / "q294.css").read_text(encoding="utf-8")
    assert "body.mode-on .hist-bar" in q294          # the precedent this follows


def test_everything_toggled_with_hidden_is_really_hidden():
    """`hidden` is only display:none from the UA sheet, so an author `display` rule beats it. The browser dry run found
       the info drawer still on the screen because of this, swallowing the control bar's Undo on a 390 px phone."""
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    # every class that gets a `display` rule here...
    displayed = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if re.search(r"(^|;)\s*display\s*:", body) and "[hidden]" not in sel:
            displayed |= set(re.findall(r"\.([a-z0-9-]+)", sel))
    # ...and every element the modules toggle with .hidden, by the class they are given
    toggled = {"qi-wrap": "wrap.hidden", "qg-sheet": "sheet.hidden", "rs-row": "stepRow.hidden"}
    src = "\n".join((Q301 / n).read_text(encoding="utf-8") for n in MODULES)
    guard = [sel for sel, _ in re.findall(r"([^{}]+)\{([^{}]*)\}", css) if "[hidden]" in sel]
    guarded = set()
    for sel in guard:
        guarded |= set(re.findall(r"\.([a-z0-9-]+)\[hidden\]", sel))
    for cls, why in toggled.items():
        assert why in src, why
        assert cls in displayed, cls                 # it really does carry a display rule
        assert cls in guarded, f"{cls} is toggled with hidden and has a display rule but no [hidden] guard"
    assert "display:none !important" in css


def test_an_adopted_button_is_parked_not_destroyed():
    """the sheet holds the engines' REAL buttons; emptying it with innerHTML would delete them from the page"""
    g = (Q301 / "groups.js").read_text(encoding="utf-8")
    assert "function stash()" in g and "park.appendChild" in g
    assert g.count('sBody.innerHTML = "";') == 1                  # only inside stash(), after the keepers are moved out
    assert "stash();" in g.split("function openSheet")[1]
    assert "stash();" in g.split("function closeSheet")[1]
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    assert ".qg-park" in css and "left:-9999px" in css


def test_the_bar_fits_a_390_px_phone():
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    assert "@media (max-width:460px)" in css
    assert "min-height:44px" in css                           # the thumb-zone target size
    assert "flex-wrap:wrap" in css                            # the group row wraps rather than scrolling off
    for n in re.findall(r"min-width:(\d+)px", css):
        assert int(n) <= 72, n                                # nothing wide enough to break 358 px of usable width


# ---------------------------------------------------------------- item 3: the circled i -------------------------
def test_the_prose_moves_behind_a_small_circled_i():
    i = (Q301 / "info.js").read_text(encoding="utf-8")
    assert "circle cx=\"12\" cy=\"12\" r=\"9.3\"" in i          # the circle of the circled i
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    assert ".qi-corner" in css and "width:28px" in css          # small
    for eng, p in GLUE.items():
        t = p.read_text(encoding="utf-8")
        assert 'id:"about-btn"' in t or 'id:"src-sec"' in t, eng


def test_the_per_structure_provenance_stays_on_the_card():
    """Q297 found cards that lied about provenance; Q301 moves the PAGE-wide prose, never the card's own line"""
    for eng, p in TEMPLATES.items():
        t = p.read_text(encoding="utf-8")
        assert "GEOMETRY_SOURCES" in t or "source" in t, eng
    q = (Q301 / "q301.js").read_text(encoding="utf-8")
    assert "structure card" in q.lower() or "card" in (Q301 / "info.js").read_text(encoding="utf-8").lower()


# ---------------------------------------------------------------- item 6: fat off at load ------------------------
def test_fat_is_off_when_the_page_loads(tpl):
    assert 'on[c] = (c === "bone" || c === "muscle");' in tpl["own"]
    assert 'on[c] = (c === "bone" || c === "muscle" || c === "fat")' not in tpl["own"]
    assert "on.fat = false;" in tpl["zan"]
    f = (Q301 / "fat.js").read_text(encoding="utf-8")
    assert "cur = false; push();" in f                        # applied at start, not merely declared


def test_the_q295_alpha_is_kept_for_when_fat_is_switched_on(tpl):
    assert "alphaFor.fat = 0.12;" in tpl["zan"]
    assert 'sysAlpha[c] = c === "fat" ? 0.12 : 1' in tpl["own"]


def test_the_cut_face_still_fills_with_fat_either_way(tpl):
    """Q295's whole point: a section drawn without fat reads as hollow"""
    cap = (VIEWER / "cut_cap" / "cut_cap.js").read_text(encoding="utf-8")
    assert 'it.cat === "fat" && it.alpha > 0.02 ? Math.max(it.alpha, 0.9)' in cap
    for eng, t in tpl.items():
        # the exception appears twice: once for Cut mode's face, once for the cross-sections
        assert t.count("Q301: fat fills the cut face even when it is not drawn in 3-D") + \
               t.count("so a fat structure hidden ONLY because its system is off still fills") == 2, eng
    for eng, p in GLUE.items():
        assert "__q301capFat" in p.read_text(encoding="utf-8"), eng


def test_fat_is_a_single_undo_step_and_q300_can_bring_it_back():
    f = (Q301 / "fat.js").read_text(encoding="utf-8")
    assert 'hist.register("fat"' in f
    assert "source:function()" in f and 'key:"fat"' in f
    assert "touched" in f                                      # off AT LOAD is the default, so no chip until it is used


# ---------------------------------------------------------------- item 7: the depth peel ------------------------
def test_the_peel_order_is_skin_inward_and_ends_at_the_skeleton():
    p = (Q301 / "peel.js").read_text(encoding="utf-8")
    order = re.findall(r'\{key:"(\w+)",\s*label:"([^"]+)",\s*cats:\[([^\]]*)\]\}', p)
    assert [k for k, _, _ in order] == ["skin", "fat", "fascia", "muscle", "ligament", "neurovas", "viscera"]
    cats = []
    for _, _, c in order:
        cats += [x.strip().strip('"') for x in c.split(",") if x.strip()]
    assert len(cats) == len(set(cats)), cats                   # no category is peeled twice
    assert "bone" not in cats and "cartilage" not in cats      # what is LEFT is the skeleton
    assert cats[0] == "skin"


def test_the_peel_cats_are_real_categories_of_the_real_pages(tpl):
    p = (Q301 / "peel.js").read_text(encoding="utf-8")
    cats = set(re.findall(r'cats:\[([^\]]*)\]', p))
    named = set()
    for c in cats:
        named |= {x.strip().strip('"') for x in c.split(",") if x.strip()}
    lk = re.search(r'var LK = \[([^\]]*)\]', tpl["zan"]).group(1)
    zan = {x.strip().strip('"') for x in lk.split(",")}
    own = set(re.findall(r"^\s{2}(\w+):\s*\{hex:", tpl["own"], re.M))
    # every peeled category exists on at least one of the two engines
    for c in named:
        assert c in zan or c in own or c in {"lymphatic", "organ", "tendon", "ligament"}, c


def test_the_peel_is_taps_not_a_slider():
    p = (Q301 / "peel.js").read_text(encoding="utf-8")
    assert 'type="range"' not in p and "input" not in p.split("NMSKPeel")[0]
    assert 'id = "pl-down"' in p and 'id = "pl-up"' in p and 'id = "pl-whole"' in p
    assert "pl-state" in p and "/ \" + P.length" in p.replace("\\u00b7", "")   # the visible layer number (Primal's pattern)


def test_the_peel_says_which_parts_of_its_order_are_our_convention():
    p = (Q301 / "peel.js").read_text(encoding="utf-8")
    low = p.lower()
    assert "tela subcutanea" in low                      # the fat step IS the superficial fascia, and says why
    assert "membranous" in low and "scarpa" in low        # and what is genuinely absent is named
    assert "convention" in low
    assert "vessels, nerves and lymphatics come off together" in low


def test_the_fat_step_really_is_the_superficial_fascia_and_scarpa_is_really_absent():
    """The peel's note makes two factual claims; both are checked against the shipped pages, not taken on trust.
       (1) the subcutaneous-fat meshes ARE the tela subcutanea, by their own Latin names;
       (2) no page ships a separate membranous (Scarpa's) layer as a mesh -- which the pages' own search data states."""
    import glob
    pages = sorted(glob.glob(str(REPO / "build" / "q29*" / "viewer_*" / "index.html")) +
                   glob.glob(str(REPO / "build" / "q3*" / "viewer_*" / "index.html")))
    if not pages:
        pytest.skip("no built page on disk")
    for f in pages[-6:]:
        t = Path(f).read_text(encoding="utf-8", errors="replace")
        # (1) the fat layer carries the superficial fascia's own name, on 17 of its 51 structures, every page
        assert len(re.findall(r'"latin":\s*"Panniculus adiposus \(tela subcutanea\)"', t)) == 17, f
        # (2) and the page itself says Scarpa's fascia ships no mesh
        assert "not a separate membranous layer" in t, f
        # a membranous-layer MESH would be a STRUCTURE RECORD ("name" followed by its "id"), not just a row in
        # the Q298 synonym table, which is where the two names legitimately do appear as cited-but-not-shipped
        assert not re.search(r'"name":"[^"]*(?:Scarpa|Camper)[^"]*","id":', t), f


def test_every_page_carries_the_q295_fat_and_the_control_counts_it_off_the_page():
    """the count is read off the page at run time, so a wrong hard-coded number cannot creep in"""
    import glob
    pages = sorted(glob.glob(str(REPO / "build" / "q29*" / "viewer_*" / "index.html")) +
                   glob.glob(str(REPO / "build" / "q3*" / "viewer_*" / "index.html")))
    if not pages:
        pytest.skip("no built page on disk")
    for f in pages[-6:]:
        t = Path(f).read_text(encoding="utf-8", errors="replace")
        # the two engines name the field differently: "sys" on the Z pages, "cat" on the Imaging ones
        n = len(re.findall(r'"sys":"fat"', t)) + len(re.findall(r'"cat": ?"fat"', t))
        assert n == 51, (f, n)
    src = (Q301 / "fat.js").read_text(encoding="utf-8")
    assert "E.count ? E.count() | 0 : 0" in src          # read off the page, never a hard-coded count
    assert not re.search(r"n\s*=\s*51\b", src)


# ---------------------------------------------------------------- undo / reset coverage -------------------------
def test_every_new_state_is_one_undo_step_and_is_in_the_model_reset():
    keys = set()
    for n in ("render.js", "peel.js", "fat.js"):
        keys |= set(re.findall(r'hist\.register\("(\w+)"', (Q301 / n).read_text(encoding="utf-8")))
    assert keys == {"renderstyle", "peel", "fat"}, keys
    for n in ("render.js", "peel.js", "fat.js"):
        s = (Q301 / n).read_text(encoding="utf-8")
        assert "reset:function()" in s, n                      # the module reset reaches it
        assert "hist.schedule" in s, n                          # and a change is committed as ONE step


def test_q300s_show_everything_gained_the_entry_point_the_modules_need():
    """a path owned by a module cannot be in a list the engine's glue built before the module started"""
    s = (VIEWER / "q300" / "showall.js").read_text(encoding="utf-8")
    assert "add:function(s){" in s and "S.push(s); sig = \"\"; render();" in s
    for eng, p in TEMPLATES.items():
        assert "add:function(s){" in p.read_text(encoding="utf-8"), eng     # sync_q300.py carried it into the page
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "anatomy" / "q301" / "patch_showall_q301.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_new_hiding_path_is_registered_with_q300s_show_everything():
    for n, key in (("render.js", "imaging"), ("peel.js", "peel"), ("fat.js", "fat")):
        s = (Q301 / n).read_text(encoding="utf-8")
        assert f'key:"{key}"' in s and "active:function()" in s and "clear:function()" in s, n
        assert "drive:function()" in s, n                       # so verify_q301 can walk the path
        assert "opt.showall && opt.showall.add" in s, n


def test_q300s_bone_pass_is_paused_by_a_style_rather_than_fighting_it(tpl):
    """Q300 ships its bone pass ON (Clear) on the Imaging pages. Calling the pair incompatible would have left the
       X-ray style DISABLED the moment those pages loaded, so the style pauses the pass instead and says so."""
    assert 'q301.mode === "colour"' in tpl["zan"]                   # both engines pause it for ANY style
    assert 'q301spec && q301spec.mode !== "colour"' in tpl["own"]
    m = _matrix()
    row = [r for r in m if tuple(sorted((r["a"], r["b"]))) == ("boneread", "imaging")]
    assert row and row[0]["ok"] == "over"
    assert "paused" in row[0]["why"] and "comes back with the colour" in row[0]["why"]
    # and neither control is disabled by it
    g = (Q301 / "groups.js").read_text(encoding="utf-8")
    assert 'tgt.classList.toggle("qg-over", !!v.overridden)' in g
    c = (Q301 / "combos.js").read_text(encoding="utf-8")
    assert 'r.ok === "over"' in c and "disable neither" in c
    # the shipped defaults this depends on
    assert "{toolbar:tb, history:NMSKHistory, level:1}" in tpl["own"]
    assert "{toolbar:tb, history:NMSKHistory, level:0}" in tpl["zan"]

def test_every_inline_script_of_a_built_page_actually_parses():
    """The guard this round needed. A Q301 engine edit appended a `// Q301` comment to a line it was spliced into the
       MIDDLE of, which commented out the rest of a one-line expression and left the own engine's whole script
       unparseable -- `NMSKClinicalTool` never appeared and the browser verify timed out on the engine's own API, not
       on anything of Q301's. Nothing short of parsing the result would have caught it, so this parses all of it."""
    import glob
    import subprocess
    import tempfile
    pages = sorted(glob.glob(str(REPO / "build" / "q301" / "viewer_*" / "index.html")))
    if not pages:
        pytest.skip("no build/q301 on disk")
    inline = re.compile(r'<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>(.*?)</script>', re.S)
    for f in pages:
        src = Path(f).read_text(encoding="utf-8")
        blocks = inline.findall(src)
        assert len(blocks) >= 5, (f, len(blocks))
        for i, js in enumerate(blocks, 1):
            if not js.strip():
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as h:
                h.write(js); tmp = h.name
            r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True)
            assert r.returncode == 0, f"{Path(f).parent.name} inline script #{i}: {r.stderr[:400]}"


def test_no_q301_edit_appends_a_line_comment_mid_line():
    """the same trap, caught at the source: an edit spliced into the middle of a line must not end in `//`"""
    src = (REPO / "scripts" / "anatomy" / "q301" / "patch_engines_q301.py").read_text(encoding="utf-8")
    import ast
    tree = ast.parse(src)
    news = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") in ("Z_EDITS", "OWN_EDITS") for t in node.targets):
            for el in node.value.elts:
                vals = [v for v in el.elts if isinstance(v, ast.Constant) and isinstance(v.value, str)]
                if len(vals) >= 2:
                    news.append((vals[0].value, vals[1].value))
    assert len(news) == 17, len(news)
    for old, new in news:
        last = new.rstrip("\n").splitlines()[-1]
        if "//" in last and not last.rstrip().endswith("*/"):
            # a trailing line comment is only safe when the anchor consumed the whole source line, i.e. the old text's
            # last line ends the statement it belongs to
            ol = old.rstrip("\n").splitlines()[-1].rstrip()
            assert ol.endswith((";", "{", "}", ")", "+", ",")), f"mid-line // comment after an anchor ending {ol[-40:]!r}"


# ---------------------------------------------------------------- nothing of Q300's may cover the new control -----
def test_the_lift_given_to_q300s_chip_bar_covers_an_open_group_not_just_the_bar():
    """Q300's chip bar is `z-index: 2147482000` in the same bottom corner. Q301 lifts it with a transform by
       `--q301-bar-h`. Twice on a 390 px phone that lift was too small: first it did not exist and the bar sat on
       Redo, then it was the control bar's own height alone and the bar sat on the OPEN GROUP'S SHEET, swallowing the
       fat toggle and two of six taps on the depth peel. The published height must include the open sheet."""
    js = (Q301 / "groups.js").read_text(encoding="utf-8")
    css = (Q301 / "q301.css").read_text(encoding="utf-8")
    assert "--q301-bar-h" in css and "translateY" in css, "the stylesheet must lift Q300's bar by the variable"
    m = re.search(r'setProperty\("--q301-bar-h",([^;]+)\);', js)
    assert m, "groups.js must publish --q301-bar-h"
    expr = m.group(1)
    assert "open" in expr, f"the lift must add the open sheet's height, not the bar's alone: {expr.strip()}"
    # and `open` must be the sheet's measured height, set inside the !sheet.hidden branch
    assert re.search(r"open\s*=\s*\(?sheet\.offsetHeight", js), "the sheet's own offsetHeight must feed the lift"
    assert re.search(r"var\s+open\s*=\s*0", js), "the lift must fall back to 0 while no group is open"
    # the lift has to be recomputed when a group closes as well as when one opens
    close = js[js.index("function closeSheet"):js.index("function openSheet")]
    assert "place()" in close, "closing a group must recompute the lift in the same frame"


def test_the_browser_check_refuses_a_tap_that_lands_on_something_else():
    """The script used to aim at an element's centre and never look at what was there, so a covered control read as a
       broken product. It now records every miss and asserts there were none."""
    v = (REPO / "scripts" / "anatomy" / "q301" / "verify_q301.py").read_text(encoding="utf-8")
    assert "elementFromPoint" in v, "the tap helper must check what is actually under the point"
    assert "MISSED" in v and "covered_controls" in v
    assert "every control this script tapped was really on top" in v
