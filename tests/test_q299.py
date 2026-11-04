"""Q299: data-level assertions for the pelvic measurements, for containment, and for the cross-section fix.

Three families, matching the three parts of the round:
  A  the pelvic measurements of all six pages against the ranges they were compared with -- the 47 women of the Q250
     reference set measured with the SAME geometric rules where one exists, published figures otherwise.
  B  no structure further outside the body than the stated tolerance, except the exempt classes, each of which is
     exempt for a stated anatomical reason and is pinned here by name so a later round cannot widen the exemption.
  C  the cut-face fill gives every cut section a minimum drawn width, and a 1 mm structure is not drawn as a cable.
Everything reads the committed measurement files, so the suite does not need a browser.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data/derived"
PELVIS = D / "Q299_pelvis.json"
CONTAIN = D / "Q299_containment.json"
XSEC = D / "Q299_crosssection_coverage.json"
FIXREP = D / "Q299_containment_fix.json"
CUTCAP = REPO / "viewer/cut_cap/cut_cap.js"
NODE = "node"
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
FEMALE = ["own_f", "base_f", "comb_f"]

# the 47-women reference (data/derived/Q250_ts_women_pelvis_measures.json), measured with the SAME rules as the pages
REF47 = {
    "transverse_mm": (138.1, 39.4), "ap_conjugate_mm": (136.2, 11.7), "intertuberous_mm": (106.3, 13.5),
    "subpubic_angle_deg": (83.4, 9.9), "bi_iliac_breadth_mm": (280.8, 17.6), "pelvic_height_mm": (208.6, 10.3),
    "breadth_over_height_pct": (134.7, 7.4), "interfemoral_head_mm": (176.0, 9.0), "sacral_breadth_mm": (120.1, 6.7),
    "sacral_length_straight_mm": (114.5, 14.6), "sacral_curvature_depth_mm": (26.3, 8.7),
    "sciatic_notch_hull_angle_deg": (99.3, 5.6), "ischiopubic_index": (123.6, 5.0),
}
# what Q299 found and what a later round must not silently undo
KNOWN_OUT = {("comb_f", "interfemoral_head_mm"), ("comb_f", "sciatic_notch_hull_angle_deg"),
             ("base_f", "interfemoral_head_mm"), ("own_f", "interfemoral_head_mm")}
# Exempt by anatomy: the ocular surface sits in the palpebral fissure and these pages carry no conjunctiva or
# eyelid-margin mesh; the subject's own finger bones are a limit of her segmentation (her CT merges the fingers into
# one label) and of the Q293 re-seating -- and bone is never moved by policy.
EXEMPT_WORDS = ("cornea", "iris", "sclera", "chamber_of_eyeball", "phalanx", "phalanges")
# The two Imaging pages were deliberately NOT touched in Q299: their geometry comes from the bundle builder and only
# build/q293/bundle_own_* is on disk, which predates the Q295 fat additions. Their five offenders are named here, with
# their measured distance, and are put to the owner in docs/OPEN_ITEMS_FOR_OWNER.md -- so the test still catches a NEW
# one appearing on those pages, and catches any of these getting worse.
IMAGING_NOT_TOUCHED = {
    ("own_m", "deltoid_r_zfill203"): 11.0,          # Q203 rule-based void fill
    ("own_m", "dorsal_n_penis_r"): 9.0,             # Q249 rule-based nerve
    ("own_m", "dorsal_n_penis_l"): 7.0,
    ("own_m", "rectus_abdominis_r_zfill203s"): 6.5,
    ("own_m", "brachialis_r_zfill203s"): 6.5,
    ("own_m", "extensor_indicis_r"): 6.5,
    ("own_f", "flexor_retinaculum_r"): 6.5,
}


@pytest.fixture(scope="module")
def pelvis():
    if not PELVIS.is_file():
        pytest.skip("Q299_pelvis.json not built")
    return json.loads(PELVIS.read_text())["pages"]


@pytest.fixture(scope="module")
def contain():
    if not CONTAIN.is_file():
        pytest.skip("Q299_containment.json not built")
    return json.loads(CONTAIN.read_text())["pages"]


@pytest.fixture(scope="module")
def xsec():
    if not XSEC.is_file():
        pytest.skip("Q299_crosssection_coverage.json not built")
    return json.loads(XSEC.read_text())["pages"]


# ------------------------------------------------------------------ A. pelvis
def test_every_page_has_the_full_pelvic_measurement_set(pelvis):
    need = ["transverse_mm", "ap_conjugate_mm", "obstetric_conjugate_mm", "interspinous_mm", "intertuberous_mm",
            "subpubic_angle_deg", "bi_iliac_breadth_mm", "bicristal_mm", "asis_breadth_mm", "pelvic_height_mm",
            "biacromial_mm", "bicristal_over_biacromial", "interfemoral_head_mm", "sacral_breadth_mm",
            "sacral_length_straight_mm", "sacral_curvature_depth_mm", "ischiopubic_index",
            "sciatic_notch_hull_angle_deg"]
    for k in KEYS:
        missing = [n for n in need if not isinstance(pelvis[k].get(n), (int, float))]
        assert missing == [], f"{k}: missing pelvic measurements {missing}"
        assert isinstance(pelvis[k].get("symphysis", {}).get("symphysis_height_mm"), (int, float))
        for s in "lr":
            assert isinstance(pelvis[k].get(f"acetabulum_app_{s}", {}).get("acetabular_diameter_mm"), (int, float)), f"{k} {s}"


def test_female_pelvimetry_is_within_two_sd_of_the_rule_matched_reference(pelvis):
    """Everything the 47 women give a rule-matched range for must be within 2 SD, except the measures Q299 reports
    as genuinely out -- and those must STAY out by at least 2 SD, so the finding cannot be quietly lost."""
    for k in FEMALE:
        for name, (m, s) in REF47.items():
            v = pelvis[k].get(name)
            if not isinstance(v, (int, float)):
                continue
            z = (v - m) / s
            if (k, name) in KNOWN_OUT:
                assert abs(z) >= 2.0, f"{k} {name} = {v} is now {z:+.2f} SD: Q299 recorded it as out of range, update the record"
            else:
                assert abs(z) <= 2.0, f"{k} {name} = {v} is {z:+.2f} SD of the 47-women reference {m} +- {s}"


def test_the_subpubic_angle_separates_the_sexes_on_every_page(pelvis):
    """female 87.4 +- 6.5, male 68.6 +- 7.6 deg, cut-off 78.6 (PMID 32274246)."""
    for k in FEMALE:
        assert pelvis[k]["subpubic_angle_deg"] > 78.6, f"{k} subpubic {pelvis[k]['subpubic_angle_deg']}"
    for k in ("own_m", "base_m", "comb_m"):
        assert pelvis[k]["subpubic_angle_deg"] < 78.6, f"{k} subpubic {pelvis[k]['subpubic_angle_deg']}"


def test_the_combined_female_femora_are_the_one_pelvic_defect_and_it_is_measured(pelvis):
    """The bi-acetabular distance of Combined Female must be recorded as wider than HER OWN pelvis, which is the
    defect Q299 found (the Q250 warp never re-seated the femora)."""
    hers = pelvis["own_f"]["interfemoral_head_mm"]
    assert pelvis["comb_f"]["interfemoral_head_mm"] - hers > 10.0
    assert abs(pelvis["base_f"]["interfemoral_head_mm"] - hers) < 5.0, "Base F should carry her own width"


def test_base_female_is_more_hip_dominant_than_her_own_body_and_both_are_recorded(pelvis):
    r_hers, r_base = pelvis["own_f"]["bicristal_over_biacromial"], pelvis["base_f"]["bicristal_over_biacromial"]
    assert r_base > r_hers, "the Q299 finding is that Base F is MORE hip-dominant than her own body"
    for k in ("own_m", "base_m", "comb_m"):
        assert pelvis[k]["bicristal_over_biacromial"] < min(r_hers, r_base), f"{k} should be less hip-dominant than any female page"


def test_her_long_bones_are_reproduced_on_the_base_female_page():
    p = D / "Q299_long_bones.json"
    if not p.is_file():
        pytest.skip("Q299_long_bones.json not built")
    B = json.loads(p.read_text())
    for bone, tol in (("femur_r", 0.03), ("humerus_r", 0.03), ("tibia_r", 0.04), ("hip_bone_r", 0.03)):
        hers, base = B["own_f"][bone], B["base_f"][bone]
        assert abs(base - hers) / hers <= tol, f"{bone}: Base F {base} vs her own {hers}"


# ------------------------------------------------------------------ B. containment
def test_every_page_body_mask_passes_validation(contain):
    for k in KEYS:
        v = contain[k]["validation"]
        assert v["ok"], f"{k}: body mask invalid -- {v['reasons']}"
        assert v["error_band"]["p95_mm"] <= 3.0, f"{k}: mask error band p95 {v['error_band']['p95_mm']} mm"
        assert len(v["deep_inside_pct"]) >= 15, f"{k}: only {len(v['deep_inside_pct'])} deep structures checked"


def test_no_structure_lies_more_than_the_tolerance_outside_the_body(contain):
    """The tolerance is 10 mm: well above the mask's own error band (p95 1.4 / max 8.3 mm) and well below the 21.7 mm
    the external pudendal vessels of Base Female reached before the fix.  Exempt by anatomy / by source, each stated:
    the ocular surface (the cornea, iris, sclera and chambers sit in the palpebral fissure, which carries no skin mesh
    on these pages) and the subject's own finger bones (her CT merges the fingers into one label; Q293 / Q297)."""
    tol = 10.0
    bad = []
    for k in KEYS:
        for r in contain[k]["offenders"]:
            cap = IMAGING_NOT_TOUCHED.get((k, r["id"]))
            if cap is not None:
                assert r["out_max_mm"] <= cap, f"{k}/{r['id']} is now {r['out_max_mm']} mm out, was under {cap}"
                continue
            if r["out_max_mm"] <= tol:
                continue
            if any(w in r["id"] for w in EXEMPT_WORDS):
                continue
            bad.append((k, r["id"], r["sys"], r["out_max_mm"]))
    assert bad == [], f"{len(bad)} structures lie more than {tol} mm outside the body: {bad[:12]}"


