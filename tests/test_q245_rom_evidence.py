"""Q245: the range-of-motion table was re-checked against the literature (docs/pose_rom_table.md, scripts/anatomy/q241/rom.py): evidence records, the bound rule, honesty of the status labels,
the embedded rig JSON and the literature check of the left / right pose thresholds."""
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
import rom  # noqa: E402

V = ("V_FT", "V_AB")
FULL_TEXT_SOURCES = {"Vairo2012", "Baumbach2014"}               # the only primary papers whose full text / tables were read


def _r(x):
    return int(math.floor(x + 0.5))


def test_rom_is_built_from_the_evidence():
    assert set(rom.ROM) == set(rom.ROM_EVID)
    assert len(rom.ROM) >= 34
    for k, (lo, hi, lab, src) in rom.ROM.items():
        v = rom.ROM_EVID[k]
        assert (lo, hi) == (v["lo"]["new"], v["hi"]["new"]), k
        assert lo < hi and lab and src, k
        assert v["lo"]["new"] <= 0 or k.startswith(("toe", "finger", "thumb")), k


def test_every_end_has_a_status_and_the_labels_are_honest():
    for k, w, e in rom.ends():
        assert e["st"] in rom.STATUS, (k, w)
        txt = rom.status_text(e)
        if e["st"] in V:
            assert e["n"] >= 1 and e["refs"], (k, w)            # 'verified' needs a source whose number was read
            assert "verified from source" in txt
        else:
            assert "verified from source" not in txt, (k, w)    # nothing else may be called verified
            assert e["st"] != "SEC" or e["n"] >= 1
        if e["st"] in ("AO", "AS", "DEF"):
            assert e["n"] == 0, (k, w)
        if e["st"] == "V_FT":
            assert set(e["refs"]) & FULL_TEXT_SOURCES, (k, w)   # 'full text' only for the two papers whose full text was returned
        if e["st"] == "AO":
            assert e["new"] == e["old"], (k, w)                 # an unverified number is never changed on a guess
    c = {k: sum(1 for _, _, e in rom.ends() if e["st"] == k) for k in rom.STATUS}
    assert c["V_FT"] == 4 and c["V_AB"] + c["V_FT"] >= 20 and c["AO"] >= 15 and c["AS"] >= 10, c


def test_sources_are_real_citations():
    cited = {r for _, _, e in rom.ends() for r in e["refs"]} | {r for _, _, refs, _ in rom.COUPLED for r in refs}
    assert cited <= set(rom.SOURCES)
    for i, (cite, doi, pmid, how) in rom.SOURCES.items():
        assert cite and how, i
        if i not in ("Apti2023", "Greene1994"):
            assert pmid and re.fullmatch(r"\d{5,8}", pmid), i  # PubMed-confirmed record
        if doi:
            assert doi.startswith("10."), i
    # PMIDs seen in the PubMed records of this session
    assert rom.SOURCES["Vairo2012"][2] == "22964130" and rom.SOURCES["Baumbach2014"][2] == "25053374" and rom.SOURCES["Soucie2011"][2] == "21070485"
    assert "NOT Am J Sports Med" in rom.SOURCES["Ellenbecker1996"][3]        # the Q245 task description cited it with the wrong journal
    assert "NOT read" in rom.SOURCES["Greene1994"][3]                      # the books were not read


def test_the_bound_rule_mean_plus_one_sd():
    """hard = round(mean + 1 SD), soft = round(mean + 2 SD) for the ends whose mean and SD were read (inputs are the numbers printed in the sources)"""
    cases = [("shoulder_flex", "hi", 170.17, 8.56), ("shoulder_rot", "lo", 81.38, 12.04), ("shoulder_rot", "hi", 60.67, 13.42),
             ("wrist_flex", "lo", 71.1, 4.9), ("wrist_flex", "hi", 74.2, 5.1), ("wrist_dev", "lo", 34.0, 3.7), ("wrist_dev", "hi", 19.7, 3.0),
             ("ankle_dp", "hi", 20.0, 9.0), ("cerv_flex", "lo", 59.1, 10.2), ("cerv_flex", "hi", 57.7, 8.2), ("cerv_lat", "lo", 41.75, 7.8), ("cerv_lat", "hi", 41.75, 7.8),
             ("cerv_rot", "lo", 70.65, 10.1), ("cerv_rot", "hi", 70.65, 10.1), ("thor_flex", "lo", 12.8, 7.6)]
    for k, w, m, sd in cases:
        e = rom.ROM_EVID[k][w]
        s = -1 if w == "lo" else 1
        assert e["new"] == s * _r(m + sd), (k, w, e["new"], m + sd)
        assert e["soft"] == s * _r(m + 2 * sd), (k, w, e["soft"], m + 2 * sd)
        assert e["st"] in V
    for k, w, e in rom.ends():                                  # a soft limit only where an SD was read, and always outside the hard bound
        if e["soft"] is not None:
            assert e["st"] in V and abs(e["soft"]) >= abs(e["new"]), (k, w)
    # mean-only bounds: the mean of the larger multi-sex sample
    assert rom.ROM_EVID["hip_flex"]["hi"]["new"] == _r((133.8 + 130.4) / 2) and rom.ROM_EVID["hip_flex"]["lo"]["new"] == -_r((18.1 + 17.4) / 2)
    assert rom.ROM_EVID["knee_flex"]["hi"]["new"] == _r((141.9 + 137.7) / 2)
    assert rom.ROM_EVID["hip_rot"]["lo"]["new"] == -_r((38.5 + 41.8 + 40.6) / 3) and rom.ROM_EVID["hip_rot"]["hi"]["new"] == _r((29.6 + 35.2 + 37.9) / 3)
    assert rom.ROM_EVID["forearm_sup"]["lo"]["new"] == -(80 + 4) and rom.ROM_EVID["forearm_sup"]["hi"]["new"] == 87 + 4


