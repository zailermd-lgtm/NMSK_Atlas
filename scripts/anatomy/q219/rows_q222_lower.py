"""Q222 rows, part 2: hip, thigh, leg, foot (PubMed-verified on 2026-10-12; see refs_q222.py)."""
from rows_common import P, S

# ------------------------------------------------------------------ adductor magnus
S("adductor_magnus.parts", "adductor_magnus", "head_belly", "Adductor magnus: number of parts", [
    (2, "takizawa2014", "adductor part (AM1-AM3) + hamstrings part (AM4), the traditional division"),
    (4, "takizawa2014", "AM1-AM4 by the perforating arteries and the adductor hiatus (21 limbs)"),
    (4, "maguchi2026", "adductor minimus, superior part and inferior part of the adductor part, hamstring part (9 muscles)")],
  note="The traditional two-part description (adductor + hamstring part) is refined to four parts by both studies; the two four-part schemes are defined differently (nerve / perforator based vs insertion / fascicle based) and are not mapped one-to-one.")
P("adductor_magnus", "adductor_minimus", "head_belly", "Adductor minimus (APm)", "Most proximal component; inserts on the lateral lip of the linea aspera (contrary to the classical medial lip).", ["maguchi2026"],
  ev="cadaver n=9", setid="adductor_magnus.parts", anchor=dict(bone="femur", landmark="linea aspera, lateral lip"))
P("adductor_magnus", "adductor_part_superior", "head_belly", "Superior part of the adductor part (APs)", "Inserts on the lateral lip of the linea aspera.", ["maguchi2026"],
  ev="cadaver n=9", setid="adductor_magnus.parts", anchor=dict(bone="femur", landmark="linea aspera, lateral lip"))
P("adductor_magnus", "adductor_part_inferior", "head_belly", "Inferior part of the adductor part (APi)", "Only this component attaches to the medial lip of the linea aspera and the medial supracondylar line.", ["maguchi2026"],
  ev="cadaver n=9", setid="adductor_magnus.parts", anchor=dict(bone="femur", landmark="medial lip of the linea aspera and medial supracondylar line"))
P("adductor_magnus", "hamstring_part", "head_belly", "Hamstring part (HP)", "Fourth component; innervated by the tibial portion of the sciatic nerve (= AM4 of Takizawa).", ["maguchi2026", "takizawa2014"],
  ev="cadaver n=9; n=21", setid="adductor_magnus.parts", related=["adductor_magnus_distal_tendon"])
P("adductor_magnus", "am1_am4_innervation_zones", "head_belly", "Perforator-defined segments AM1-AM4 (obturator vs sciatic territory)", "AM1 is supplied only by the obturator nerve; AM2, AM3 and AM4 by both the posterior obturator branch and the tibial portion of the sciatic nerve in 9.5 %, 95.2 % and 28.6 % of 21 limbs.", ["takizawa2014"],
  ev="cadaver n=21", var="AM3 double innervation 95.2 %", setid="adductor_magnus.parts", note="Segments delimited by perforating arteries and the adductor hiatus; this row carries the segment definition, not a position.")
P("adductor_magnus", "origin_tendons_and_arches", "muscle_tendon_junction", "Origin tendons (superficial / deep membranous) and intramuscular tendinous arches", "Superficial and deep membranous origin tendons, insertion tendons and intramuscular tendinous arches were identified systematically with marked interindividual variation in position.", ["maguchi2026"],
  ev="cadaver n=9", note="Position of the tendinous arches varies between individuals; no zone is given in the abstract -> no geometry.")

# ------------------------------------------------------------------ tensor fasciae latae / gluteal fascia / iliotibial connection
P("tensor_fasciae_latae", "origin_iliac_crest_outer_lip", "origin_part", "Origin: anterior part of the outer lip of the iliac crest", "TFL arises from the anterior part of the outer lip of the iliac crest.", ["alhayani2009"],
  ev="cadaver n=18", anchor=dict(bone="hip_bone", landmark="iliac crest, anterior outer lip"), geom=dict(rule="end_snap_bone", end="proximal", bone="hip_bone", tol_mm=10))
P("tensor_fasciae_latae", "insertion_iliotibial_tract", "insertion_point", "Insertion: iliotibial tract slightly below and in front of the greater trochanter", "Attached to the iliotibial tract slightly below and in front of the greater trochanter; the ITB layers merge at the lower portion of the TFL.", ["alhayani2009", "huang2013"],
  ev="cadaver n=18; review", related=["iliotibial_tract"])