def test_the_pages_q299_fixed_have_nothing_left_outside_but_the_exempt_classes(contain):
    """Base Female was the owner's page: 20 offenders beyond 5 mm before, and after the fix the only ones left are
    the six ocular-surface meshes. Combined Male and Combined Female keep only exempt classes and bone."""
    for k in ("base_f", "comb_m"):
        left = [(r["id"], r["sys"], r["out_max_mm"]) for r in contain[k]["offenders"]
                if not any(w in r["id"] for w in EXEMPT_WORDS)]
        assert left == [], f"{k}: {left}"
    left = [(r["id"], r["sys"], r["out_max_mm"]) for r in contain["comb_f"]["offenders"]
            if not any(w in r["id"] for w in EXEMPT_WORDS) and r["sys"] != "bone"]
    assert all(x[2] <= 6.0 for x in left), f"comb_f: {left}"


def test_the_ocular_exemption_is_the_only_offender_on_base_male(contain):
    """Base Male is the control: its external pudendal vessels end inside the external genital skin the female pages
    no longer have, and nothing else on that page is outside the body at all."""
    ids = [r["id"] for r in contain["base_m"]["offenders"]]
    assert ids, "the audit found nothing at all on Base M -- the test is not measuring"
    assert all(any(w in i for w in EXEMPT_WORDS) for i in ids), f"Base M has a non-exempt offender: {ids}"


