#!/usr/bin/env python3
"""Q206: prints the numeric bullets of the PROJECT_STATE.md Q206 section from the committed JSONs (Q206_summary_{male,female}.json, Q206_continuity.json, Q206_ship_diff_*.json, Q206_moved_over_5mm.json,
Q206_bones_vs_skin.json, Q206_triquetrum_r.json)."""
import json
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "derived"
L = lambda n: json.loads((D / n).read_text())


def trio(v):
    return f"{v[0]}/{v[1]}/{v[2]}"


def main():
    cont = L("Q206_continuity.json")
    for w, ks in (("male", ("z_male", "z_male_fit", "q205_m", "q206_m")), ("female", ("z_base_f", "z_female_fit", "q205_f", "q206_f"))):
        s = L(f"Q206_summary_{w}.json")
        j = s["wrist_junction_major_moderate_minor"]
        sd = L(f"Q206_ship_diff_{w}.json")
        print(f"## {w}")
        print("- Q198 wrist junctions (major/moderate/minor) Q205 -> Q206: L " + trio(j["before"]["wrist_l"]) + " -> " + trio(j["after"]["wrist_l"]) + ", R " + trio(j["before"]["wrist_r"]) + " -> " + trio(j["after"]["wrist_r"])
              + "; elbow L " + trio(j["before"]["elbow_l"]) + " -> " + trio(j["after"]["elbow_l"]) + ", R " + trio(j["before"]["elbow_r"]) + " -> " + trio(j["after"]["elbow_r"])
              + "; shoulder L " + trio(j["before"]["shoulder_l"]) + " -> " + trio(j["after"]["shoulder_l"]) + ", R " + trio(j["before"]["shoulder_r"]) + " -> " + trio(j["after"]["shoulder_r"]))
        f = s["wrist_structures_findings_ge_moderate"]
        print(f"- wrist-zone findings >= moderate on non-bone / non-muscle structures: {f['before']['n']} {f['before']['by_check']} -> {f['after']['n']} {f['after']['by_check']}; remaining: {[ (x[0], x[1], x[2], x[4]) for x in f['after']['items']]}")
        z = s["wrist_zone_soft_stats"]
        print("- Q198 wrist zone (R = 55 mm), non-muscle structures: inside bone (> 8 % of vertices, depth > 3 mm) L " + str(z["before"]["l"]["inside_bone_gt8pct_depth_gt3mm"]) + " -> " + str(z["after"]["l"]["inside_bone_gt8pct_depth_gt3mm"])
              + ", R " + str(z["before"]["r"]["inside_bone_gt8pct_depth_gt3mm"]) + " -> " + str(z["after"]["r"]["inside_bone_gt8pct_depth_gt3mm"])
              + "; outside skin (> 5 %, excursion > 5 mm) L " + str(z["before"]["l"]["outside_skin_gt5pct_excursion_gt5mm"]) + " -> " + str(z["after"]["l"]["outside_skin_gt5pct_excursion_gt5mm"])
              + ", R " + str(z["before"]["r"]["outside_skin_gt5pct_excursion_gt5mm"]) + " -> " + str(z["after"]["r"]["outside_skin_gt5pct_excursion_gt5mm"])
              + "; mean inside-bone share L " + str(z["before"]["l"]["mean_inside_bone_pct"]) + " -> " + str(z["after"]["l"]["mean_inside_bone_pct"]) + " %, R " + str(z["before"]["r"]["mean_inside_bone_pct"]) + " -> " + str(z["after"]["r"]["mean_inside_bone_pct"])
              + " %; mean outside-skin share L " + str(z["before"]["l"]["mean_outside_skin_pct"]) + " -> " + str(z["after"]["l"]["mean_outside_skin_pct"]) + " %, R " + str(z["before"]["r"]["mean_outside_skin_pct"]) + " -> " + str(z["after"]["r"]["mean_outside_skin_pct"]) + " %")
        r = s["regions"]
        print("- Q204 regional pass wrist_hand major/moderate/minor " + trio([r["before"]["wrist_hand"][k] for k in ("major", "moderate", "minor")]) + " -> " + trio([r["after"]["wrist_hand"][k] for k in ("major", "moderate", "minor")])
              + " (soft tissue inside bone sev>=2 " + str(r["before"]["wrist_hand"]["soft_inside_bone_sev2plus"]) + " -> " + str(r["after"]["wrist_hand"]["soft_inside_bone_sev2plus"]) + ", outside skin sev>=2 " + str(r["before"]["wrist_hand"]["soft_outside_skin_sev2plus"]) + " -> " + str(r["after"]["wrist_hand"]["soft_outside_skin_sev2plus"]) + ")"
              + "; arm_elbow_forearm " + trio([r["before"]["arm_elbow_forearm"][k] for k in ("major", "moderate", "minor")]) + " -> " + trio([r["after"]["arm_elbow_forearm"][k] for k in ("major", "moderate", "minor")]))
        for sdn in "lr":
            row = []
            for k in ks:
                v = cont[k][sdn]
                row.append(f"mean {round(sum(v.values()) / len(v), 2)} / max {max(v.values())} / > 3 mm {sum(1 for x in v.values() if x > 3)}")
            print(f"- wrist chain gaps ({len(cont[ks[0]][sdn])} parent -> child pairs) side {sdn.upper()}: unfitted base | Q202 page | Q205 page | Q206 page = " + " | ".join(row))
        print(f"- scope: {len(sd['geometry_changed'])} geometry-changed (all listed), {sd['card_only'] and len(sd['card_only'])} card-only, {sd['unchanged']} unchanged, {len(sd['geometry_changed_but_not_listed'])} unlisted")
    m = L("Q206_moved_over_5mm.json")
    for w in ("male", "female"):
        print(f"- moved > 5 mm {w}: {m[w]['counts_over_5mm']}")
    b = L("Q206_bones_vs_skin.json")
    for w in ("male", "female"):
        for sdn in "lr":
            print(f"- bones outside the displayed skin {w} {sdn}: " + str([(x["id"], x["outside_skin_gt3mm_pct"], x["max_outside_mm"]) for x in b[w][sdn]["bones_with_gt1pct_outside"][:4]]))


if __name__ == "__main__":
    main()
