"""Q222 rows, part 6: labra, discs, retinacula, femoral canal (PubMed-verified on 2026-10-12)."""
from rows_common import P, S

# ------------------------------------------------------------------ glenoid labrum / biceps long-head attachment
P("glenoid_labrum", "superior_anterosuperior_sector_variable", "ligament_component", "Superior and anterosuperior sectors: variable labrum-glenoid relation", "A wide variety of morphologic labral-glenoid findings in the superior and anterosuperior sectors (36 cadaver shoulders), incl. the sublabral hole, which is a physiologic variant.", ["barthel2003"], cls="cartilage",
  ev="cadaver n=36 shoulders, macro + microscopy", var="wide variation")
P("glenoid_labrum", "posterior_inferior_sectors_firm_bond", "ligament_component", "Dorsal and inferior sectors: uniform, firm labrum-glenoid bond", "Relatively uniform anatomy with a firm bond between labrum and glenoid.", ["barthel2003"], cls="cartilage", ev="cadaver n=36 shoulders")
S("biceps_long_head.attachment_types", "biceps_brachii_tendon_complex", "origin_part", "Long head of biceps: types of attachment at the glenoid", [
    (4, "barthel2003", "four types of biceps tendon attachment, as described by Vangsness (36 shoulders)")])
P("biceps_brachii_tendon_complex", "attachment_types_four", "origin_part", "Long-head attachment: four types (supraglenoid tubercle / labrum)", "Four types of biceps tendon attachment to the superior glenoid / labrum were identified (the abstract does not list them; Vangsness' scheme).", ["barthel2003"], cls="tendon",
  ev="cadaver n=36 shoulders", setid="biceps_long_head.attachment_types", related=["glenoid_labrum", "biceps_brachii"],
  note="Count of types only; the individual types are not named in the abstract and are not invented here.")

# ------------------------------------------------------------------ acetabular labrum
P("acetabular_labrum", "zone_anterosuperior", "ligament_component", "Antero-superior zone (clock-face quadrant)", "Free nerve endings and nerve end organs are more frequent in the antero-superior zone than in the other quadrants; healed-tear-like vascularity in four specimens.", ["alzaharani2014"], cls="cartilage",
  ev="histology of 20 labra from arthroplasty patients", var="nerve endings more frequent")
P("acetabular_labrum", "zone_posterosuperior", "ligament_component", "Postero-superior zone (clock-face quadrant)", "As the antero-superior zone: more free nerve endings and nerve end organs than elsewhere.", ["alzaharani2014"], cls="cartilage", ev="histology of 20 labra")

# ------------------------------------------------------------------ TFCC
S("tfcc.components", "tfcc_disc", "ligament_component", "TFCC: components", [
    (6, "winnett2025", "disc proper, meniscus homologue, ECU sub-sheath, palmar ulno-carpal ligaments, palmar and dorsal distal radio-ulnar ligaments (the radio-ulnar ligaments counted as two, ulno-carpal ligaments as one group)")],
  note="Count depends on whether the ulnocarpal ligaments (ulnolunate, ulnotriquetral) and the two radioulnar ligaments are counted singly.")
for slug, nm, ds in [("disc_proper", "Disc proper (articular disc)", "Central fibrocartilage disc of the TFCC."),
                     ("meniscus_homologue", "Meniscus homologue", "Ulnocarpal meniscus homologue component, demonstrated sonographically."),
                     ("ecu_subsheath", "Extensor carpi ulnaris sub-sheath", "The ECU sub-sheath is counted as a component of the TFCC."),
                     ("palmar_ulnocarpal_ligaments", "Palmar-sided ulno-carpal ligaments", "Palmar ulno-carpal ligaments."),
                     ("palmar_radioulnar_ligament", "Palmar distal radio-ulnar ligament", "With its foveal insertion, among the most important stabilisers of the TFCC (Mak 2017)."),
                     ("dorsal_radioulnar_ligament", "Dorsal distal radio-ulnar ligament", "With its foveal insertion, among the most important stabilisers of the TFCC (Mak 2017).")]:
    P("tfcc_disc", slug, "ligament_component", nm, ds, ["winnett2025"] + (["mak2017"] if "radioulnar" in slug else []), cls="cartilage", ev="sonographic anatomy review; surgical review", setid="tfcc.components")

# ------------------------------------------------------------------ TMJ disc
for slug, nm, ds in [("anterior_band", "Anterior band", "Thicker part of the biconcave disc (anterior)."),
                     ("intermediate_zone", "Intermediate zone", "Thinnest part; collagen runs mainly anteroposteriorly, with a ring-like peripheral orientation."),
                     ("posterior_band", "Posterior band", "Thicker part of the biconcave disc (posterior).")]:
    P("tmj_disc", slug, "ligament_component", nm, ds, ["detamore2003", "giambartolomei2011"], cls="cartilage", ev="review (biochemistry / mechanics); fetal measurements, 16-20 weeks",
      note="Band thickness was measured in fetuses (Giambartolomei 2011); adult values are not given in the abstracts used.")