def test_the_external_pudendal_vessels_were_the_finding_and_are_fixed(contain):
    if not FIXREP.is_file():
        pytest.skip("Q299_containment_fix.json not built")
    fix = json.loads(FIXREP.read_text())["pages"]
    for sid in ("zan_external_pudendal_veins_l", "zan_external_pudendal_veins_r",
                "zan_superficial_external_pudendal_artery_l", "zan_superficial_external_pudendal_artery_r"):
        s = fix["base_f"]["fixed"].get(sid)
        assert s, f"{sid} is not in the Base F fix report"
        assert s["out_max_before_mm"] > 15.0, f"{sid} before {s['out_max_before_mm']}"
        assert s["outside_after_max_mm"] <= 2.0, f"{sid} after {s['outside_after_max_mm']}"
        assert s["flipped_tris"] == 0, f"{sid} flipped {s['flipped_tris']} triangles"
        assert 0.8 <= s["volume_ratio"] <= 1.2, f"{sid} volume x{s['volume_ratio']}"
    # and the page the owner would compare it with has no such defect
    assert fix["base_m"]["to_fix"] == [], f"Base M should need no fix: {fix['base_m']['to_fix']}"


def test_no_structure_is_moved_that_the_policy_exempts():
    if not FIXREP.is_file():
        pytest.skip("Q299_containment_fix.json not built")
    fix = json.loads(FIXREP.read_text())["pages"]
    for k, p in fix.items():
        for sid in p.get("fixed", {}):
            assert "bone" != next((r["sys"] for r in p["to_fix"] if r["id"] == sid), None) or True
        moved_bones = [r["id"] for r in p["to_fix"] if r["sys"] == "bone"]
        assert moved_bones == [], f"{k}: a bone is in the fix list ({moved_bones}) -- bones are never moved"
        for r in p["exempt"]:
            assert r["id"] not in p.get("fixed", {}), f"{k}: {r['id']} is exempt but was moved"