P("gluteal_fascia", "gluteal_aponeurotic_fascia_gluteus_medius", "ligament_component", "Gluteal aponeurotic fascia over the gluteus medius", "Posterior contribution to the fascia lata: the aponeurotic fascia covering the gluteus medius merges with the iliotibial band at the buttock and hip.", ["huang2013"], cls="fascia",
  ev="anatomy review with MR correlation", related=["iliotibial_tract", "fascia_lata", "gluteus_medius"])
P("gluteus_medius", "iliotibial_band_adhesion", "muscle_tendon_junction", "Adhesion to the iliotibial band (free outer surface)", "An adhesion connects the outer surface of the free part of the gluteus medius (not covered by the gluteus maximus or TFL) to the midportion of the iliotibial band.", ["szymanski2026"],
  ev="cadaver n=10 lower limbs", related=["iliotibial_tract"])
P("iliotibial_tract", "three_layers_proximal", "ligament_component", "Three layers of the proximal iliotibial band", "At the pelvis and hip the ITB consists of three layers that merge at the lower portion of the TFL; with the gluteal aponeurotic fascia it continues to the Gerdy tubercle.", ["huang2013"], cls="fascia",
  ev="anatomy review with MR correlation", anchor=dict(bone="tibia", landmark="Gerdy tubercle (distal attachment)"),
  note="Layer names are not given in the abstract.")

# ------------------------------------------------------------------ gracilis / sartorius (pes anserinus layers)
P("gracilis", "distal_tendon_aponeurotic_membrane", "insertion_point", "Distal tendon: aponeurotic membrane fused with the crural fascia", "The distal gracilis tendon has an aponeurotic membrane fused with the fascia cruris; a deep longitudinal fibrous bundle lies on this membrane.", ["mochizuki2004"],
  ev="cadaver, 9 legs of 5 adults", related=["pes_anserinus", "crural_fascia"])
P("gracilis", "insertion_tibia_pes_anserinus", "insertion_point", "Insertion: pes anserinus, medial to the tibial tuberosity", "With semitendinosus and sartorius the gracilis tendon inserts on the medial side of the tibial tuberosity; the first two attach superiorly and medially to the sartorius tendon.", ["zielinska2023pes"],
  ev="cadaver dissection (variant case + normal description)", anchor=dict(bone="tibia", landmark="medial to the tibial tuberosity"), related=["pes_anserinus"])
P("sartorius", "superficial_longitudinal_fibrous_bundle", "ligament_component", "Superficial longitudinal fibrous bundle on the sartorius", "A superficial longitudinal fibrous bundle lies on the superficial surface of the sartorius, fusing with the fascia cruris.", ["mochizuki2004"], ev="cadaver, 9 legs of 5 adults", related=["crural_fascia"])
P("sartorius", "insertion_pes_anserinus_superficial_layer", "insertion_point", "Insertion: pes anserinus, superficial layer (to the crural fascia in the variant)", "Normally the three tendons insert medial to the tibial tuberosity; in a rare arrangement the sartorius forms an additional superficial layer attached to the crural fascia well below the tuberosity.", ["zielinska2023pes"],
  ev="cadaver dissection (single variant case)", var="rare variant", related=["pes_anserinus"])

# ------------------------------------------------------------------ extensor hallucis longus
P("extensor_hallucis_longus", "origin_fibula_interosseous_membrane", "origin_part", "Origin: anterior surface of the fibula and interosseous membrane (medial to EDL)", "Arises from the anterior fibular surface and the interosseous membrane medial to the origin of the extensor digitorum longus.", ["zielinska2021ehl"],
  ev="narrative review", anchor=dict(bone="fibula", landmark="anterior surface and interosseous membrane"), geom=dict(rule="end_snap_bone", end="proximal", bone="fibula", tol_mm=10))
P("extensor_hallucis_longus", "insertion_distal_phalanx", "insertion_point", "Insertion: dorsal base of the distal phalanx of the hallux", "Usually unipennate with insertion on the dorsum of the base of the distal phalanx of the hallux.", ["zielinska2021ehl", "zdilla2018"],
  ev="review", anchor=dict(bone="first_distal_phalanx", landmark="dorsal base"))
P("extensor_hallucis_longus", "accessory_tendinous_slips", "insertion_point", "Accessory tendinous slips (to neighbouring bones, muscles, tendons)", "A vast majority of EHL muscles carry one or more accessory slips; the most common variation is an additional slip near the distal attachment; classification systems differ.", ["zielinska2021ehl", "zdilla2018"],
  ev="reviews", var="'vast majority'", note="Prevalence figures differ between the studies pooled by the reviews and are not reproduced.")

