#!/usr/bin/env python3
"""Q368: the antagonist table of the functional groups -> data/anatomy/antagonist_groups_q368.json.

Owner (2026-11-17, translated): the name card gets an "ADD" button that adds "functional group, opposing (antagonist)
functional group, adjacent tissues" to the marked set. The functional groups are the ones the card already offers
(Related structures -> Functional group): the 110 groups of scripts/anatomy/q298/relations_q298.py, ids as in
data/derived/Q298_relations_<page>.json `fgroups` (the same ids on both Base pages).

Every pair is symmetric by construction (a pair is one undirected record) and carries the book statement(s) it rests on:
book key + PRINTED page + a paraphrase (knowledge only, nothing copied). A group with no meaningful antagonist is listed
under `none` with a one-line reason. Where the Q298 set has a motion but not its opposite (the toes), the opposing group
is defined here (`added_groups`), with its membership as the book prints it, and the sidecar resolves it on each page.

    python3 scripts/anatomy/q368/build_antagonists_q368.py          # write the table (validates against both pages' groups)
    python3 scripts/anatomy/q368/build_antagonists_q368.py --check  # exit 1 if the committed table differs
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "anatomy" / "antagonist_groups_q368.json"
REL = {p: REPO / "data" / "derived" / f"Q298_relations_{p}.json" for p in ("base_m", "base_f")}

BOOKS = {
    "mannan2017": {
        "short": "Mannan 2017",
        "citation": "Noor MA. Mannan's Regional Dissection and Surface Anatomy. 14th ed. Jaypee Brothers Medical Publishers, "
                    "New Delhi, 2017. ISBN 978-93-86322-11-1",
        "opened": "owner-supplied PDF with a text layer; pages are the printed page numbers (PDF page = printed + 18)"},
    "sontakke2023": {
        "short": "Sontakke 2023",
        "citation": "Sontakke YA. Textbook of Human Anatomy with Color Atlas and Clinical Integration, Vol. 5: Head, Neck "
                    "and Face (bound with Vol. 6: Brain). CBS Publishers & Distributors, New Delhi, 1st e-book ed. 2023",
        "opened": "owner-supplied PDF with a text layer; pages are the printed page numbers of Vol. 5 (PDF page = printed + 19)"},
}
NOT_USED = [
    {"file": "grays_atlas_of_anatomy.pdf", "why": "image-only scan (no text layer); not usable for this pass"},
    {"file": "lumley_surface_anatomy.pdf", "why": "image-only scan (no text layer); not usable for this pass"},
    {"file": "peripheral_nerves.pdf", "why": "image-only scan (no text layer); not usable for this pass"},
    {"file": "peripheral_nerve_injury_anatomical.pdf", "why": "text layer; a nerve-injury book, its movement lists are "
     "per nerve, not per joint -- Mannan's per-joint tables were used instead"},
    {"file": "pns_interrelationships_variations.pdf", "why": "text layer; nerve variations only, no movement tables"},
    {"file": "fascia_in_sport_and_movement.pdf", "why": "text layer; fascial chains, no per-joint antagonist statements"},
    {"file": "atlas_untitled.pdf", "why": "text layer; neonatal procedures atlas, no muscle actions"},
]


def R(book, page, note):
    return {"book": book, "page": str(page), "note": note}


M, S = "mannan2017", "sontakke2023"
UL = "Functional classification of the upper-limb muscles by joint; a note on the same page defines the antagonist as " \
     "the muscle that opposes the action of the other group (p. 198)."

# Display names for Q298 groups whose generated name hides the motion (the sign of 'rot' / 'dev' in Q283's records).
# Each follows from the group's members against the book list cited in its pair.
LABELS = {
    "act_hip_rot_p": "Medial rotation at the hip joint",
    "act_hip_rot_n": "Lateral rotation at the hip joint",
    "act_shoulder_rot_p": "Medial rotation at the glenohumeral (shoulder) joint",
    "act_shoulder_rot_n": "Lateral rotation at the glenohumeral (shoulder) joint",
    "act_wrist_dev_p": "Radial deviation (abduction) at the radiocarpal (wrist) joint",
    "act_wrist_dev_n": "Ulnar deviation (adduction) at the radiocarpal (wrist) joint",
}

ADDED = {
    "q368_toes_mtp_flex": {
        "name": "Flexion of the lateral four toes at the metatarsophalangeal joints",
        "members": ["flexor_digitorum_brevis", "zan_lumbrical_muscles_of_foot", "plantar_interossei", "dorsal_interossei_foot",
                    "flexor_digitorum_longus", "quadratus_plantae"],
        "refs": [R(M, 299, "Metatarsophalangeal joints: flexion by flexor digitorum brevis, the lumbricals and the interossei "
                           "(prime movers), with flexor digitorum longus and flexor accessorius (quadratus plantae) assisting.")],
        "why": "The Q298 set has extension at the 2nd-4th MTP joints but no flexion group for those toes."},
    "q368_toes_ip_ext": {
        "name": "Extension of the lateral four toes at the interphalangeal joints",
        "members": ["extensor_digitorum_longus", "extensor_digitorum_brevis"],
        "refs": [R(M, 299, "Interphalangeal joints of the foot: the digits are extended by extensor digitorum longus and "
                           "brevis and extensor hallucis longus; the hallux muscle is split off into its own group here.")],
        "why": "The Q298 set has flexion at the PIP / DIP joints of the 2nd-5th toes but no extension group."},
    "q368_hallux_ip_ext": {
        "name": "Extension of the great toe at the interphalangeal joint",
        "members": ["extensor_hallucis_longus"],
        "refs": [R(M, 299, "Interphalangeal joints of the foot: extensor hallucis longus is the long extensor named for the "
                           "great toe in the extension list.")],
        "why": "The Q298 set has flexion at the great toe's IP joint but no extension group."},
}


def P(a, b, movement, refs):
    return {"a": a, "b": b, "movement": movement, "refs": refs}


PAIRS = [
    # ---- upper limb: Mannan 2017 pp. 195-198, "functional classification ... in relation to the joints"
    P("act_shoulder_flex_p", "act_shoulder_flex_n", "shoulder flexion / extension",
      [R(M, 195, "Shoulder joint: flexors (clavicular head of pectoralis major, anterior deltoid, coracobrachialis, biceps) "
                 "and extensors (posterior deltoid, teres major, latissimus dorsi) listed as opposite movements. " + UL)]),
    P("act_shoulder_abd_p", "act_shoulder_abd_n", "shoulder abduction / adduction",
      [R(M, 195, "Shoulder joint: abductors (deltoid, supraspinatus) and adductors (pectoralis major, latissimus dorsi, "
                 "coracobrachialis, teres major, long head of triceps).")]),
    P("act_shoulder_rot_p", "act_shoulder_rot_n", "shoulder medial / lateral rotation",
      [R(M, 196, "Shoulder joint: medial rotators (pectoralis major, anterior deltoid, latissimus dorsi, teres major, "
                 "subscapularis) and lateral rotators (infraspinatus, teres minor, posterior deltoid).")]),
    P("act_elbow_flex_p", "act_elbow_flex_n", "elbow flexion / extension",
      [R(M, 196, "Elbow joint: flexors (biceps, brachialis; pronator teres, brachioradialis) and extensors (triceps, "
                 "anconeus).")]),
    P("act_forearm_sup_p", "act_forearm_sup_n", "supination / pronation",
      [R(M, 196, "Radio-ulnar joints: supinators (supinator, biceps) and pronators (pronator teres, pronator quadratus).")]),
    P("act_wrist_flex_p", "act_wrist_flex_n", "wrist flexion / extension",
      [R(M, 196, "Wrist joint: flexion by flexor carpi radialis and ulnaris and palmaris longus (with the long finger flexors, "
                 "p. 197)."), R(M, 197, "Wrist joint: extension by the radial extensors and extensor carpi ulnaris (with "
                 "extensor digitorum).")]),
    P("act_wrist_dev_p", "act_wrist_dev_n", "wrist abduction (radial deviation) / adduction (ulnar deviation)",
      [R(M, 197, "Wrist joint: adduction by flexor and extensor carpi ulnaris; abduction by flexor carpi radialis and the "
                 "radial extensors.")]),
    P("act_thumb_cmc_flex_p", "act_thumb_cmc_flex_n", "thumb CMC flexion / extension",
      [R(M, 197, "Carpometacarpal joint of the thumb: flexion (flexor pollicis brevis, opponens; flexor pollicis longus) and "
                 "extension (extensor pollicis longus and brevis, abductor pollicis longus).")]),
    P("act_thumb_cmc_abd_p", "act_thumb_cmc_abd_n", "thumb CMC abduction / adduction",
      [R(M, 197, "Carpometacarpal joint of the thumb: abduction (abductor pollicis longus and brevis) and adduction "
                 "(adductor pollicis).")]),
    P("act_thumb_mcp_flex_p", "act_thumb_mcp_flex_n", "thumb MCP flexion / extension",
      [R(M, 197, "Metacarpophalangeal joints: flexion movement listed."),
       R(M, 198, "Metacarpophalangeal joints: extension, for the thumb by extensor pollicis longus and brevis.")]),
    P("act_thumb_ip_flex_p", "act_thumb_ip_flex_n", "thumb IP flexion / extension",
      [R(M, 198, "Interphalangeal joints: the thumb is flexed by flexor pollicis longus and extended by extensor pollicis "
                 "longus.")]),
]
for f in (2, 3, 4, 5):
    PAIRS += [
        P(f"act_f{f}_mcp_flex_p", f"act_f{f}_mcp_flex_n", f"finger {f} MCP flexion / extension",
          [R(M, 197, "Metacarpophalangeal joints: flexion by the long finger flexors (prime movers) with lumbricals and "
                     "interossei."), R(M, 198, "Metacarpophalangeal joints: extension by extensor digitorum (with extensor "
                     "indicis / digiti minimi for the index and little finger).")]),
        P(f"act_f{f}_pip_flex_p", f"act_f{f}_pip_flex_n", f"finger {f} PIP flexion / extension",
          [R(M, 198, "Interphalangeal joints: the proximal joint is flexed by flexor digitorum superficialis and profundus; "
                     "extension by extensor digitorum.")]),
        P(f"act_f{f}_dip_flex_p", f"act_f{f}_dip_flex_n", f"finger {f} DIP flexion / extension",
          [R(M, 198, "Interphalangeal joints: the distal joint is flexed by flexor digitorum profundus; extension by "
                     "extensor digitorum.")]),
    ]
LL = "Functional classification of the lower-limb muscles by joint (Movement involved in the inferior extremity)."
PAIRS += [
    # ---- lower limb: Mannan 2017 pp. 296-299
    P("act_hip_flex_p", "act_hip_flex_n", "hip flexion / extension",
      [R(M, 296, "Hip joint: flexion (psoas major, iliacus; pectineus, rectus femoris, sartorius, adductors) and extension "
                 "(gluteus maximus; hamstrings). " + LL)]),
    P("act_hip_abd_p", "act_hip_abd_n", "hip abduction / adduction",
      [R(M, 296, "Hip joint: abduction (gluteus medius and minimus; tensor fasciae latae, sartorius)."),
       R(M, 297, "Hip joint: adduction (adductor longus, brevis and magnus; pectineus, gracilis).")]),
    P("act_hip_rot_p", "act_hip_rot_n", "hip medial / lateral rotation",
      [R(M, 297, "Hip joint: medial rotation (tensor fasciae latae, anterior fibres of gluteus medius and minimus) and lateral "
                 "rotation (obturators, gemelli, quadratus femoris; piriformis, gluteus maximus, sartorius, adductors).")]),
    P("act_knee_flex_p", "act_knee_flex_n", "knee flexion / extension",
      [R(M, 297, "Knee joint: flexion (biceps femoris, semimembranosus, semitendinosus; gracilis, sartorius, popliteus) and "
                 "extension (quadriceps femoris; tensor fasciae latae).")]),
    P("act_ankle_dp_p", "act_ankle_dp_n", "ankle dorsiflexion / plantarflexion",
      [R(M, 298, "Ankle joint: dorsiflexion (tibialis anterior; extensor digitorum longus, extensor hallucis longus, "
                 "peroneus tertius) and plantar flexion (gastrocnemius, soleus; tibialis posterior, the long toe flexors, "
                 "plantaris).")]),
    P("act_subtalar_inv_p", "act_subtalar_inv_n", "inversion / eversion",
      [R(M, 298, "Subtalar and talocalcaneonavicular joints: eversion (peroneus longus, brevis, tertius) and inversion "
                 "(tibialis anterior and posterior).")]),
    P("act_t1_mtp_flex_p", "act_t1_mtp_flex_n", "great toe MTP flexion / extension",
      [R(M, 299, "Metatarsophalangeal joints: flexion and extension listed as opposite movements (extension of the great "
                 "toe by extensor hallucis longus).")]),
    P("act_t5_mtp_flex_p", "act_t5_mtp_flex_n", "little toe MTP flexion / extension",
      [R(M, 299, "Metatarsophalangeal joints: flexion and extension listed as opposite movements.")]),
    P("quadriceps_femoris", "hamstrings", "knee extension / flexion",
      [R(M, 297, "Knee joint: the hamstrings (biceps femoris, semimembranosus, semitendinosus) are the prime flexors and "
                 "quadriceps femoris the prime extensor.")]),
    P("triceps_surae", "leg_anterior", "ankle plantarflexion / dorsiflexion",
      [R(M, 298, "Ankle joint: gastrocnemius and soleus are the prime plantar flexors (plantaris assisting); the dorsiflexors "
                 "are the anterior-compartment muscles (tibialis anterior, extensor digitorum longus, extensor hallucis "
                 "longus, peroneus tertius).")]),
    P("leg_lateral", "act_subtalar_inv_p", "eversion / inversion",
      [R(M, 298, "Subtalar joint: the peroneal (fibular) muscles evert the foot; tibialis anterior and posterior invert it.")]),
    P("hip_adductors", "act_hip_abd_p", "hip adduction / abduction",
      [R(M, 296, "Hip joint: abductors (gluteus medius and minimus; tensor fasciae latae, sartorius)."),
       R(M, 297, "Hip joint: adductors (adductor longus, brevis, magnus; pectineus, gracilis).")]),
    P("deep_gluteal", "act_hip_rot_p", "hip lateral / medial rotation",
      [R(M, 297, "Hip joint: the short lateral rotators (obturators, gemelli, quadratus femoris; piriformis) against the "
                 "medial rotators (tensor fasciae latae, anterior fibres of gluteus medius and minimus).")]),
]
for t in (2, 3, 4):
    PAIRS.append(P(f"act_t{t}_mtp_flex_n", "q368_toes_mtp_flex", f"toe {t} MTP extension / flexion",
                   [R(M, 299, "Metatarsophalangeal joints: extension by extensor digitorum longus and brevis against flexion "
                              "by flexor digitorum brevis, lumbricals and interossei (flexor digitorum longus and accessorius "
                              "assisting).")]))
for t in (2, 3, 4, 5):
    for j in ("pip", "dip"):
        PAIRS.append(P(f"act_t{t}_{j}_flex_p", "q368_toes_ip_ext", f"toe {t} {j.upper()} flexion / extension",
                       [R(M, 299, "Interphalangeal joints of the foot: flexion of the digits (flexor digitorum longus and "
                                  "brevis) against extension (extensor digitorum longus and brevis).")]))
PAIRS.append(P("act_t1_ip_flex_p", "q368_hallux_ip_ext", "great toe IP flexion / extension",
               [R(M, 299, "Interphalangeal joints of the foot: flexor hallucis longus in the flexion list, extensor hallucis "
                          "longus in the extension list.")]))
PAIRS += [
    # ---- trunk and neck
    P("act_lumbar_flex_p", "act_lumbar_flex_n", "lumbar flexion / extension",
      [R(M, 311, "Rectus abdominis flexes the vertebral column."),
       R(M, 338, "Erector spinae (sacrospinalis) mainly extends the vertebral column.")]),
    P("act_thoracic_flex_p", "act_thoracic_flex_n", "thoracic flexion / extension",
      [R(M, 311, "The anterior abdominal wall muscles flex the vertebral column (rectus abdominis)."),
       R(M, 338, "Erector spinae (sacrospinalis) mainly extends the vertebral column.")]),
    P("erector_spinae", "act_lumbar_flex_p", "trunk extension / flexion (lumbar)",
      [R(M, 338, "Erector spinae (sacrospinalis) mainly extends the vertebral column."),
       R(M, 311, "Rectus abdominis flexes the vertebral column.")]),
    P("erector_spinae", "act_thoracic_flex_p", "trunk extension / flexion (thoracic)",
      [R(M, 338, "Erector spinae (sacrospinalis) mainly extends the vertebral column."),
       R(M, 311, "The anterior abdominal wall flexes the vertebral column.")]),
    P("act_cervical_flex_p", "act_cervical_flex_n", "neck flexion / extension",
      [R(S, 91, "Sternocleidomastoid flexes the cervical vertebral column."),
       R(S, 205, "The prevertebral muscles are (weak) flexors of the head and neck."),
       R(S, 225, "The suboccipital muscles extend the head at the atlanto-occipital joints.")]),
    P("suprahyoid", "infrahyoid", "hyoid elevation / depression",
      [R(S, 110, "The infrahyoid (strap) muscles depress the hyoid bone after it has been elevated in swallowing."),
       R(S, 147, "The suprahyoid muscles (mylohyoid among them) fix and elevate the hyoid bone.")]),
]

LAT = ("Lateral flexion to one side is opposed by the same muscles of the other side, which are already in this group "
       "(it holds both sides); there is no separate opposing group.")
ROT = ("The two spinal rotation groups split rotation to the same side and to the opposite side, each holding both sides "
       "-- the right member of one and the left member of the other turn the same way, so they are not antagonists; the "
       "opposing rotation is produced by the same groups' members of the other side.")
NONE = {
    "act_cervical_lat_p": LAT, "act_lumbar_lat_p": LAT, "act_thoracic_lat_p": LAT,
    "act_cervical_rot_p": ROT, "act_cervical_rot_n": ROT, "act_thoracic_rot_p": ROT, "act_thoracic_rot_n": ROT,
    "gluteal": "Mixed actions: gluteus maximus is the prime extensor of the hip, gluteus medius and minimus abduct and "
               "medially rotate it (Mannan 2017 pp. 296-297); the opposing groups are given per action instead.",
    "anterolateral_abdominal_wall": "Grouped by region: rectus abdominis flexes the vertebral column (Mannan 2017 p. 311) "
               "while transversus abdominis only compresses the abdomen; the trunk-flexion action groups carry the pair with "
               "the erector spinae.",
    "rotator_cuff": "Stabiliser group: it holds the humeral head in the glenoid, and its own members rotate in opposite "
                    "directions (subscapularis medially; infraspinatus, teres minor laterally -- Mannan 2017 p. 196).",
    "rotator_cuff_plus": "Stabiliser group with the structures it runs under (see Rotator cuff); no opposing group.",
    "scalenes": "Grouped by region; their actions (flexing and side-bending the neck, raising the upper ribs) have no single "
                "opposing group.",
    "suboccipital": "Postural group that steadies and extends the head (Sontakke 2023 p. 225); no opposing group.",
    "thenar": "Grouped by region (the short muscles of the thumb) with mixed actions; the opposing movements are given per "
              "joint in the thumb action groups.",
    "hypothenar": "Grouped by region (the short muscles of the little finger) with mixed actions; no opposing group.",
    "itb_tensors": "Defined by a shared insertion (the iliotibial tract), not by an action at one joint.",
    "calcaneal_tendon_contributors": "Defined by a shared tendon (calcaneal), not by an action; the plantarflexion groups carry "
                                     "the pair.",
    "patellar_tendon_contributors": "Defined by a shared tendon (quadriceps / patellar), not by an action; Quadriceps femoris "
                                    "carries the pair.",
    "pes_anserinus": "Defined by a shared insertion (the three medial knee tendons), not by an action.",
    "carpal_tunnel_contents": "Defined by a shared tunnel (tendons and a nerve), not by an action.",
}


def build() -> dict:
    groups = {}
    for p, f in REL.items():
        d = json.loads(f.read_text(encoding="utf-8"))
        groups[p] = {g["id"]: g for g in d["fgroups"]}
    common = set(groups["base_m"]) & set(groups["base_f"])
    known = common | set(ADDED)
    seen, problems = set(), []
    for pr in PAIRS:
        for k in ("a", "b"):
            if pr[k] not in known:
                problems.append(f"pair names unknown group {pr[k]}")
        key = tuple(sorted((pr["a"], pr["b"])))
        if key in seen or pr["a"] == pr["b"]:
            problems.append(f"duplicate / self pair {key}")
        seen.add(key)
        for r in pr["refs"]:
            if r["book"] not in BOOKS or not r["page"] or not r["note"]:
                problems.append(f"pair {key}: incomplete citation")
    paired = {pr[k] for pr in PAIRS for k in ("a", "b")}
    for g in NONE:
        if g not in common:
            problems.append(f"none names unknown group {g}")
        if g in paired:
            problems.append(f"{g} is both paired and in none")
    uncovered = sorted(common - paired - set(NONE))
    if uncovered:
        problems.append(f"groups neither paired nor explained: {uncovered}")
    if problems:
        raise SystemExit("antagonist table invalid:\n  " + "\n  ".join(problems))
    return {
        "schema": "nmsk.antagonist_groups.v1", "round": "Q368",
        "doc": "Opposing (antagonist) functional groups for the name card's ADD menu. Group ids are the Q298 functional "
               "groups (data/derived/Q298_relations_<page>.json fgroups, identical on both Base pages) plus the groups "
               "defined here under added_groups (members are page-id bases; the sidecar adds _l / _r). Pairs are undirected "
               "(A opposes B and B opposes A). Every pair cites the book statement it rests on (printed page, paraphrase "
               "only). Built by scripts/anatomy/q368/build_antagonists_q368.py.",
        "books": BOOKS, "not_used": NOT_USED, "labels": LABELS, "added_groups": ADDED, "pairs": PAIRS,
        "none": dict(sorted(NONE.items())),
        "counts": {"pairs": len(PAIRS), "groups_paired": len(paired), "groups_without": len(NONE), "added_groups": len(ADDED),
                   "q298_groups": len(common)},
    }


def main() -> int:
    res = build()
    txt = json.dumps(res, ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == txt
        print("ANTAGONISTS_Q368_" + ("UP_TO_DATE" if ok else "STALE"))
        return 0 if ok else 1
    OUT.write_text(txt, encoding="utf-8")
    print(f"{OUT.relative_to(REPO)}: {res['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