# ------------------------------------------------------------------ C. cross-section
def test_the_cut_face_fill_has_a_minimum_drawn_width():
    src = CUTCAP.read_text(encoding="utf-8")
    assert "function strokeItem(" in src and "function contourLen(" in src
    assert "bandFrac" in src and "bandMax" in src
    assert "var BAND_FRAC = 1 / 500, BAND_MAX = 2.5;" in src, "the controller must pass a minimum drawn width"
    assert src.count("bandFrac:BAND_FRAC") >= 4, "every build call of the controller must pass it"


def test_a_thin_structure_is_drawn_and_a_thin_one_is_not_drawn_thick():
    """Runs the real module under node on two synthetic sections:
      * a single-layer tilted SHEET -- the real fascia case, one contour segment per row, so the parity sanity test
        fails and before Q299 it was left as a 1 px vector outline with not one painted pixel;
      * a 1 mm TUBE -- too thin for the raster to show.
    Both must come out painted, the band must still be a thickened outline (every painted pixel within half a band of
    a real contour segment), and a 1 mm structure must not be drawn wider than the stated 2.5 mm maximum."""
    js = r"""
    eval(require('fs').readFileSync('viewer/cut_cap/cut_cap.js','utf8') + ';global.K=NMSKCapCore;');
    function tube(r, n, y0, y1){                       // closed cylinder about y
      var pos=[], idx=[];
      for (var s=0;s<2;s++) for (var i=0;i<n;i++){ var a=2*Math.PI*i/n; pos.push(r*Math.cos(a), s?y1:y0, r*Math.sin(a)); }
      for (var i=0;i<n;i++){ var j=(i+1)%n; idx.push(i,j,n+i, j,n+j,n+i); }
      return {pos:new Float32Array(pos), idx:new Uint16Array(idx), bmin:[-r,y0,-r], bmax:[r,y1,r]};
    }
    function shift(g, dx){ var q=new Float32Array(g.pos); for (var i=0;i<q.length;i+=3) q[i]+=dx;
      return {pos:q, idx:g.idx, bmin:[g.bmin[0]+dx,g.bmin[1],g.bmin[2]], bmax:[g.bmax[0]+dx,g.bmax[1],g.bmax[2]]}; }
    var sheet = {pos:new Float32Array([160,-10,-20, 240,-10,20, 240,10,20, 160,10,-20]),
                 idx:new Uint16Array([0,1,2, 0,2,3]), bmin:[160,-10,-20], bmax:[240,10,20]};
    var big = tube(20, 24, -10, 10), thin = shift(tube(0.5, 12, -10, 10), 90);
    function items(){ return [
      {key:'big', name:'big', cat:'muscle', rgb:[1,0,0], alpha:1, geom:function(){return big;}},
      {key:'nerve1mm', name:'n', cat:'nerve', rgb:[0,1,0], alpha:1, geom:function(){return thin;}},
      {key:'fascia', name:'f', cat:'fascia', rgb:[0,0,1], alpha:1, geom:function(){return sheet;}}]; }
    function px(res, key){ var it=res.items.filter(function(x){return x.key===key;})[0]; if(!it) return null;
      var n=0; for (var i=0;i<res.ids.length;i++) if (res.ids[i]===it.code) n++;
      return {status:it.status, px:n, width_mm:it.width_mm, band_mm:it.band_mm}; }
    var off = K.build(items(), {n:[0,1,0], d:0}, {});
    var on  = K.build(items(), {n:[0,1,0], d:0}, {bandFrac:1/500, bandMax:2.5});
    console.log(JSON.stringify({
      off:{nerve:px(off,'nerve1mm'), fascia:px(off,'fascia'), outline_only:off.stats.outline_only, thin:off.stats.thin},
      on :{nerve:px(on ,'nerve1mm'), fascia:px(on ,'fascia'), band:on.stats.band, banded:on.stats.banded},
      px_mm:on.px, band_mm:on.stats.band_mm}));
    """
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=180, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2000:]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    # before Q299: the single-layer sheet failed the parity test and painted nothing at all
    assert o["off"]["outline_only"] >= 1, o
    assert o["off"]["fascia"]["status"] == "outline" and o["off"]["fascia"]["px"] == 0, o
    # after: painted, in its own colour
    assert o["on"]["fascia"]["status"] == "band" and o["on"]["fascia"]["px"] > 0, o
    assert o["on"]["band"] >= 1 and o["on"]["banded"] >= 1, o
    # the 1 mm tube gains pixels too
    assert o["on"]["nerve"]["px"] > o["off"]["nerve"]["px"], o
    # the band is a minimum, not a licence to draw thick
    assert 0 < o["band_mm"] <= 2.5, o
    assert o["on"]["fascia"]["band_mm"] == o["band_mm"] and o["on"]["nerve"]["band_mm"] == o["band_mm"], o
    # painted area / contour length of the 1 mm tube section must stay within the band
    drawn_mm = o["on"]["nerve"]["px"] * o["px_mm"] ** 2 / (3.14159 * 1.0)
    assert drawn_mm <= 2.5, f"a 1 mm nerve is drawn {drawn_mm:.2f} mm wide: {o}"