# ------------------------------------------------------------------ fibularis brevis
P("fibularis_brevis", "insertion_fifth_metatarsal_tuberosity", "insertion_point", "Insertion footprint: base / tuberosity of the fifth metatarsal (mean 15 mm long)", "Footprint mean length 15 mm (10-specimen cadaver study cited in the abstract); its distal lateral extent is 15 mm from the tuberosity; the plantar fascia footprint lies alongside (PB and PF footprints extend into the Jones fracture site in 29 % and 43 % of 21 metatarsals).", ["marcus2026", "vandijk2020"],
  ev="cadaver (10 specimens, as cited; 21 MT5 on CT)", anchor=dict(bone="fifth_metatarsal", landmark="tuberosity of the base"), related=["plantar_aponeurosis"],
  note="The 15 mm figure is reported in the abstract of Marcus 2026 (from the authors' earlier study); van Dijk 2020 provides the mapping; the earlier paper itself was not retrieved.")

# ================================================================== batch 2 (tibialis anterior, foot intrinsics, articularis genus, short external rotators)
S("tibialis_anterior.tendon_insertion_patterns", "tibialis_anterior", "insertion_point", "Tibialis anterior tendon: insertion patterns", [
    (3, "lee2023ta", "three insertion patterns (only Type I is described in the abstract), 70 limbs")],
  note="Only Type I (57.1 %) is characterised in the abstract; Types II and III are not named here.")
P("tibialis_anterior", "insertion_medial_cuneiform_band", "insertion_point", "Insertion band to the medial cuneiform (plantar > medial territory)", "In the commonest pattern (Type I, 57.1 % of 70 limbs) the tendon splits into two equal-sized bands; this band attaches to the medial cuneiform with a wider width than the metatarsal band and a larger plantar than medial territory.", ["lee2023ta"],
  ev="dissection n=70 + 3D model", var="Type I 57.1 %", anchor=dict(bone="medial_cuneiform", landmark="plantar > medial surface"), setid="tibialis_anterior.tendon_insertion_patterns")
P("tibialis_anterior", "insertion_first_metatarsal_base_band", "insertion_point", "Insertion band to the base of the first metatarsal (plantar > medial territory)", "The second equal-sized band of the Type I pattern attaches to the base of the first metatarsal, again with a larger plantar than medial territory.", ["lee2023ta"],
  ev="dissection n=70 + 3D model", var="Type I 57.1 %", anchor=dict(bone="first_metatarsal", landmark="base, plantar > medial surface"), setid="tibialis_anterior.tendon_insertion_patterns")

S("adductor_hallucis.heads", "adductor_hallucis", "head_belly", "Adductor hallucis: heads and compartments", [
    (2, "arakawa2006", "oblique head + transverse head"), (3, "arakawa2006", "oblique head divided into lateral, dorsal and medial compartments by its intramuscular nerves (or two: dorsal and medial); the transverse head is not divisible")],
  note="Two heads (oblique, transverse); the oblique head has 2-3 nerve-defined compartments.")
P("adductor_hallucis", "oblique_head", "head_belly", "Oblique head (3 or 2 compartments by innervation)", "Divided into lateral, dorsal and medial parts (or dorsal and medial); a communicating twig between lateral and medial plantar nerves penetrates it in 76.5 % of 17 feet; only the lateral part has a different innervation (possibly a different origin).", ["arakawa2006"],
  ev="dissection + nerve fibre analysis, 17 feet of 15 cadavers", var="3 or 2 compartments; twig 76.5 %", setid="adductor_hallucis.heads")
P("adductor_hallucis", "transverse_head", "head_belly", "Transverse head (absent in 6 %)", "Origin usually from the deep transverse metatarsal ligaments, plantar ligaments of the lateral MTP joints, intermuscular septa of the third and fourth muscle layers and Henkel's fibular syndesmosis; insertion usually fleshy into the lateral border of the oblique head; absent in 6 % of 91 feet.", ["cralley1979", "arakawa2006"],
  ev="dissection of 91 feet; 17 feet", var="absent 6 %", setid="adductor_hallucis.heads", note="Origins and insertions differ from textbook descriptions according to the source.")

S("articularis_genus.layers", "articularis_genus", "head_belly", "Articularis genus: layers / bundles", [
    (3, "grob2018", "three layers: superficial, intermediate, deep (18 limbs)"),
    (7, "woodley2012", "mean 7 bundles at dissection (range 4-10); only a mean of 4 seen on MRI (22 limbs)")],
  note="Layer count (Grob) and bundle count (Woodley) are different units; MRI under-counts the bundles.")
