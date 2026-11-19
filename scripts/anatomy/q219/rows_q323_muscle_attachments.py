"""Q323 rows: a muscle-level ORIGIN and INSERTION for every muscle record in data/muscles/*/*.json that the parts table did not
already place, generated from the record's own authored `attachments` (origin_bone / origin_landmark / insertion_bone /
insertion_landmark) and citing the record's own `source` string verbatim (as rows_q256_attachments.py does for tendons, ligaments
and fascia). Imported LAST by build_parts.py / build_geometry.py, so it can see every earlier row.

Rules (no guessing):
- A row is not added when the table already has a row of the same type for that structure WITH a geometry rule (curated Q219/Q222
  rows win; no duplicate point). Rows of the same type without geometry (sub-slips, arms, text) do not block the muscle-level row.
- Geometry: `end_snap_bone` with `other_bone` (the record's other attachment bone): the two ends of the muscle's own mesh are assigned
  to the two named bones by the lower total gap (build_geometry._two_bone_end), no proximal/distal convention. tol 8 mm (as the
  curated muscle rows), error bound <= 40 mm, snapped point <= 10 mm from the muscle end. One point per named bone field (the record
  schema names exactly one origin bone and one insertion bone); a bone GROUP ('ribs', 'phalanges_hand' ...) resolves to its member
  bones and the point lands on the member the mesh end touches. A second bone named only in the landmark text is not placed.
- No geometry (text only, with the reason) when: the record's bone is a placeholder (its landmark says the true attachment is
  cartilage/skin), the record is midline, or the record covers several separate Z part meshes (its text is not specific to one).
"""
from __future__ import annotations
import glob
import json
import re
from pathlib import Path

import rows_common
from rows_common import P
from rows_q256_attachments import refs_for

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SIDE = re.compile(r"_(r|l)$")
SIDE_TOK = re.compile(r"\b([a-z0-9]+(?:_[a-z0-9]+)*?)_(?:l|r)\b")
PLACEHOLDER = "schema takes a bone id"
TOL, MAX_ERR = 8, 40
# record -> Z mesh base of another name: (a) where the Base pages themselves attach the record to that mesh; (b) the same muscle under a
# Terminologia Anatomica synonym / spelling in Z-Anatomy (cervicis = colli, buccinator = bucinator, lumbricals = lumbrical muscles ...),
# whole-muscle meshes only (a Z mesh of one PART of the muscle, e.g. zan_occipitalis_muscle for occipitofrontalis, is not aliased)
MESH_ALIAS = {"palmaris_longus": "zan_palmaris_longus_muscle", "temporalis": "zan_temporalis_muscle",
              "tibialis_posterior": "zan_tibialis_posterior_muscle",
              "buccinator": "zan_bucinator", "lateral_cricoarytenoid": "zan_lateral_crico_arytenoid_muscle",
              "posterior_cricoarytenoid": "zan_posterior_crico_arytenoid_muscle", "lumbricals_hand": "zan_lumbrical_muscles_of_hand",
              "lumbricals_foot": "zan_lumbrical_muscles_of_foot", "semispinalis_cervicis": "zan_semispinalis_colli_muscle",
              "splenius_cervicis": "zan_splenius_colli_muscle", "stapedius": "oa_stapedius",
              "external_intercostals": "zan_external_intercostal_muscles", "internal_intercostals": "zan_internal_intercostal_muscles",
              "innermost_intercostals": "zan_innermost_intercostal_muscles"}
# records the Base pages attach to SEVERAL separate Z part meshes (heads / parts): the record's text is for the whole muscle
SPLIT_IN_Z = {"deltoid": 3, "triceps_brachii": 3, "pectoralis_major": 3, "iliopsoas": 2}


def unside(s: str) -> str:
    return SIDE_TOK.sub(r"\1", s or "")


recs: dict[str, dict] = {}
for f in sorted(glob.glob(str(REPO / "data/muscles/*/*.json"))):
    d = json.load(open(f))
    if not isinstance(d, dict) or "attachments" not in d:
        continue
    b = SIDE.sub("", d["id"])
    if b not in recs or d["id"].endswith("_r"):
        recs[b] = d

ruled = {(r["structure_id"], r["part_type"]) for r in rows_common.ROWS if (r.get("geometry") or {}).get("rule")}
report = {"records": len(recs), "rows_added": 0, "skipped_already_placed": [], "text_only": {}}

for sid, rec in sorted(recs.items()):
    a = rec["attachments"]
    sided = bool(SIDE.search(rec["id"]))
    source = rec.get("source", "")
    refs = refs_for(source)
    nm = rec.get("name_common") or rec.get("name_ta") or sid
    ob, ib = SIDE.sub("", a["origin_bone"]), SIDE.sub("", a["insertion_bone"])
    ol, il = unside(a["origin_landmark"]), unside(a["insertion_landmark"])
    o_ok, i_ok = PLACEHOLDER not in a["origin_landmark"], PLACEHOLDER not in a["insertion_landmark"]
    note = ("Muscle-level attachment from this project's own record (data/muscles), generated in Q323; the bone is the record's "
            f"origin_bone / insertion_bone, the text its landmark. Source (verbatim): {source}")
    for ptype, slug, bone, other, land, ok, oth_ok, word in (("origin_part", "origin_q323", ob, ib, ol, o_ok, i_ok, "Origin"),
                                                             ("insertion_point", "insertion_q323", ib, ob, il, i_ok, o_ok, "Insertion")):
        if (sid, ptype) in ruled:
            report["skipped_already_placed"].append(f"{sid}.{ptype}")
            continue
        why = None
        if not sided:
            why = "midline record: the per-side resolver would duplicate one point as r and l (as Q256)"
        elif not ok:
            why = "the record's bone is a placeholder: its landmark says the true attachment is cartilage / skin, not the named bone"
        elif sid in SPLIT_IN_Z:
            why = f"the record covers {SPLIT_IN_Z[sid]} separate Z part meshes on the Base pages; its text is not specific to one of them"
        geom = None if why else dict(rule="end_snap_bone", bone=bone, other_bone=other if oth_ok else None, tol_mm=TOL, max_err_mm=MAX_ERR,
                                     **({"mesh": MESH_ALIAS[sid]} if sid in MESH_ALIAS else {}))
        if why:
            geom = dict(rule=None, why=why)
            report["text_only"][f"{sid}.{slug}"] = why
        P(sid, slug, ptype, f"{word}: {land or bone}", f"{nm}: {word.lower()} on the {bone.replace('_', ' ')} ({land}).", refs,
          cls="muscle", ver="unverified", ev="textbook", anchor=dict(bone=bone, landmark=land), geom=geom, note=note)
        report["rows_added"] += 1

(REPO / "data/derived/Q323_muscle_attachment_rows.json").write_text(json.dumps(report, indent=1) + "\n")
