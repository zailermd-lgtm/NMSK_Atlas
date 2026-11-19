"""Q368: the name card's colour swatch + ADD menu, and the antagonist table behind ADD -> Antagonist group."""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ANT = json.loads((REPO / "data/anatomy/antagonist_groups_q368.json").read_text(encoding="utf-8"))
REL = {p: json.loads((REPO / f"data/derived/Q298_relations_{p}.json").read_text(encoding="utf-8")) for p in ("base_m", "base_f")}
JS = (REPO / "viewer/quickcard/quickcard.js").read_text(encoding="utf-8")
SEL = (REPO / "viewer/selection/selection.js").read_text(encoding="utf-8")
ZAN = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")


def groups(p):
    d = REL[p]
    return {g["id"]: {d["ids"][i] for i in g["i"]} for g in d["fgroups"]}


def test_table_is_current():
    r = subprocess.run([sys.executable, str(REPO / "scripts/anatomy/q368/build_antagonists_q368.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_pairs_symmetric_unique_and_not_self():
    seen = set()
    for p in ANT["pairs"]:
        assert p["a"] != p["b"]
        k = frozenset((p["a"], p["b"]))
        assert k not in seen, k
        seen.add(k)
    # an undirected record is symmetric by construction; the page reads it both ways (pr.a === g ? pr.b : pr.b === g ? pr.a)
    assert "pr.a === g.id ? pr.b : pr.b === g.id ? pr.a" in JS


def test_every_pair_cited():
    for p in ANT["pairs"]:
        assert p["refs"], p
        for r in p["refs"]:
            assert r["book"] in ANT["books"] and re.fullmatch(r"\d{1,4}", r["page"]) and len(r["note"]) > 20, (p["a"], p["b"], r)
    for g in ANT["added_groups"].values():
        assert g["refs"] and all(r["book"] in ANT["books"] and r["page"] for r in g["refs"])


def test_members_exist_on_both_pages():
    for p in REL:
        G = groups(p)
        for pr in ANT["pairs"]:
            for k in (pr["a"], pr["b"]):
                assert k in G or k in ANT["added_groups"], (p, k)
                if k in G:
                    assert len(G[k]) >= 2, (p, k)
        ids = set(REL[p]["ids"])
        for gid, g in ANT["added_groups"].items():
            got = [x for b in g["members"] for x in (b + "_l", b + "_r") if x in ids]
            assert len(got) == 2 * len(g["members"]), (p, gid, got)


def test_every_group_paired_or_explained():
    G = set(groups("base_m")) & set(groups("base_f"))
    paired = {x for pr in ANT["pairs"] for x in (pr["a"], pr["b"])}
    assert not (paired & set(ANT["none"]))
    assert G <= paired | set(ANT["none"])
    assert all(len(v) > 20 for v in ANT["none"].values())


def test_biceps_antagonist_is_elbow_extensors():
    G = groups("base_m")
    opp = {pr["b"] if pr["a"] == "act_elbow_flex_p" else pr["a"] for pr in ANT["pairs"] if "act_elbow_flex_p" in (pr["a"], pr["b"])}
    assert opp == {"act_elbow_flex_n"}
    assert "biceps_brachii_l" in G["act_elbow_flex_p"]
    assert any("triceps" in x for x in G["act_elbow_flex_n"]) and "anconeus_l" in G["act_elbow_flex_n"]


def test_sidecar_ships_the_table():
    t = (REPO / "scripts/anatomy/q342/build_sidecar_q342.py").read_text(encoding="utf-8")
    assert '"ant": build_ant(C)' in t and "antagonist_groups_q368.json" in t


def test_card_reuses_the_one_colour_store_and_the_engine_colour():
    assert 'c.setUserColour(hex, "ids", ids)' in JS                  # the selection controller's ucol, not a second store
    assert 'if (scope === "ids")' in SEL and "palette:function()" in SEL
    assert "colour:function(id){ var o = objsById[id]" in ZAN and "var c = colOf(o)" in ZAN
    assert 'markIds(ids, true, false, true)' in JS                   # ADD adds (replace = false), one undo step


def test_public_ban_list():
    bad = re.compile(r"ultrasound|hounsfield|t1_se|imaging_tissues|tissue table|nmskultrasound|acoustic|mrayl|b-mode", re.I)
    for f in ("viewer/quickcard/quickcard.js", "viewer/quickcard/quickcard.css", "data/anatomy/antagonist_groups_q368.json"):
        assert not bad.search((REPO / f).read_text(encoding="utf-8")), f