def test_changes_old_vs_new():
    ch = {(k, w): (e["old"], e["new"]) for k, w, e in rom.changed()}
    want = {("cerv_flex", "lo"): (-45, -69), ("cerv_flex", "hi"): (45, 66), ("cerv_rot", "hi"): (60, 81), ("hip_flex", "lo"): (-30, -18), ("hip_flex", "hi"): (120, 132),
            ("hip_rot", "hi"): (45, 34), ("hip_abd", "hi"): (45, 39), ("knee_flex", "hi"): (135, 140), ("ankle_dp", "hi"): (20, 29), ("thumb_cmc_abd", "hi"): (70, 42),
            ("wrist_dev", "lo"): (-30, -38), ("forearm_sup", "hi"): (80, 91), ("shoulder_flex", "hi"): (180, 179)}
    for k, v in want.items():
        assert ch[k] == v, k
    assert len(ch) == 23
    # unchanged AAOS values that the sources support within a few degrees
    for k in (("elbow_flex", "hi"), ("wrist_flex", "hi")):
        assert k not in ch or abs(ch[k][1] - ch[k][0]) <= 1
    doc = (REPO / "docs/pose_rom_table.md").read_text(encoding="utf-8")
    assert "## Old versus new" in doc and "180 -> **179**" in doc and "70 -> **42**" in doc


def test_coupled_motions_documented():
    txt = " ".join(c[0] + c[1] for c in rom.COUPLED)
    for w in ("KNEE", "scapulohumeral", "Hip rotation", "Knee rotation", "Forearm rotation", "1.7 : 1", "4 +- 7", "35 / 40 / 44"):
        assert w in txt, w


def test_documentation_states_what_was_and_was_not_read():
    doc = (REPO / "docs/pose_rom_table.md").read_text(encoding="utf-8")
    for w in ("How honest is this table", "abstract only (number not verified)", "secondary snippet only", "mean + 1 SD", "mean + 2 SD", "Joint-axis definitions versus the ISB", "could not be fetched",
              "PMID 22964130", "doi:10.1186/1471-2474-15-246", "Grood-Suntay"):
        assert w in doc, w
    c = {k: sum(1 for _, _, e in rom.ends() if e["st"] == k) for k in rom.STATUS}
    n = sum(c.values())
    assert "**verified from source (full text)** - %d of %d" % (c["V_FT"], n) in doc
    assert "**abstract only (number not verified)** - %d of %d" % (c["AO"], n) in doc


def test_rigs_carry_the_new_bounds_and_the_evidence():
    files = sorted((REPO / "data/anatomy").glob("pose_rig_*.json"))
    assert len(files) == 6
    for f in files:
        rig = json.loads(f.read_text(encoding="utf-8"))["rig"]
        assert set(rig["rom"]) == set(rig["rom_meta"]) and rig["rom"], f.name
        for k, r in rig["rom"].items():
            assert r[:2] == [rom.ROM[k][0], rom.ROM[k][1]] and r[3] == rom.ROM[k][3], (f.name, k)
            m = rig["rom_meta"][k]
            assert m["old"] == [rom.ROM_EVID[k]["lo"]["old"], rom.ROM_EVID[k]["hi"]["old"]] and m["st"] == [rom.ROM_EVID[k]["lo"]["st"], rom.ROM_EVID[k]["hi"]["st"]], (f.name, k)
        # the sliders really use the Q245 numbers
        for j in rig["joints"]:
            if j["id"].startswith("hip_"):
                d = {x["k"]: x for x in j["dof"]}
                assert (d["flex"]["lo"], d["flex"]["hi"]) == (-18, 132) and (d["rot"]["lo"], d["rot"]["hi"]) == (-40, 34), (f.name, j["id"])
            if j["id"].startswith("knee_"):
                assert j["dof"][0]["hi"] == 140
        reg = {r["id"]: r for r in rig["regions"]}
        c = {x["k"]: x for x in reg["cervical"]["dof"]} if "cervical" in reg else {}
        if c:
            assert (c["flex"]["lo"], c["flex"]["hi"]) == (-69, 66) and (c["rot"]["lo"], c["rot"]["hi"]) == (-81, 81)
    for key in ("own_m", "own_f", "comb_m", "comb_f", "base_m", "base_f"):
        rep = json.loads((REPO / ("data/derived/Q241_rig_%s.json" % key)).read_text(encoding="utf-8"))
        assert "rest_values_outside_range" in rep


def test_asymmetry_thresholds_are_checked_against_the_literature_and_unchanged():
    import asym
    assert asym.GROUP_THR == {"shoulder": 5.0, "elbow": 5.0, "forearm": 8.0, "wrist": 5.0, "fingers": 8.0, "hip": 5.0, "knee": 5.0, "ankle": 5.0, "toes": 8.0, "pelvis": 3.0, "spine": 3.0, "head": 5.0}
    md = (REPO / "data/derived/Q241_pose_asymmetry.md").read_text(encoding="utf-8")
    assert "2.1 What the literature justifies" in md
    for w in ("Zwerus 2019", "Vairo 2012", "Macedo & Magee 2008", "Conte 2009", "Biaggi 2021", "Kouyoumdjian 2012", "Elveru 1988", "not a 95% limit", "NOT recomputed", "NOT supported by the three citations"):
        assert w in md, w
    assert "justified" in md and "assumption" in md
