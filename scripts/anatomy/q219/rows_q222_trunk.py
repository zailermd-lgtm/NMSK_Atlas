"""Q222 rows, part 3: diaphragm, abdominal wall, inguinal region, perineum (PubMed-verified on 2026-10-12)."""
from rows_common import P, S

# ------------------------------------------------------------------ diaphragm
S("diaphragm.lumbar_crura", "diaphragm", "origin_part", "Diaphragm: vertebral levels of the crural attachments", [
    (3, "khadanovich2025", "right crus L2-L4 (bodies) + L2/3 disc"), (3, "khadanovich2025", "left crus L1-L3")],
  note="Level counts differ by side (right crus L2-L4, left L1-L3; 10 specimens); textbook statements (L1-L3 / L1-L2) are not reproduced.")
P("diaphragm", "origin_right_crus", "origin_part", "Right crus: L2-L4 vertebral bodies and the L2/3 intervertebral disc", "The right crus attaches to the L2-L4 vertebral bodies and the L2/3 disc; the thoracic duct overlies it at L3 and L2/3.", ["khadanovich2025"],
  ev="embalmed specimens n=10", anchor=dict(bone="lumbar_vertebrae", landmark="L2-L4 bodies, L2/3 disc"), setid="diaphragm.lumbar_crura", related=["lumbar_vertebrae"])
P("diaphragm", "origin_left_crus", "origin_part", "Left crus: L1-L3 vertebrae", "The left crus inserts onto L1-L3; the cisterna chyli (70 % of specimens) overlaps it at the same levels.", ["khadanovich2025"],
  ev="embalmed specimens n=10", anchor=dict(bone="lumbar_vertebrae", landmark="L1-L3"), setid="diaphragm.lumbar_crura")
P("diaphragm", "crural_passage_sympathetic_trunk", "fascial_passage", "Sympathetic trunks emerge beneath the crura", "Both sympathetic trunks emerge underneath the crura at the L1/2 disc or L1 level.", ["khadanovich2025"],
  ev="embalmed specimens n=10", passes=dict(kind="nerve", traversing=[], traversing_text="sympathetic trunk", through="beneath the diaphragmatic crus (L1/2 disc or L1)"))
P("diaphragm", "aortic_hiatus_or_crus_passage_azygos_ventral_root", "fascial_passage", "Ventral root of the azygos / hemiazygos vein through the aortic hiatus or the crura", "Only the ventral root passes the diaphragm, variably through the aortic hiatus or through the crura; the dorsal root has no contact with the diaphragm.", ["bauer2026"],
  ev="formalin specimens n=20", var="route variable", passes=dict(kind="vessel", traversing=[], traversing_text="ventral root of the azygos (100 %) / hemiazygos vein (90 %)", through="aortic hiatus or crura of the diaphragm"))

# ------------------------------------------------------------------ inguinal region: transversus abdominis / internal oblique / transversalis fascia / cremaster
S("inguinal_canal.posterior_wall", "transversus_abdominis", "ligament_component", "Posterior wall of the inguinal canal: composition patterns", [
    (4, "xiao2024", "four patterns: TAM+AIOMA fused tendinous layer; IOMA+TAM muscular; IOMA+AIOMA; TAM+TAA")])
for slug, nm, ds in [("pattern_tam_aioma_fused", "Pattern 1: transversus abdominis and internal oblique aponeurosis fused into a tendinous layer", "Transversus abdominis muscle and the internal oblique aponeurosis fuse to form a tendinous layer."),
                     ("pattern_ioma_tam_muscular", "Pattern 2: internal oblique and transversus abdominis muscles form a muscular posterior wall", "Internal oblique and transversus abdominis muscles form the muscular posterior wall."),
                     ("pattern_ioma_aioma", "Pattern 3: internal oblique muscle and its aponeurosis continue in the posterior wall", "Internal oblique muscle and its aponeurosis continue in the posterior wall."),
                     ("pattern_tam_taa", "Pattern 4: transversus abdominis muscle and its aponeurosis continue in the posterior wall", "Transversus abdominis muscle and transversus aponeurosis continue in the posterior wall.")]:
    P("transversus_abdominis", slug, "ligament_component", nm, ds + " (30 cadavers; the abstract gives no prevalences).", ["xiao2024"], ev="cadaver n=30", setid="inguinal_canal.posterior_wall", related=["internal_oblique", "cremaster", "inguinal_ligament"],
      note="Patterns of the inguinal-canal posterior wall as reported by one series; prevalence per pattern not in the abstract; naming of the tendon layer as 'conjoint tendon' is not used by the abstract.")
P("transversalis_fascia", "single_membrane_not_in_posterior_wall", "ligament_component", "Transversalis fascia: single thin layer, not part of the posterior wall", "A thin fascial tissue with only one layer of membrane, lying under the abdominal wall on the side of the peritoneal-cavity vessels; not involved in the composition of the posterior wall of the inguinal canal.", ["xiao2024"], cls="fascia",
  ev="cadaver n=30")
P("cremaster", "origin_internal_oblique_transversus", "origin_part", "Origin: internal oblique and transversus abdominis muscles and their aponeuroses", "The tendon membrane of the cremaster is organised from the internal oblique and transversus abdominis muscles and their tendon membranes, extending on the spermatic cord and fixing it to the lower wall of the canal.", ["xiao2024"],
  ev="cadaver n=30", related=["internal_oblique", "transversus_abdominis"])

# ------------------------------------------------------------------ perineum
S("deep_transverse_perineal.existence", "deep_transverse_perineal", "head_belly", "Deep transverse perineal muscle: is there a definable striated muscle?", [
    (0, "kampelmann2025", "no clearly definable striated muscle belly in 10 donors of either sex (striated fibres just over 10 % of the tissue in males, under 1 % in females)")],
  note="Existence of the muscle as a classic named muscle is disputed; only one study is recorded here and it is negative.")
P("deep_transverse_perineal", "deep_perineal_pouch_tissue_plate", "ligament_component", "Tissue plate of the deep perineal pouch (above the perineal membrane)", "A 4-5 mm thick plate between the ischiopubic rami, superior to the perineal membrane; about 80 % connective tissue; males about 10 % smooth + just over 10 % striated muscle; females about 20 % muscle cells, under 1 % striated.", ["kampelmann2025"],
  ev="embalmed donors n=10 (mean age 82)", var="muscle decreases with age", setid="deep_transverse_perineal.existence", related=["perineal_membrane"])
P("bulbospongiosus", "origin_perineal_body_enveloping_bulb", "origin_part", "Origin: perineal body, enveloping the bulbar urethra", "Paired striated muscle originating from the perineal body and enveloping the bulbar portion of the urethra; innervated by the deep branch of the pudendal nerve.", ["lannes2026"],
  ev="narrative review", var="male description", note="Review of the male muscle; the female arrangement is not covered by this reference.")
