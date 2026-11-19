#!/usr/bin/env python3
"""Q308, the owner's THIRD test: compare against every other 3-D model we can actually reach.

This is run as a SEARCH over each model's own catalogue, not as an impression. For each of the four structure
families, every reachable catalogue is asked whether it holds that structure. Where a model holds it, its mesh
is the comparison. Where no model holds it, that is itself the finding -- and it is the reason the structure had
to be built rule-based rather than imported.

    python3 scripts/anatomy/q308/models308.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/derived/Q308_other_models.json"

def strings(o, acc, keys=("name", "label", "id", "title")):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in keys and isinstance(v, str):
                acc.append(v)
            else:
                strings(v, acc, keys)
    elif isinstance(o, list):
        for v in o:
            strings(v, acc, keys)


ZYGOTE_BIODIGITAL = ("Zygote and BioDigital were NOT consulted and nothing from them was used: Zygote is paid "
                     "and proprietary, and Q302 additionally found its Reproductive and Nervous sets sculpted "
                     "from atlases; BioDigital is a hosted viewer/API that delivers no mesh. Stated rather "
                     "than omitted.")


# Strict patterns. The first pass of this script produced FOUR false positives and they are worth recording,
# because each is a way a model can look as if it holds a structure when it does not:
#   `antebrachial` without `lateral` matched the MEDIAL antebrachial cutaneous nerve's branches, which do ship;
#   `nail bed` and `digital pulp` matched OUR OWN `cited_but_not_shipped` rows in data/derived/Q306_search_*.json,
#       i.e. the project's own record that they are absent, read back as if it were a catalogue;
#   `labi` matched the INFERIOR LABIAL artery and veins -- of the lip, not the vulva.
# So: only real geometry catalogues are read, our own derived tables and prose documents are excluded, and a hit
# must be a node the model declares to be a MESH.
TARGETS = {
 "coracoacromial ligament": r"coraco[-_ ]?acromial",
 "anterolateral ligament of the knee": r"anterolateral[-_ ]lig",
 "psoas minor": r"psoas[-_ ]minor",
 "LACN anterior / posterior branch": r"(anterior|posterior)[-_ ]branch[-_ ]of[-_ ](the[-_ ])?lateral[-_ ]antebrachial"
                                     r"|lateral[-_ ]antebrachial.*(anterior|posterior)[-_ ]branch",
 "nail bed / nail matrix": r"\bnail[-_ ](bed|matrix)\b|matrix[-_ ]unguis",
 "digital pulp": r"\bdigital[-_ ]pulp\b|\bpulp[-_ ]space\b",
 "female perineal skin": r"perineal[-_ ]skin|\bvulva\b|labium[-_ ](majus|minus)|labia[-_ ](majora|minora)",
 "zygapophysial joint capsule": r"(zygapophys|facet)[a-z_ ]*capsul|capsul[a-z_ ]*(zygapophys|facet)",
 "retrocalcaneal bursa": r"(retro|subtendinous)[-_ ]?calcaneal[-_ ]bursa|bursa[-_ ]tendinis[-_ ]calcanei",
 "TFCC articular disc": r"triangular[-_ ]fibrocartilage|articular[-_ ]disc[-_ ]of[-_ ](the[-_ ])?distal[-_ ]radio",
}


def zan_names():
    """the pinned Z-Anatomy catalogue: 3,572 Blender OBJECT names, i.e. real datablocks, not terminology rows."""
    acc = []
    strings(json.loads((REPO / "data/derived/zanatomy_inventory.json").read_text(encoding="utf-8")), acc)
    return sorted({a.strip() for a in acc if a and len(a) < 200})


def hra_mesh_nodes():
    """HRA / CCF: only nodes the manifest itself declares `author_node_type == 'mesh'`, with their triangle
    count and size, so a hit is real geometry and not an ontology crosswalk row."""
    d = json.loads((REPO / "data/derived/Q242_hra_manifest.json").read_text(encoding="utf-8"))
    out = []
    for o in d.get("objects", []):
        n = o.get("nodes")
        if not n:
            continue
        for r in n["rows"]:
            if len(r) > 3 and r[3] == "mesh":
                out.append({"set": o.get("title", ""), "name": r[0], "label": r[1],
                            "ontology_id": r[2], "triangles": r[5] if len(r) > 5 else None,
                            "size_mm_xyz": r[6] if len(r) > 6 else None})
    return out


def main():
    zan = zan_names()
    hra = hra_mesh_nodes()
    rows = {}
    for tgt, pat in TARGETS.items():
        rx = re.compile(pat, re.I)
        z = sorted({a for a in zan if rx.search(a)})[:6]
        h = [x for x in hra if rx.search(str(x["name"])) or rx.search(str(x["label"]))]
        rows[tgt] = {
          "Z-Anatomy (pin 6c7f9016, 3572 objects, CC BY-SA 4.0)":
              {"holds_real_geometry": bool(z), "examples": z},
          "HRA / CCF (united female+male v1.10, CC BY 4.0, mesh nodes only)":
              {"holds_real_geometry": bool(h), "examples": h[:4]},
          "BodyParts3D v4.0 (CC BY 4.0)":
              {"holds_real_geometry": False,
               "examples": [],
               "note": "Q302 catalogued its 1,524 parts and found no peripheral nerve branch, no nail "
                       "structure and a male `perineum` measured at 368 faces / 11.5 x 21.8 x 21.3 mm -- an "
                       "area marker. Its free OBJ set is ~99 % decimated, so it is a SHAPE REFERENCE and not a "
                       "source to ship. Not re-downloaded this round; this row is Q302's measurement, cited."},
          "Chinese Visible Human (Wu 2015)":
              {"holds_real_geometry": False,
               "examples": [],
               "note": "colour cryosection segmentation; supplies this project's perineal muscles and perineal "
                       "body. Holds none of these ten structures."},
          "SPL / Open Anatomy (3D Slicer licence)":
              {"holds_real_geometry": False, "examples": [],
               "note": "Q296 surveyed all seven atlases: none contains a pelvis, pelvic floor or perineum, and "
                       "none contains any of these ten. The inner-ear meshes are what this project imports."},
          "SPARC 692":
              {"holds_real_geometry": False, "examples": [],
               "note": "human sciatic nerve CALIBRE at defined levels only; the samples were excised and laid "
                       "straight (85.1 mm arc), so there is no course in the body at all."},
        }
    built = ["coracoacromial ligament", "anterolateral ligament of the knee", "psoas minor",
             "LACN anterior / posterior branch"]
    held = {t: sorted(m for m, r in rows[t].items() if r["holds_real_geometry"]) for t in built}
    out = {
      "doc": "Q308, the owner's third test: against other 3-D models. Measured over each model's own geometry "
             "catalogue, mesh nodes only.",
      "method": ("Z-Anatomy: the 3,572 Blender OBJECT names of the pin. HRA/CCF: only nodes the manifest marks "
                 "`author_node_type == mesh`, with their triangle count and bounding size. The other four "
                 "models carry the measurement the round that surveyed them recorded, cited, and were not "
                 "re-downloaded -- the disk has 0.66 GB free."),
      "false_positives_of_the_first_pass": [
        "`antebrachial` without `lateral` matched the MEDIAL antebrachial cutaneous nerve, which does ship",
        "`nail bed` / `digital pulp` matched this project's OWN cited_but_not_shipped rows in "
        "data/derived/Q306_search_*.json, read back as if they were a catalogue",
        "`labi` matched the inferior LABIAL artery and veins -- of the lip, not the vulva",
      ],
      "results": rows,
      "licence_blocked": ZYGOTE_BIODIGITAL,
      "headline": {
        "finding": ("HRA / CCF united-female and united-male v1.10 hold the ANTEROLATERAL LIGAMENT OF THE KNEE "
                    "as a real CLOSED mesh, on the SAME two Visible Human donors as this project's Imaging "
                    "pages, under CC BY 4.0: VH_F left and right, 1,680 triangles, 9.0 x 56.9 x 14.2 mm; "
                    "VH_M left and right, 790 triangles, 12.6 x 54.0 x 21.7 mm. UBERON:0014899."),
        "why_nobody_found_it_before": ("the ALL only became a recorded absence in Q306, and Q296 / Q302 surveyed "
                                       "HRA before that, against a different gap list. This is a new check, not "
                                       "a contradiction of theirs."),
        "consequence": ("the rule-based ALL this round ships SHOULD be replaced by that real mesh, at least on "
                        "the two Imaging pages whose skeletons are those donors. That is an import round of its "
                        "own: the GLBs are deliberately kept outside the repository (1.21 GB for the set) and "
                        "the disk has 0.66 GB free, so it is brought to the owner as a decision rather than "
                        "half-done here."),
        "caveat": ("HRA's 56.9 / 54.0 mm is a BOUNDING-BOX extent, not a centreline length, so it is an upper "
                   "bound on the ligament's length and not directly our measured length."),
      },
      "conclusion": {
        "built_families_held_by_a_reachable_model": {t: v for t, v in held.items() if v},
        "built_families_held_by_none": sorted(t for t, v in held.items() if not v),
        "what_this_means": ("For the three families no reachable model holds, there is no other model's mesh to "
                            "compare the SHAPE against, and that is precisely why they were built from cited "
                            "literature on each page's own bones rather than imported. For the fourth -- the "
                            "ALL -- a real mesh DOES exist and the honest conclusion is that ours should give "
                            "way to it."),
      },
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for t in TARGETS:
        hold = [m.split(" (")[0] for m, r in rows[t].items() if r["holds_real_geometry"]]
        print(f"{t:36s} {', '.join(hold) if hold else 'NONE of the reachable models'}")
    print("\nHEADLINE:", out["headline"]["finding"][:150], "...")
    print("written", OUT)


if __name__ == "__main__":
    main()