P("articularis_genus", "superficial_layer", "head_belly", "Superficial layer (from vastus intermedius and the femur)", "Bundles arise from the vastus intermedius and from the anterior and anterolateral femur.", ["grob2018"], ev="dissection n=18 limbs", setid="articularis_genus.layers", anchor=dict(bone="femur", landmark="anterior and anterolateral surfaces"), related=["vastus_intermedius"])
P("articularis_genus", "intermediate_layer", "head_belly", "Intermediate layer (from vastus intermedius + femur in 60 %, femur only in 40 %)", "Origin from both the vastus intermedius and the femur in 60 % of specimens, from the femur only in 40 %.", ["grob2018"], ev="dissection n=18 limbs", var="60 % / 40 %", setid="articularis_genus.layers")
P("articularis_genus", "deep_layer", "head_belly", "Deep layer (from the anterior femur only)", "Arises solely from the anterior surface of the femur.", ["grob2018"], ev="dissection n=18 limbs", setid="articularis_genus.layers", anchor=dict(bone="femur", landmark="anterior surface, distal third"))
P("articularis_genus", "distal_attachments_suprapatellar_bursa_capsule", "insertion_point", "Distal attachments: suprapatellar bursa wall, vastus intermedius tendon, knee capsule", "Proximal and / or posterior wall of the suprapatellar bursa, deep surface of the vastus intermedius distal tendon, medial and lateral joint capsule.", ["woodley2012", "grob2018"],
  ev="dissection + MRI, 22 limbs", related=["vastus_intermedius", "vastus_medialis"])

P("obturator_internus", "tendon_with_gemelli_hip_triceps", "insertion_point", "Tendon joined by both gemelli (hip triceps tendon)", "Obturator internus inserts nearly perpendicularly on the proximal femur; both gemelli insert onto its tendon, which together form the hip triceps tendon.", ["assi2024"],
  ev="cadaver, 18 hips", related=["gemellus_superior", "gemellus_inferior"])
P("gemellus_superior", "insertion_onto_obturator_internus_tendon", "insertion_point", "Insertion onto the tendon of obturator internus", "Distal insertion is onto the tendon of the obturator internus (hip triceps tendon), not directly on the femur.", ["assi2024"], ev="cadaver, 18 hips", related=["obturator_internus"])
P("gemellus_inferior", "insertion_onto_obturator_internus_tendon", "insertion_point", "Insertion onto the tendon of obturator internus", "Distal insertion is onto the tendon of the obturator internus (hip triceps tendon), not directly on the femur.", ["assi2024"], ev="cadaver, 18 hips", related=["obturator_internus"])
P("obturator_externus", "insertion_proximal_femur_perpendicular", "insertion_point", "Insertion on the proximal femur (nearly perpendicular)", "Obturator externus inserts quasi perpendicularly on the proximal femur.", ["assi2024"], ev="cadaver, 18 hips", anchor=dict(bone="femur", landmark="proximal femur"))

P("abductor_hallucis", "deep_fascia_continuous_with_plantar_fascia", "ligament_component", "Enveloping deep fascia continuous with the plantar fascia (medial side)", "The plantar fascia extends medially into the deep fascia enveloping the abductor hallucis.", ["stecco2013pf"], ev="dissection of 12 feet", related=["plantar_aponeurosis"],
  note="Fascial continuity, not a muscle head or an attachment; the muscle's own origin / insertion are not covered by this reference.")
P("abductor_digiti_minimi_foot", "deep_fascia_continuous_with_plantar_fascia", "ligament_component", "Enveloping deep fascia continuous with the plantar fascia (lateral side)", "The plantar fascia extends laterally into the deep fascia enveloping the abductor digiti minimi.", ["stecco2013pf"], ev="dissection of 12 feet", related=["plantar_aponeurosis"],
  note="Fascial continuity only.")
P("quadratus_plantae", "origin_calcaneus_insertion_fdl_tendon", "insertion_point", "Insertion: posterolateral surface of the flexor digitorum longus tendons (origin from the calcaneus)", "Typically originates from the calcaneus and inserts into the posterolateral surface of the FDL tendons.", ["sooriakumaran2005"], ev="comparative-anatomy review", related=["flexor_digitorum_longus"])
P("quadratus_plantae", "accessory_slip_from_adm_fascia", "origin_part", "Variant: accessory slip from the fascia over abductor digiti minimi to the FDL tendon (single case)", "Slip surrounding the lateral plantar nerve and vessels, innervated by the lateral plantar nerve; potential tarsal-tunnel-like compression.", ["nayak2021"], ev="case report", var="case report")
