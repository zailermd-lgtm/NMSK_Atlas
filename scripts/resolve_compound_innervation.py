#!/usr/bin/env python3
"""Turn packed innervation strings into the nerve ids they stand for.

THE DEFECT. innervation.nerve was a single string, and 64 muscles have more
than one nerve. Their value was a pseudo-id that packed both together --
'femoral_n_and_obturator_n', 'median_n_1_2_ulnar_n_3_4',
'tibial_part_of_sciatic_n_long_head_common_fibular_part_short_head' -- and
resolved to nothing. The validator carried an allow-list excusing exactly
those strings, so 64 muscles pointed at no nerve and the checks said that
was fine. The anatomy underneath is right, and is written in prose on each
compartment: "tibial division of sciatic n.", "ulnar n., deep branch".

THE FIX, IN THAT ORDER OF PREFERENCE.

  1. Derived. Where a nerve entity already lists the compartment in its
     targets, that is the link, from the other end. Most of the 22 packed
     values resolve this way with nothing authored at all: the tree already
     carries sciatic_n_branch_to_biceps_femoris_short_head and
     obturator_n_branch_to_adductor_magnus_adductor_part.

  2. Reviewed. Ten muscles have compartments no nerve targets. Each of those
     is resolved below from the compartment's own prose to an id that exists
     in the tree -- "ulnar n., deep branch" to ulnar_n_deep_branch -- and the
     prose is checked to still say what the table assumes it says.

Each compartment gets innervation_branch_ids; the muscle gets the union as a
list. Nothing is written if any id fails to resolve.

THE SCIATIC NERVE IS LEFT AS IT IS. Its hamstring branches hang off the
undivided trunk, with the tibial/common-fibular split modelled only from the
popliteal fossa down. That is a documented decision in the tree, not an
oversight: the note on common_fibular_n says exactly where the short head's
supply comes from. Re-parenting the branches would contradict where tibial_n
is modelled to begin. The division each head answers to stays in the prose
on the compartment, where it already was.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

_SIDE = re.compile(r"_(r|l)(?=_|$)")

# The eleven muscular branches to the intercostal spaces, T1-T11.
INTERCOSTAL_SERIES = (
    [f"intercostal_n_t{i}_muscular" for i in range(1, 7)]
    + [f"thoracoabdominal_n_t{i}_intercostal_muscular" for i in range(7, 12)])

# compartment id with the side token removed -> (ids, phrase the compartment's
# own prose must contain, so the table cannot silently outlive an edit to it)
REVIEWED = {
    "sternocleidomastoid_sternal":
        (["accessory_n_scm_branch", "cervical_plexus_root_C2",
          "cervical_plexus_root_C3"], "accessory n."),
    "sternocleidomastoid_clavicular":
        (["accessory_n_scm_branch", "cervical_plexus_root_C2",
          "cervical_plexus_root_C3"], "accessory n."),
    "trapezius_upper":
        (["accessory_n_trapezius_branch", "cervical_plexus_root_C3",
          "cervical_plexus_root_C4"], "accessory n."),
    "trapezius_middle":
        (["accessory_n_trapezius_branch", "cervical_plexus_root_C3",
          "cervical_plexus_root_C4"], "accessory n."),
    "trapezius_lower":
        (["accessory_n_trapezius_branch", "cervical_plexus_root_C3",
          "cervical_plexus_root_C4"], "accessory n."),
    "iliopsoas_psoas_major":
        (["lumbar_root_L1", "lumbar_root_L2", "lumbar_root_L3"],
         "lumbar plexus"),
    "coccygeus_main":
        (["sacral_root_S3", "sacral_root_S4"], None),
    "internal_oblique_inferior_conjoint":
        (["iliohypogastric_n", "ilioinguinal_n"], "iliohypogastric"),
    "transversus_abdominis_inferior_conjoint":
        (["iliohypogastric_n", "ilioinguinal_n"], "iliohypogastric"),
    "levator_ani_puborectalis":
        (["sacral_root_S3", "sacral_root_S4"], "direct sacral"),
    "levator_ani_pubococcygeus": (["pudendal_n"], "pudendal"),
    "levator_ani_iliococcygeus": (["pudendal_n"], "pudendal"),
    "levator_scapulae_main":
        (["dorsal_scapular_n", "cervical_plexus_root_C3",
          "cervical_plexus_root_C4"], None),
    "quadratus_lumborum_iliolumbar":
        (["lumbar_root_T12", "lumbar_root_L1", "lumbar_root_L2",
          "lumbar_root_L3"], "T12-L3"),
    "flexor_pollicis_brevis_superficial":
        (["median_n_recurrent_thenar_branch"], "recurrent"),
    "flexor_pollicis_brevis_deep": (["ulnar_n_deep_branch"], "deep branch"),
    "lumbricals_hand_1_2": (["median_n_palmar_digital_nn"], "median"),
    "lumbricals_hand_3_4": (["ulnar_n_lumbrical_branches"], "ulnar"),
}


def unsided(comp_id: str) -> str:
    return _SIDE.sub("", comp_id, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    nerve_ids, targets_of = set(), defaultdict(set)
    for path in (DATA_DIR / "nerves").glob("*.json"):
        for n in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(n, dict) and "id" in n:
                nerve_ids.add(n["id"])
                for t in n.get("targets") or []:
                    if isinstance(t, str):
                        targets_of[t].add(n["id"])

    plans, problems = [], []
    for path in sorted((DATA_DIR / "muscles").rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        muscles = payload if isinstance(payload, list) else [payload]
        changed = False
        for m in muscles:
            if not isinstance(m, dict) or "id" not in m:
                continue
            packed = (m.get("innervation") or {}).get("nerve")
            if not isinstance(packed, str) or packed in nerve_ids:
                continue
            union = []
            for c in m.get("functional_compartments") or []:
                ids = sorted(targets_of.get(c["id"], ()))
                how = "derived"
                if not ids:
                    key = unsided(c["id"])
                    if key in REVIEWED:
                        ids, must_say = REVIEWED[key]
                        prose = c.get("innervation_branch") or ""
                        if must_say and must_say.lower() not in prose.lower():
                            problems.append(
                                f"{c['id']}: reviewed as {ids} on the strength of "
                                f"prose saying {must_say!r}, but the prose now "
                                f"reads {prose!r}")
                        how = "reviewed"
                    elif packed == "intercostal_nerves":
                        ids, how = list(INTERCOSTAL_SERIES), "series"
                    else:
                        problems.append(f"{c['id']}: no nerve targets it and no "
                                        f"reviewed resolution ({packed})")
                        continue
                missing = [i for i in ids if i not in nerve_ids]
                if missing:
                    problems.append(f"{c['id']}: {missing} are not nerve entities")
                    continue
                c["innervation_branch_ids"] = list(ids)
                for i in ids:
                    if i not in union:
                        union.append(i)
                print(f"  {c['id']:44} {how:8} {ids if len(ids) < 4 else str(len(ids)) + ' ids'}")
            if len(union) >= 2:
                m["innervation"]["nerve"] = union
            elif len(union) == 1:
                m["innervation"]["nerve"] = union[0]
            else:
                problems.append(f"{m['id']}: no compartment resolved")
                continue
            m["innervation"]["was_packed_as"] = packed
            changed = True
        if changed:
            plans.append((path, payload))

    print(f"\n{len(plans)} muscle files would change")
    if problems:
        print(f"\n{len(problems)} problem(s); nothing written:")
        for p in problems:
            print(f"    {p}")
        return 1
    if not args.write:
        print("\nPass --write to apply.")
        return 0
    for path, payload in plans:
        path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(plans)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