# ------------------------------------------------------------------ superior peroneal retinaculum / tunnel
P("peroneal_retinaculum", "tunnel_roof", "ligament_component", "Roof of the superior peroneal tunnel: superior peroneal retinaculum", "The tunnel is spacious; the superior peroneal retinaculum forms its roof.", ["athavale2011"], cls="fascia",
  ev="cadaver n=58 limbs", related=["fibularis_tendon_complex"])
P("peroneal_retinaculum", "tunnel_floor_osseous", "ligament_component", "Floor, osseous component: retromalleolar groove of the fibula", "The retromalleolar groove has a constantly concave contour (60 dry fibulae) and forms only part of the floor.", ["athavale2011"], cls="fascia", ev="cadaver n=58; dry fibulae n=60")
P("peroneal_retinaculum", "tunnel_floor_nonosseous", "ligament_component", "Floor, non-osseous component: lower part of the posterior intermuscular septum of the leg", "The non-osseous floor is the lower part of the posterior intermuscular septum.", ["athavale2011"], cls="fascia", ev="cadaver n=58 limbs", related=["posterior_intermuscular_septum_leg"])
P("peroneal_retinaculum", "tunnel_contents_variants", "fascial_passage", "Contents beyond the two tendons: PB muscle fibres, peroneus quartus, split PB tendon, double PL tendon, accessory peroneal nerve", "Peroneus brevis muscle fibres were the most frequent additional content, then the peroneus quartus; split PB tendon, double PL tendon and an accessory peroneal nerve were observed.", ["athavale2011", "wang2005"], cls="fascia",
  ev="cadaver n=58 limbs; MR review", var="frequent", passes=dict(kind="tendon", traversing=["fibularis_longus", "fibularis_brevis"], traversing_text="peroneus quartus, accessory nerve when present", through="superior peroneal tunnel (under the superior peroneal retinaculum)"))
S("fibularis_tendon.variants", "fibularis_tendon_complex", "insertion_point", "Peroneal tendons: variants listed", [
    (1, "wang2005", "bifurcated peroneus brevis tendon"), (1, "wang2005", "peroneus quartus tendon inserting into the PB tendon")], note="Variant list, not a count of parts.")
P("fibularis_tendon_complex", "peroneus_quartus_to_pb_tendon", "insertion_point", "Peroneus quartus tendon inserting into the peroneus brevis tendon (variant)", "An accessory peroneus quartus muscle may insert into the PB tendon.", ["wang2005"], cls="tendon", ev="MR imaging review", var="variant")
P("fibularis_tendon_complex", "pb_tendon_bifurcated", "insertion_point", "Bifurcated / mildly crescentic peroneus brevis tendon (variant)", "A bifurcated or mildly crescentic PB tendon is a normal variant to recognise on MR; a split PB tendon was also seen in the dissection series.", ["wang2005", "athavale2011"], cls="tendon", ev="MR review; cadaver n=58", var="variant")

# ------------------------------------------------------------------ femoral canal / sheath / lacunar ligament
P("femoral_canal", "boundary_lacunar_ligament_curved_edge", "ligament_component", "Lacunar ligament curved edge (medial boundary)", "The fascia lata turns back as the lacunar ligament, fusing with the pectineus fascia 1-1.5 cm below Cooper's ligament; its curved edge supports the transversalis fascia of the floor and bars the canal from entering the thigh.", ["lytle1979"], cls="fascia",
  ev="dissection of the posterior abdominal wall + pelvis (J Anat 1979)", related=["inguinal_ligament"])
P("femoral_canal", "floor_transversalis_fascia", "ligament_component", "Floor: transversalis fascia", "The transversalis fascia of the femoral canal floor turns down to form the medial wall of the venous compartment of the femoral sheath.", ["lytle1979"], cls="fascia", ev="dissection", related=["transversalis_fascia", "femoral_sheath"])
S("femoral_sheath.compartments", "femoral_sheath", "ligament_component", "Femoral sheath: compartments", [(3, "lytle1979", "a venous compartment and, 'usually taught', a medial or third compartment = the femoral canal; Lytle disputes that the canal opens unprotected into the thigh")])
P("femoral_sheath", "venous_compartment_medial_wall", "ligament_component", "Venous compartment: medial wall from the transversalis fascia", "Medial wall of the venous compartment formed by the transversalis fascia of the femoral canal floor.", ["lytle1979"], cls="fascia", ev="dissection", setid="femoral_sheath.compartments")
P("femoral_sheath", "third_compartment_femoral_canal_taught", "ligament_component", "Medial (third) compartment = femoral canal (as taught; disputed by the source)", "The femoral canal is usually taught as the medial third compartment of the sheath; the author argues the lacunar ligament closes the canal off from the thigh.", ["lytle1979"], cls="fascia",
  ev="dissection", setid="femoral_sheath.compartments", var="disputed", note="The abstract's own words: 'usually taught' vs the author's finding.  The other compartments of the sheath are not named in the abstract.")
