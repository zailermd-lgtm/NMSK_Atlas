#!/usr/bin/env python3
"""Q295: the `fat` system (fat + unlabelled soft tissue from imaging) in both viewer engines, the cut-face fill and the imaging class map.
Idempotent; every edit asserts its anchor exactly once."""
import json, re, sys
from pathlib import Path
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]


def sub1(text, old, new, label):
    if new in text:
        return text
    n = text.count(old)
    assert n == 1, (label, n)
    return text.replace(old, new)


# 1. cut-face fill: a faint fat layer is still cut and filled solid (it is the filling of the section, faded only in 3-D so it does not occlude)
p = REPO / "viewer/cut_cap/cut_cap.js"; t = p.read_text()
t = sub1(t, "  function rankOf(cat){ var r = RANK[cat]; return r == null ? 3 : r; }",
         "  function rankOf(cat){ var r = RANK[cat]; return r == null ? 3 : r; }\n"
         "  function capA(it){ return it.cat === \"fat\" && it.alpha > 0.02 ? Math.max(it.alpha, 0.9) : it.alpha; }   // Q295: fat is faded in 3-D but fills the cut face solid",
         "capA")
t = sub1(t, "      if (!(it.alpha >= 0.2)) return;                                  // a ghost",
         "      if (!(capA(it) >= 0.2)) return;                                  // a ghost", "cut alpha")
t = sub1(t, "      var it = by[r.ii], a = Math.round(Math.max(0, Math.min(1, it.alpha)) * 255), c = it.rgb;",
         "      var it = by[r.ii], a = Math.round(Math.max(0, Math.min(1, capA(it))) * 255), c = it.rgb;", "recolor alpha")
t = sub1(t, "fillItem:fillItem, build:build, recolor:recolor, lookup:lookup, rankOf:rankOf};",
         "fillItem:fillItem, build:build, recolor:recolor, lookup:lookup, rankOf:rankOf, capA:capA};", "export capA")
t = sub1(t, "    items.forEach(function(it){ is += it.key + (it.alpha >= 0.2 ? \"\" : \"~\") + \";\";",
         "    items.forEach(function(it){ is += it.key + (NMSKCapCore.capA(it) >= 0.2 ? \"\" : \"~\") + \";\";", "sig alpha")
p.write_text(t)

# 2. own engine
p = REPO / "viewer/atlas_viewer.template.html"; t = p.read_text()
t = sub1(t, '  organ:     {hex:0xC98A6B, label:"Organ"},\n',
         '  organ:     {hex:0xC98A6B, label:"Organ"},\n  fat:       {hex:0xE9D08A, label:"Fat & unlabelled soft tissue"},\n', "TISSUE.fat")
t = sub1(t, '  on[c] = (c === "bone" || c === "muscle");\n  sysAlpha[c] = 1;',
         '  on[c] = (c === "bone" || c === "muscle" || c === "fat");   // Q295: fat on but faint (fills the cut faces / cross-sections)\n'
         '  sysAlpha[c] = c === "fat" ? 0.12 : 1;', "own fat default")
t = sub1(t, '<input type="range" class="sys-op-sl" min="0" max="100" value="100" aria-label="',
         '<input type="range" class="sys-op-sl" min="0" max="100" value="\' + Math.round((sysAlpha[c] == null ? 1 : sysAlpha[c]) * 100) + \'" aria-label="',
         "own slider init")
t = sub1(t, '<output class="sys-op-v">100%</output>',
         '<output class="sys-op-v">\' + Math.round((sysAlpha[c] == null ? 1 : sysAlpha[c]) * 100) + \'%</output>', "own slider label")
p.write_text(t)

# 3. Z engine
p = REPO / "viewer/zan_atlas.template.html"; t = p.read_text()
t = sub1(t, 'var LK = ["bone","cartilage","joint","insertion","muscle","fascia","bursa","nerve","cns","vessel","lymph","viscera","skin"];',
         'var LK = ["bone","cartilage","joint","insertion","muscle","fascia","bursa","nerve","cns","vessel","lymph","viscera","fat","skin"];', "LK")
t = sub1(t, "    alphaFor.skin = 0.3;", "    alphaFor.fat = 0.12;   // Q295: fat / unlabelled soft tissue from imaging: faint in 3-D, solid in the cut face\n    alphaFor.skin = 0.3;", "alphaFor")
n = t.count("--t-insertion:")
assert n >= 3, n
if "--t-fat:" not in t:
    t = t.replace("--t-insertion:", "--t-fat:#e3c77e; --t-insertion:")
t = sub1(t, 'lymph:.2, viscera:.25, skin:.06};\n    function selLook', 'lymph:.2, viscera:.25, fat:.05, skin:.06};\n    function selLook', "XRAY_A")
t = sub1(t, '{k:"vessel",label:"Cardiovascular"},{k:"lymph",label:"Lymphoid"},{k:"viscera",label:"Viscera"},\n',
         '{k:"vessel",label:"Cardiovascular"},{k:"lymph",label:"Lymphoid"},{k:"viscera",label:"Viscera"},\n      {k:"fat",label:"Fat & unlabelled soft tissue"},\n', "LAYERS")
t = sub1(t, '"btn-solid":function(){ var m={}; LK.forEach(function(k){m[k]=1;}); preset(m); },',
         '"btn-solid":function(){ var m={}; LK.forEach(function(k){m[k]=1;}); m.fat=0.12; preset(m); },', "solid preset")
t = sub1(t, 'lymph:.2,viscera:.25,skin:.06}); },\n      "btn-bones"', 'lymph:.2,viscera:.25,fat:.05,skin:.06}); },\n      "btn-bones"', "xray preset")
p.write_text(t)

# 4. imaging / ultrasound class map: the new system maps to fat, its unlabelled soft tissue to the generic soft-tissue class
p = REPO / "clinical/data/imaging_tissues.json"; t = p.read_text()
anchor = '      {"cat": ["bone"], "re": "tooth|teeth|incisor|molar|canine|premolar|enamel"'
ins = ('      {"cat": ["fat"], "re": "unlabelled soft tissue|soft_unlabelled", "cls": "soft_unassigned", "why": "Q295: space no segmented structure covers where the body\'s own imaging shows soft tissue (not fat): generic soft tissue"},\n'
       '      {"cat": ["fat"], "cls": "fat", "why": "Q295: fat measured from the body\'s own imaging (CT HU / cryosection colour) in the space no structure covers"},\n')
if '"cat": ["fat"]' not in t:
    assert t.count(anchor) == 1
    t = t.replace(anchor, ins + anchor)
    json.loads(t)
    p.write_text(t)
print("PATCH_Q295_OK")