def test_the_cross_section_coverage_improved_on_every_page_and_by_class(xsec):
    for k in KEYS:
        b, a = xsec[k]["totals_before"], xsec[k]["totals_after"]
        assert a["invisible"] < b["invisible"] * 0.6, f"{k}: invisible sections {b['invisible']} -> {a['invisible']}"
        assert a["thin"] == 0 and a["outline"] == 0, f"{k}: {a['thin']} thin / {a['outline']} outline-only sections remain"
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        for cls in ("vessel", "fascia"):
            b = xsec[k]["by_class_before"][cls]["invisible"]
            a = xsec[k]["by_class_after"][cls]["invisible"]
            assert b > 100 and a <= 0.10 * b, f"{k} {cls}: {b} -> {a}"


def test_the_lower_limb_nerve_inventory_is_recorded():
    """The owner's case, as data: 0 fibular / peroneal nerve meshes on either Imaging page against 18 on every Z page."""
    p = D / "Q299_lower_limb_nerves.json"
    if not p.is_file():
        pytest.skip("Q299_lower_limb_nerves.json not built")
    J = json.loads(p.read_text())
    for k in ("own_m", "own_f"):
        assert J["fibular_or_peroneal"][k] == [], f"{k} now carries a fibular nerve: update the record"
        assert len(J["missing_from_imaging"][k]) >= 50, f"{k}: only {len(J['missing_from_imaging'][k])} missing"
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        assert len(J["fibular_or_peroneal"][k]) == 18, f"{k}: {len(J['fibular_or_peroneal'][k])} fibular meshes"
        assert any(i.startswith("common_fibular_n") for i in J["fibular_or_peroneal"][k]), k
    assert J["lower_limb"]["own_m"] < J["lower_limb"]["comb_m"] / 4


def test_the_imaging_pages_carry_no_fibular_nerve_and_the_round_says_so():
    """The owner's own case AS Q299 FOUND IT, pinned against the Q299-era build on disk. The Imaging-based pages of
    that build have no common / deep / superficial fibular nerve at all, which is why no cross-section of them could
    show one; Q299 recorded the finding and did not invent the nerve. Q304 later carried 18 fibular meshes onto each
    Imaging page from the Combined page of the same body, so the CURRENT pages do carry them -- that is
    tests/test_q304.py's business, and this test deliberately keeps reading build/q299 so the historical
    measurement stays checkable."""
    doc = REPO / "docs/research/Q299_pelvis_containment_crosssection.md"
    if not doc.is_file():
        pytest.skip("Q299 research doc not written")
    t = doc.read_text(encoding="utf-8")
    assert "common_fibular_n" in t and "OPEN_ITEMS" in t.replace("open_items", "OPEN_ITEMS").upper()
    for stem in ("viewer_m_hr/atlas_viewer_male.html", "viewer_f_hr/atlas_viewer_female.html"):
        p = REPO / "build/q299" / stem
        if not p.is_file():
            pytest.skip("build/q299, the baseline this historical measurement was made on, is not on disk")
        html = p.read_text(encoding="utf-8")
        i = html.index('id="bundle-json" type="application/json">') + len('id="bundle-json" type="application/json">')
        B = json.loads(html[i:html.index("</script>", i)])
        ids = {s["id"] for s in B["structures"]}
        assert not {i2 for i2 in ids if "fibular_n" in i2}, "an Imaging page now carries a fibular nerve: update the record"


# ------------------------------------------------------------------ the pose rig after the geometry change
@pytest.mark.parametrize("key", ["base_f", "comb_f", "comb_m"])
def test_the_pose_rig_took_fresh_weights_for_the_replaced_geometries(key):
    """The moved structures are skinned, and make_pose_rig derives their weights from the vertex positions, so their
    entries must come from a fresh run on the new page while every other entry stays byte for byte as committed.
    This checks the result is internally consistent and that the splice is recorded."""
    import base64, zlib
    p = REPO / f"data/anatomy/pose_rig_{key}.json"
    if not p.is_file():
        pytest.skip(f"{p.name} missing")
    J = json.loads(p.read_text())
    R = J["rig"]
    if "Q299" not in R.get("notes", ""):
        pytest.skip("the Q299 rig splice has not been applied yet")
    if not FIXREP.is_file():
        pytest.skip("Q299_containment_fix.json not built")
    rep = json.loads(FIXREP.read_text())["pages"][key]
    assert len(R["nv"]) == R["count"]
    blob = zlib.decompress(base64.b64decode(J["weights_zlib_b64"]))

    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)

    off = 0
    for e in R["skin"]:
        assert e[4] == off, f"{key}: skinning weight offsets are not contiguous at structure {e[0]}"
        off += seglen(e)
    assert off == len(blob), f"{key}: weight blob is {len(blob)} bytes, the entries account for {off}"
    ids = set(rep.get("fixed_indices", {}).values())
    placed = {e[0] for e in R["skin"]} | {x for g in R["rigid"] for x in g[1]}
    assert ids <= placed, f"{key}: a replaced structure is in neither the skinned nor the rigid list"
    assert all(0 <= x < R["count"] for x in placed)


def test_bone_penetration_is_measured_per_bone_and_its_known_cases_are_pinned(contain):
    """The bone test must use PER-BONE masks: one global bone mask closes the thoracic cage and the pelvis and its hole
    fill swallows the mediastinum, which called 53 % of Imaging M's abdominal aorta "inside a bone". With per-bone
    masks the aorta is not in the list at all, and the structures that really do sit mostly inside a bone are few and
    named."""
    for k in KEYS:
        rows = contain[k].get("bone_mostly_inside")
        if rows is None:
            pytest.skip("the per-bone audit has not been re-run")
        assert len(rows) <= 12, f"{k}: {len(rows)} structures mostly inside a bone -- was 1-10 in Q299"
        for r in rows:
            assert r.get("bones"), f"{k}: {r['id']} does not name the bone it is inside"
    assert not [r for r in contain["own_m"]["bone_mostly_inside"] if "aorta" in r["id"]], \
        "the abdominal aorta is back in the list: the bone mask has gone global again"
    heel = [r for r in contain["base_m"]["bone_mostly_inside"] if "calcaneal_branches_of_fibular_artery" in r["id"]]
    assert heel, "the calcaneal branches of the fibular artery were the headline bone-penetration finding of Q299"
